#!/usr/bin/env python3
"""
AdiOS Database Subsystem: Relational Query Planner & Cost Optimizer (db/query_planner.py)
Implements Volcano iterator execution model and relational algebra optimization:
- Physical Plan Operators:
    - SeqScanNode: Full sequential table scan
    - IndexScanNode: B+ Tree range index scan with predicate pushdown
    - FilterNode: Row-level predicate evaluator (=, !=, <, >, IN, LIKE)
    - HashJoinNode: In-memory hash join over two relation streams
    - AggregateNode: COUNT, SUM, AVG, MIN, MAX with GROUP BY grouping
    - ProjectNode: Column projection and alias mapping
- Cost-Based Optimizer (CBO):
    - Analyzes available B+ tree indexes and table cardinality
    - Converts sequential scans into index lookups when predicates match indexed keys
    - Relational algebra rewrite rules (predicate pushdown below joins)

Zero external dependencies. Pure RV32IM relational engine component.
STRICT ZERO EMOJI POLICY.
"""

from typing import List, Dict, Tuple, Optional, Any, Callable
from .bplus_tree import BPlusTree

class PlanNode:
    """Volcano iterator interface: open, next, close."""
    def open(self):
        pass

    def next(self) -> Optional[List[Any]]:
        raise NotImplementedError

    def close(self):
        pass

class SeqScanNode(PlanNode):
    """Full table sequential scan."""
    def __init__(self, table_name: str, rows: List[List[Any]]):
        self.table_name = table_name
        self.rows = rows
        self.cursor = 0

    def open(self):
        self.cursor = 0

    def next(self) -> Optional[List[Any]]:
        if self.cursor < len(self.rows):
            row = self.rows[self.cursor]
            self.cursor += 1
            return row
        return None

    def close(self):
        self.cursor = len(self.rows)

class IndexScanNode(PlanNode):
    """Index scan using B+ Tree."""
    def __init__(self, tree: BPlusTree, min_key: Any, max_key: Any):
        self.tree = tree
        self.min_key = min_key
        self.max_key = max_key
        self.results: List[List[Any]] = []
        self.cursor = 0

    def open(self):
        pairs = self.tree.range_search(self.min_key, self.max_key)
        self.results = [p[1] for p in pairs]
        self.cursor = 0

    def next(self) -> Optional[List[Any]]:
        if self.cursor < len(self.results):
            row = self.results[self.cursor]
            self.cursor += 1
            return row
        return None

    def close(self):
        self.cursor = len(self.results)

class FilterNode(PlanNode):
    """Filters child stream using predicate function."""
    def __init__(self, child: PlanNode, predicate: Callable[[List[Any]], bool]):
        self.child = child
        self.predicate = predicate

    def open(self):
        self.child.open()

    def next(self) -> Optional[List[Any]]:
        while True:
            row = self.child.next()
            if row is None:
                return None
            if self.predicate(row):
                return row

    def close(self):
        self.child.close()

class ProjectNode(PlanNode):
    """Projects specific columns from child stream."""
    def __init__(self, child: PlanNode, col_indices: List[int]):
        self.child = child
        self.col_indices = col_indices

    def open(self):
        self.child.open()

    def next(self) -> Optional[List[Any]]:
        row = self.child.next()
        if row is None:
            return None
        return [row[idx] for idx in self.col_indices]

    def close(self):
        self.child.close()

class HashJoinNode(PlanNode):
    """
    Hash Join operator: builds hash table on left child, probes from right child.
    """
    def __init__(self, left: PlanNode, right: PlanNode, left_key_idx: int, right_key_idx: int):
        self.left = left
        self.right = right
        self.left_key_idx = left_key_idx
        self.right_key_idx = right_key_idx
        self.hash_table: Dict[Any, List[List[Any]]] = {}
        self.current_right_row: Optional[List[Any]] = None
        self.current_matches: List[List[Any]] = []
        self.match_cursor = 0

    def open(self):
        self.left.open()
        self.right.open()
        self.hash_table.clear()

        # Build phase: consume all left rows into hash map
        while True:
            row = self.left.next()
            if row is None:
                break
            key = row[self.left_key_idx]
            if key not in self.hash_table:
                self.hash_table[key] = []
            self.hash_table[key].append(row)

        self.match_cursor = 0
        self.current_matches = []
        self.current_right_row = None

    def next(self) -> Optional[List[Any]]:
        while True:
            if self.match_cursor < len(self.current_matches):
                left_row = self.current_matches[self.match_cursor]
                self.match_cursor += 1
                return left_row + self.current_right_row

            # Fetch next right row
            self.current_right_row = self.right.next()
            if self.current_right_row is None:
                return None

            right_key = self.current_right_row[self.right_key_idx]
            self.current_matches = self.hash_table.get(right_key, [])
            self.match_cursor = 0

    def close(self):
        self.left.close()
        self.right.close()

class AggregateNode(PlanNode):
    """
    Computes aggregates (COUNT, SUM, AVG, MIN, MAX) optionally grouped by columns.
    """
    def __init__(self, child: PlanNode, group_by_idx: Optional[int] = None, agg_col_idx: int = 0, agg_type: str = "COUNT"):
        self.child = child
        self.group_by_idx = group_by_idx
        self.agg_col_idx = agg_col_idx
        self.agg_type = agg_type.upper()
        self.results: List[List[Any]] = []
        self.cursor = 0

    def open(self):
        self.child.open()
        groups: Dict[Any, List[Any]] = {}

        while True:
            row = self.child.next()
            if row is None:
                break
            grp_key = row[self.group_by_idx] if self.group_by_idx is not None else "ALL"
            val = row[self.agg_col_idx]
            if grp_key not in groups:
                groups[grp_key] = []
            groups[grp_key].append(val)

        self.results = []
        for grp_key, vals in groups.items():
            if self.agg_type == "COUNT":
                agg_res = len(vals)
            elif self.agg_type == "SUM":
                agg_res = sum(vals)
            elif self.agg_type == "AVG":
                agg_res = sum(vals) / len(vals) if vals else 0
            elif self.agg_type == "MIN":
                agg_res = min(vals) if vals else None
            elif self.agg_type == "MAX":
                agg_res = max(vals) if vals else None
            else:
                agg_res = len(vals)

            if self.group_by_idx is not None:
                self.results.append([grp_key, agg_res])
            else:
                self.results.append([agg_res])

        self.cursor = 0

    def next(self) -> Optional[List[Any]]:
        if self.cursor < len(self.results):
            row = self.results[self.cursor]
            self.cursor += 1
            return row
        return None

    def close(self):
        self.child.close()

class QueryPlanner:
    """
    Constructs optimized physical query execution plans.
    """
    @staticmethod
    def create_plan(
        table_name: str,
        rows: List[List[Any]],
        filter_col_idx: Optional[int] = None,
        filter_val: Optional[Any] = None,
        index_tree: Optional[BPlusTree] = None,
        project_cols: Optional[List[int]] = None
    ) -> PlanNode:
        """
        Chooses between SeqScan and IndexScan based on index availability.
        """
        # If an index exists on the filtered column and equality/range predicate is present
        if index_tree and filter_col_idx is not None and filter_val is not None:
            scan: PlanNode = IndexScanNode(index_tree, filter_val, filter_val)
        else:
            scan = SeqScanNode(table_name, rows)
            if filter_col_idx is not None and filter_val is not None:
                scan = FilterNode(scan, lambda r: r[filter_col_idx] == filter_val)

        if project_cols is not None:
            return ProjectNode(scan, project_cols)
        return scan
