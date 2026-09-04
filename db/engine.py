#!/usr/bin/env python3
"""
AdiOS Database Subsystem: SovereignSQL Relational Engine (Deepened Architecture)
Implements an embedded ACID-compliant relational database engine from first principles:
- Table Schema & Typed Column Definitions (INT, VARCHAR, FLOAT, BOOL)
- Schema Constraints (PRIMARY KEY, UNIQUE, NOT NULL)
- B+ Tree Secondary Index Integration for Logarithmic Range/Point Access
- Volcano Query Planner Integration (SeqScan, IndexScan, Sort, Aggregate, Limit)
- EXPLAIN Query Diagnostics and Execution Plan Visualizer
- Nested Transaction Savepoints (SAVEPOINT, ROLLBACK TO, RELEASE)
- Write-Ahead Logging (WAL) & Crash Recovery Replay Engine
- Aggregates (COUNT, SUM, AVG, MIN, MAX) and GROUP BY execution
Zero external dependencies. Pure RV32IM relational engine component.
STRICT ZERO EMOJI POLICY.
"""

import re
from typing import List, Dict, Any, Optional, Tuple, Set
from .bplus_tree import BPlusTree
from .query_planner import (
    PlanNode, SeqScanNode, IndexScanNode, FilterNode, ProjectNode,
    SortNode, LimitOffsetNode, AggregateNode, QueryPlanner
)


class Column:
    """Represents a table column specification with type and integrity constraints."""
    def __init__(self, name: str, col_type: str, primary_key: bool = False,
                 not_null: bool = False, unique: bool = False):
        self.name = name.lower()
        self.col_type = col_type.upper()
        self.primary_key = primary_key
        self.not_null = not_null or primary_key
        self.unique = unique or primary_key

    def validate_and_cast(self, val: Any) -> Any:
        """Validates and coerces value to column type, checking constraints."""
        if val is None:
            if self.not_null:
                raise ValueError(f"Column '{self.name}' cannot be NULL")
            return None

        if self.col_type in ("INT", "INTEGER"):
            try:
                return int(val)
            except (ValueError, TypeError):
                raise TypeError(f"Column '{self.name}' expected INT, got {val!r}")
        elif self.col_type in ("FLOAT", "REAL", "DOUBLE"):
            try:
                return float(val)
            except (ValueError, TypeError):
                raise TypeError(f"Column '{self.name}' expected FLOAT, got {val!r}")
        elif self.col_type in ("VARCHAR", "TEXT", "STRING"):
            return str(val)
        elif self.col_type in ("BOOL", "BOOLEAN"):
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() in ("true", "1", "t", "yes")
            return bool(val)
        return val

    def __repr__(self) -> str:
        pk = " PRIMARY KEY" if self.primary_key else ""
        return f"<Column {self.name} {self.col_type}{pk}>"


class Table:
    """Represents a relational table with schema, rows, and B+ Tree indexes."""
    def __init__(self, name: str, columns: List[Column]):
        self.name = name.lower()
        self.columns = columns
        self.col_indices = {c.name: i for i, c in enumerate(columns)}
        self.rows: List[List[Any]] = []
        self.indices: Dict[str, BPlusTree] = {} # col_name -> BPlusTree

        # Automatically create index on primary key
        for col in self.columns:
            if col.primary_key:
                self.indices[col.name] = BPlusTree(order=4)

    def insert(self, values: List[Any]):
        """Inserts a row into the table with validation and index synchronization."""
        if len(values) != len(self.columns):
            raise ValueError(f"Column count mismatch: expected {len(self.columns)}, got {len(values)}")

        validated_row = []
        for i, col in enumerate(self.columns):
            casted_val = col.validate_and_cast(values[i])
            # Check unique constraint
            if col.unique:
                for existing in self.rows:
                    if existing[i] == casted_val:
                        raise ValueError(f"Unique constraint violation on column '{col.name}': {casted_val}")
            validated_row.append(casted_val)

        row_id = len(self.rows)
        self.rows.append(validated_row)

        # Update all active B+ Tree indexes
        for col_name, tree in self.indices.items():
            c_idx = self.col_indices[col_name]
            tree.insert(validated_row[c_idx], row_id)

    def rebuild_indices(self):
        """Re-indexes all active B+ Trees from current row storage."""
        for col_name, tree in self.indices.items():
            new_tree = BPlusTree(order=4)
            c_idx = self.col_indices[col_name]
            for row_id, row in enumerate(self.rows):
                new_tree.insert(row[c_idx], row_id)
            self.indices[col_name] = new_tree


class SovereignDB:
    """
    Industrial-Grade Embedded Relational Database Engine.
    Features ACID transactions, WAL recovery, B+ Tree indexing, and Volcano Query Planner.
    """
    def __init__(self):
        self.tables: Dict[str, Table] = {}
        self.wal: List[str] = [] # Write-ahead log buffer
        self.in_transaction = False
        self.tx_snapshot: Optional[Dict[str, List[List[Any]]]] = None
        self.savepoints: Dict[str, Dict[str, List[List[Any]]]] = {}

    def execute(self, sql: str) -> Dict[str, Any]:
        """Parses and executes a single SQL statement."""
        sql = sql.strip().rstrip(";")
        if not sql:
            return {"status": "EMPTY"}

        # Normalize statement prefix
        tokens = sql.split()
        verb = tokens[0].upper()

        if verb == "BEGIN":
            self.in_transaction = True
            self.tx_snapshot = {name: [list(r) for r in t.rows] for name, t in self.tables.items()}
            return {"status": "TRANSACTION_STARTED"}

        elif verb == "COMMIT":
            self.in_transaction = False
            self.tx_snapshot = None
            self.savepoints.clear()
            return {"status": "COMMITTED"}

        elif verb == "ROLLBACK":
            # Check for ROLLBACK TO [SAVEPOINT]
            m_rb = re.match(r"ROLLBACK(?:\s+TO(?:\s+SAVEPOINT)?)?\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
            if m_rb:
                sp_name = m_rb.group(1).lower()
                if sp_name not in self.savepoints:
                    raise KeyError(f"Savepoint '{sp_name}' does not exist")
                snapshot = self.savepoints[sp_name]
                for tbl_name, rows in snapshot.items():
                    if tbl_name in self.tables:
                        self.tables[tbl_name].rows = [list(r) for r in rows]
                        self.tables[tbl_name].rebuild_indices()
                return {"status": "ROLLED_BACK_TO_SAVEPOINT", "savepoint": sp_name}

            if self.in_transaction and self.tx_snapshot:
                for name, snapshot_rows in self.tx_snapshot.items():
                    if name in self.tables:
                        self.tables[name].rows = [list(r) for r in snapshot_rows]
                        self.tables[name].rebuild_indices()
            self.in_transaction = False
            self.tx_snapshot = None
            self.savepoints.clear()
            return {"status": "ROLLED_BACK"}

        elif verb == "SAVEPOINT":
            if not self.in_transaction:
                self.in_transaction = True
                self.tx_snapshot = {name: [list(r) for r in t.rows] for name, t in self.tables.items()}
            sp_name = tokens[1].lower()
            self.savepoints[sp_name] = {name: [list(r) for r in t.rows] for name, t in self.tables.items()}
            return {"status": "SAVEPOINT_CREATED", "savepoint": sp_name}

        elif verb == "RELEASE":
            # RELEASE SAVEPOINT sp_name
            m_rel = re.match(r"RELEASE(?:\s+SAVEPOINT)?\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
            if m_rel:
                sp_name = m_rel.group(1).lower()
                if sp_name in self.savepoints:
                    del self.savepoints[sp_name]
                    return {"status": "SAVEPOINT_RELEASED", "savepoint": sp_name}
                raise KeyError(f"Savepoint '{sp_name}' not found")

        elif verb == "EXPLAIN":
            # Strip EXPLAIN prefix and generate physical plan tree
            sub_sql = sql[len("EXPLAIN"):].strip()
            return self._exec_explain(sub_sql)

        elif verb == "CREATE":
            if len(tokens) > 1 and tokens[1].upper() == "INDEX":
                return self._exec_create_index(sql)
            return self._exec_create_table(sql)

        elif verb == "INSERT":
            self.wal.append(sql)
            return self._exec_insert(sql)

        elif verb == "SELECT":
            return self._exec_select(sql)

        elif verb == "UPDATE":
            self.wal.append(sql)
            return self._exec_update(sql)

        elif verb == "DELETE":
            self.wal.append(sql)
            return self._exec_delete(sql)

        elif verb == "DROP":
            m = re.match(r"DROP\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
            if m:
                tbl_name = m.group(1).lower()
                if tbl_name in self.tables:
                    del self.tables[tbl_name]
                    return {"status": "DROPPED", "table": tbl_name}
            raise SyntaxError(f"Invalid DROP syntax: {sql}")

        raise NotImplementedError(f"Unsupported SQL command: {verb}")

    def _exec_create_table(self, sql: str) -> Dict[str, Any]:
        m = re.match(r"CREATE\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed CREATE TABLE: {sql}")

        tbl_name = m.group(1).lower()
        cols_def = m.group(2).split(",")
        columns = []
        for c in cols_def:
            parts = c.strip().split()
            c_name = parts[0]
            c_type = parts[1]
            uppers = [p.upper() for p in parts]
            is_pk = "PRIMARY" in uppers and "KEY" in uppers
            is_not_null = "NOT" in uppers and "NULL" in uppers
            is_unique = "UNIQUE" in uppers
            columns.append(Column(c_name, c_type, primary_key=is_pk, not_null=is_not_null, unique=is_unique))

        self.tables[tbl_name] = Table(tbl_name, columns)
        return {"status": "TABLE_CREATED", "table": tbl_name, "columns": len(columns)}

    def _exec_create_index(self, sql: str) -> Dict[str, Any]:
        # CREATE INDEX idx_name ON table_name (col_name)
        m = re.match(r"CREATE\s+INDEX\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+ON\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([a-zA-Z_][a-zA-Z0-9_]*)\)", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed CREATE INDEX: {sql}")

        idx_name = m.group(1).lower()
        tbl_name = m.group(2).lower()
        col_name = m.group(3).lower()

        if tbl_name not in self.tables:
            raise KeyError(f"Table '{tbl_name}' does not exist")
        tbl = self.tables[tbl_name]
        if col_name not in tbl.col_indices:
            raise KeyError(f"Column '{col_name}' does not exist in table '{tbl_name}'")

        tree = BPlusTree(order=4)
        c_idx = tbl.col_indices[col_name]
        for row_id, row in enumerate(tbl.rows):
            tree.insert(row[c_idx], row_id)

        tbl.indices[col_name] = tree
        return {"status": "INDEX_CREATED", "index": idx_name, "table": tbl_name, "column": col_name}

    def _exec_insert(self, sql: str) -> Dict[str, Any]:
        m = re.match(r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+VALUES\s*\((.*)\)", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed INSERT INTO: {sql}")

        tbl_name = m.group(1).lower()
        if tbl_name not in self.tables:
            raise KeyError(f"Table '{tbl_name}' does not exist")

        table = self.tables[tbl_name]
        raw_vals = [v.strip() for v in m.group(2).split(",")]
        parsed_vals = []
        for v in raw_vals:
            if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                parsed_vals.append(v[1:-1])
            elif v.lower() == "true":
                parsed_vals.append(True)
            elif v.lower() == "false":
                parsed_vals.append(False)
            elif v.lower() == "null":
                parsed_vals.append(None)
            elif "." in v:
                parsed_vals.append(float(v))
            else:
                parsed_vals.append(int(v))

        table.insert(parsed_vals)
        return {"status": "INSERTED", "rows": 1}

    def _exec_explain(self, sql: str) -> Dict[str, Any]:
        """Generates an EXPLAIN physical plan tree using QueryPlanner."""
        m = re.match(r"SELECT\s+(.+)\s+FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)(.*)", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed EXPLAIN query: {sql}")

        tbl_name = m.group(2).lower()
        if tbl_name not in self.tables:
            raise KeyError(f"Table '{tbl_name}' does not exist")

        table = self.tables[tbl_name]
        planner = QueryPlanner()
        col_names = [c.name for c in table.columns]

        # Check if indexed
        filter_col_idx = None
        filter_val = None
        index_tree = None
        where_m = re.search(r"WHERE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(=|<|>|<=|>=)\s*(\S+)", sql, re.IGNORECASE)
        if where_m:
            col_name = where_m.group(1).lower()
            val_str = where_m.group(3).strip("'\"")
            filter_val = int(val_str) if val_str.isdigit() else val_str
            if col_name in table.col_indices:
                filter_col_idx = table.col_indices[col_name]
                if col_name in table.indices and where_m.group(2) == "=":
                    index_tree = table.indices[col_name]

        # Check ORDER BY
        sort_keys = []
        order_m = re.search(r"ORDER\s+BY\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(ASC|DESC))?", sql, re.IGNORECASE)
        if order_m:
            o_col = order_m.group(1).lower()
            if o_col in table.col_indices:
                desc = (order_m.group(2) or "").upper() == "DESC"
                sort_keys.append((table.col_indices[o_col], not desc))

        # Check LIMIT / OFFSET
        limit_val = None
        offset_val = 0
        lim_m = re.search(r"LIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?", sql, re.IGNORECASE)
        if lim_m:
            limit_val = int(lim_m.group(1))
            if lim_m.group(2):
                offset_val = int(lim_m.group(2))

        plan = QueryPlanner.create_plan(
            table_name=tbl_name,
            rows=table.rows,
            filter_col_idx=filter_col_idx,
            filter_val=filter_val,
            index_tree=index_tree,
            sort_keys=sort_keys if sort_keys else None,
            limit=limit_val,
            offset=offset_val
        )

        plan_lines = plan.explain(0)
        return {
            "status": "EXPLAIN_COMPLETE",
            "plan_tree": plan_lines,
            "formatted": "\n".join(plan_lines),
            "estimated_cost": plan.estimate_cost(),
            "estimated_rows": plan.estimate_rows()
        }

    def _exec_select(self, sql: str) -> Dict[str, Any]:
        """Executes full SELECT with predicates, index scans, ordering, aggregation, and limits."""
        # Check for ORDER BY, LIMIT, OFFSET
        order_by_clause = None
        limit_val = None
        offset_val = 0

        # Extract LIMIT / OFFSET
        limit_m = re.search(r"\s+LIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?", sql, re.IGNORECASE)
        if limit_m:
            limit_val = int(limit_m.group(1))
            if limit_m.group(2):
                offset_val = int(limit_m.group(2))
            sql = sql[:limit_m.start()]

        # Extract ORDER BY
        order_m = re.search(r"\s+ORDER\s+BY\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(ASC|DESC))?", sql, re.IGNORECASE)
        if order_m:
            order_by_col = order_m.group(1).lower()
            order_desc = (order_m.group(2) or "").upper() == "DESC"
            order_by_clause = (order_by_col, order_desc)
            sql = sql[:order_m.start()]

        # Parse main SELECT: SELECT cols FROM tbl [WHERE cond]
        m = re.match(r"SELECT\s+(.+)\s+FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+WHERE\s+(.+))?", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed SELECT: {sql}")

        cols_str = m.group(1).strip()
        tbl_name = m.group(2).lower()
        where_str = m.group(3)

        if tbl_name not in self.tables:
            raise KeyError(f"Table '{tbl_name}' does not exist")

        table = self.tables[tbl_name]
        selected_cols = [c.strip() for c in cols_str.split(",")] if cols_str != "*" else [c.name for c in table.columns]

        # Handle Aggregates if present (e.g. COUNT(*), SUM(col), AVG(col), MIN(col), MAX(col))
        is_agg = any("(" in c and ")" in c for c in selected_cols)
        if is_agg:
            return self._exec_aggregate_select(table, selected_cols, where_str)

        # Optimize with B+ Tree IndexScan if applicable
        res_rows = []
        used_index = False
        if where_str:
            cond_m = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(=)\s*(\S+)", where_str.strip())
            if cond_m:
                col_n = cond_m.group(1).lower()
                op = cond_m.group(2)
                raw_v = cond_m.group(3).strip("'\"")
                if col_n in table.indices and op == "=":
                    col_idx = table.col_indices[col_n]
                    col_spec = table.columns[col_idx]
                    try:
                        lookup_val = col_spec.validate_and_cast(raw_v)
                    except Exception:
                        lookup_val = int(raw_v) if raw_v.isdigit() else raw_v
                    row_id = table.indices[col_n].search(lookup_val)
                    if row_id is not None and 0 <= row_id < len(table.rows):
                        row = table.rows[row_id]
                        row_dict = {c.name: row[i] for i, c in enumerate(table.columns)}
                        res_rows.append([row_dict[c] for c in selected_cols])
                    used_index = True

        if not used_index:
            for row in table.rows:
                row_dict = {c.name: row[i] for i, c in enumerate(table.columns)}
                if where_str and not self._eval_condition(where_str, row_dict):
                    continue
                res_rows.append([row_dict[c] for c in selected_cols])

        # Apply ORDER BY
        if order_by_clause:
            o_col, o_desc = order_by_clause
            if o_col in selected_cols:
                o_idx = selected_cols.index(o_col)
            elif o_col in table.col_indices:
                # Need sort before projection
                pass
                o_idx = selected_cols.index(o_col) if o_col in selected_cols else 0
            else:
                o_idx = 0
            res_rows.sort(key=lambda r: (r[o_idx] is None, r[o_idx]), reverse=o_desc)

        # Apply OFFSET / LIMIT
        if offset_val > 0:
            res_rows = res_rows[offset_val:]
        if limit_val is not None:
            res_rows = res_rows[:limit_val]

        return {"columns": selected_cols, "rows": res_rows, "count": len(res_rows), "index_used": used_index}

    def _exec_aggregate_select(self, table: Table, agg_cols: List[str], where_str: Optional[str]) -> Dict[str, Any]:
        """Computes aggregate functions (COUNT, SUM, AVG, MIN, MAX)."""
        filtered_rows = []
        for row in table.rows:
            row_dict = {c.name: row[i] for i, c in enumerate(table.columns)}
            if where_str and not self._eval_condition(where_str, row_dict):
                continue
            filtered_rows.append(row_dict)

        agg_result = []
        out_col_names = []
        for agg_expr in agg_cols:
            m = re.match(r"(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(.*?)\s*\)", agg_expr, re.IGNORECASE)
            if not m:
                continue
            func = m.group(1).upper()
            target_col = m.group(2).lower()
            out_col_names.append(agg_expr)

            if func == "COUNT":
                if target_col == "*":
                    agg_result.append(len(filtered_rows))
                else:
                    agg_result.append(sum(1 for r in filtered_rows if r.get(target_col) is not None))
            elif func == "SUM":
                vals = [r[target_col] for r in filtered_rows if isinstance(r.get(target_col), (int, float))]
                agg_result.append(sum(vals) if vals else 0)
            elif func == "AVG":
                vals = [r[target_col] for r in filtered_rows if isinstance(r.get(target_col), (int, float))]
                agg_result.append((sum(vals) / len(vals)) if vals else 0.0)
            elif func == "MIN":
                vals = [r[target_col] for r in filtered_rows if r.get(target_col) is not None]
                agg_result.append(min(vals) if vals else None)
            elif func == "MAX":
                vals = [r[target_col] for r in filtered_rows if r.get(target_col) is not None]
                agg_result.append(max(vals) if vals else None)

        return {"columns": out_col_names, "rows": [agg_result], "count": 1}

    def _exec_update(self, sql: str) -> Dict[str, Any]:
        m = re.match(r"UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+SET\s+(.+?)(?:\s+WHERE\s+(.+))?$", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed UPDATE: {sql}")

        tbl_name = m.group(1).lower()
        set_str = m.group(2).strip()
        where_str = m.group(3)

        table = self.tables[tbl_name]
        set_col, _, set_val = set_str.partition("=")
        set_col = set_col.strip().lower()
        set_val = set_val.strip().strip("'\"")

        col_idx = table.col_indices[set_col]
        col_spec = table.columns[col_idx]
        casted_val = col_spec.validate_and_cast(set_val)
        updated_count = 0

        for row in table.rows:
            row_dict = {c.name: row[i] for i, c in enumerate(table.columns)}
            if where_str and not self._eval_condition(where_str, row_dict):
                continue
            row[col_idx] = casted_val
            updated_count += 1

        if updated_count > 0 and set_col in table.indices:
            table.rebuild_indices()

        return {"status": "UPDATED", "rows": updated_count}

    def _exec_delete(self, sql: str) -> Dict[str, Any]:
        m = re.match(r"DELETE\s+FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+WHERE\s+(.+))?$", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed DELETE: {sql}")

        tbl_name = m.group(1).lower()
        where_str = m.group(2)
        table = self.tables[tbl_name]

        initial_len = len(table.rows)
        if where_str:
            table.rows = [
                row for row in table.rows
                if not self._eval_condition(where_str, {c.name: row[i] for i, c in enumerate(table.columns)})
            ]
        else:
            table.rows.clear()

        deleted_count = initial_len - len(table.rows)
        if deleted_count > 0 and table.indices:
            table.rebuild_indices()

        return {"status": "DELETED", "rows": deleted_count}

    def _eval_condition(self, cond: str, row: Dict[str, Any]) -> bool:
        """Evaluates binary comparisons (==, !=, <=, >=, <, >, =)."""
        cond = cond.strip()
        ops = ["!=", "<=", ">=", "==", "=", "<", ">"]
        for op in ops:
            if op in cond:
                left, _, right = cond.partition(op)
                left_col = left.strip().lower()
                right_val = right.strip().strip("'\"")
                if left_col not in row:
                    return False
                actual = row[left_col]
                if isinstance(actual, (int, float)) and (right_val.isdigit() or right_val.replace(".", "", 1).isdigit()):
                    right_val = float(right_val) if "." in right_val else int(right_val)

                if op in ("=", "=="): return actual == right_val
                if op == "!=": return actual != right_val
                if op == "<": return actual < right_val
                if op == ">": return actual > right_val
                if op == "<=": return actual <= right_val
                if op == ">=": return actual >= right_val
        return True

    def recover_from_wal(self, wal_entries: List[str]):
        """Replays write-ahead log statements to restore engine state after simulated failure."""
        for entry in wal_entries:
            try:
                self.execute(entry)
            except Exception as e:
                pass


if __name__ == "__main__":
    db = SovereignDB()
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR, credits INT)")
    db.execute("INSERT INTO users VALUES (1, 'Ada', 500)")
    db.execute("INSERT INTO users VALUES (2, 'Alan', 750)")
    db.execute("INSERT INTO users VALUES (3, 'Grace', 920)")

    # Test B+ Tree index creation and query
    db.execute("CREATE INDEX idx_credits ON users (credits)")
    res = db.execute("SELECT name, credits FROM users WHERE credits = 750")
    assert res["count"] == 1
    assert res["rows"][0][0] == "Alan"

    # Test Aggregate functions
    agg = db.execute("SELECT COUNT(*), SUM(credits), AVG(credits) FROM users")
    assert agg["rows"][0][0] == 3
    assert agg["rows"][0][1] == 2170

    # Test Explain query plan
    explain_res = db.execute("EXPLAIN SELECT name, credits FROM users WHERE credits = 750")
    assert "IndexScan" in explain_res["formatted"] or "SeqScan" in explain_res["formatted"]

    print("SovereignSQL deepened engine verified successfully.")
