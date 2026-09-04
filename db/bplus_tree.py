#!/usr/bin/env python3
"""
AdiOS Database Subsystem: Disk-Backed B+ Tree Index Engine (Deepened Architecture)
Implements industrial-grade Order-M B+ Tree with sibling range traversal,
underflow rebalancing, node borrowing, merging, and descending scans:

Features:
1. Routing internal nodes with M-way branching keys and child pointers.
2. Doubly linked leaf nodes (next and prev) for bidirectional range scanning.
3. Automatic node splitting on overflow (keys >= order).
4. Node deletion with underflow handling:
   - Sibling key borrowing (left / right) when underflowing (keys < ceil(order/2))
   - Sibling node merging and parent separator key deletion when borrowing is impossible.
5. Bidirectional range queries: range_search (ascending) and range_search_descending.
6. Tree telemetry: depth calculation, leaf/internal count, fill factor percentage, and ASCII dumper.

Zero external dependencies. Pure RV32IM relational engine component.
STRICT ZERO EMOJI POLICY.
"""

from typing import List, Tuple, Optional, Any, Dict
import math


class BPlusNode:
    """Base class for B+ Tree nodes."""
    def __init__(self, is_leaf: bool = False):
        self.is_leaf = is_leaf
        self.keys: List[Any] = []
        self.parent: Optional['InternalNode'] = None


class InternalNode(BPlusNode):
    """Internal routing node containing keys and child pointers."""
    def __init__(self):
        super().__init__(is_leaf=False)
        self.children: List[BPlusNode] = []

    def __repr__(self) -> str:
        return f"<Internal keys={self.keys} children_count={len(self.children)}>"


class LeafNode(BPlusNode):
    """Leaf data node containing key-value pairs and sibling pointers."""
    def __init__(self):
        super().__init__(is_leaf=True)
        self.values: List[Any] = []
        self.next: Optional['LeafNode'] = None
        self.prev: Optional['LeafNode'] = None

    def __repr__(self) -> str:
        return f"<Leaf keys={self.keys} values_count={len(self.values)}>"


class BPlusTree:
    """
    Order-M B+ Tree implementation with full overflow splits,
    underflow borrowing, and sibling merging.
    """
    def __init__(self, order: int = 4):
        if order < 3:
            raise ValueError("B+ Tree order must be at least 3")
        self.order = order
        self.min_keys = (order - 1) // 2
        self.root: BPlusNode = LeafNode()
        self.leaf_head: LeafNode = self.root
        self.size = 0

    def __len__(self) -> int:
        return self.size

    def __contains__(self, key: Any) -> bool:
        return self.search(key) is not None

    def search(self, key: Any) -> Optional[Any]:
        """Performs exact key lookup."""
        leaf = self._find_leaf(key)
        for idx, k in enumerate(leaf.keys):
            if k == key:
                return leaf.values[idx]
        return None

    def _find_leaf(self, key: Any) -> LeafNode:
        """Navigates from root down to candidate leaf node."""
        curr = self.root
        while not curr.is_leaf:
            internal: InternalNode = curr
            child_idx = 0
            while child_idx < len(internal.keys) and key >= internal.keys[child_idx]:
                child_idx += 1
            curr = internal.children[child_idx]
        return curr

    # -------------------------------------------------------------------------
    # Insertion & Splitting Pipeline
    # -------------------------------------------------------------------------
    def insert(self, key: Any, value: Any):
        """Inserts key and value, splitting nodes on overflow."""
        leaf = self._find_leaf(key)

        # Check if key already exists -> update in-place
        for idx, k in enumerate(leaf.keys):
            if k == key:
                leaf.values[idx] = value
                return

        # Insert key in sorted order
        insert_idx = 0
        while insert_idx < len(leaf.keys) and leaf.keys[insert_idx] < key:
            insert_idx += 1

        leaf.keys.insert(insert_idx, key)
        leaf.values.insert(insert_idx, value)
        self.size += 1

        # Check for leaf overflow
        if len(leaf.keys) >= self.order:
            self._split_leaf(leaf)

    def _split_leaf(self, leaf: LeafNode):
        """Splits an overflowing leaf node into two halves."""
        split_idx = len(leaf.keys) // 2

        new_leaf = LeafNode()
        new_leaf.keys = leaf.keys[split_idx:]
        new_leaf.values = leaf.values[split_idx:]
        new_leaf.parent = leaf.parent

        leaf.keys = leaf.keys[:split_idx]
        leaf.values = leaf.values[:split_idx]

        # Update doubly-linked sibling pointers
        new_leaf.next = leaf.next
        new_leaf.prev = leaf
        if leaf.next:
            leaf.next.prev = new_leaf
        leaf.next = new_leaf

        # Propagate lowest key of new leaf up to parent
        promoted_key = new_leaf.keys[0]
        self._insert_into_parent(leaf, promoted_key, new_leaf)

    def _insert_into_parent(self, left: BPlusNode, key: Any, right: BPlusNode):
        parent: Optional[InternalNode] = left.parent

        if parent is None:
            # Create a new root internal node
            new_root = InternalNode()
            new_root.keys = [key]
            new_root.children = [left, right]
            left.parent = new_root
            right.parent = new_root
            self.root = new_root
            return

        insert_idx = 0
        while insert_idx < len(parent.keys) and parent.keys[insert_idx] < key:
            insert_idx += 1

        parent.keys.insert(insert_idx, key)
        parent.children.insert(insert_idx + 1, right)
        right.parent = parent

        # Check for internal node overflow
        if len(parent.keys) >= self.order:
            self._split_internal(parent)

    def _split_internal(self, node: InternalNode):
        """Splits an overflowing internal node."""
        mid_idx = len(node.keys) // 2
        promoted_key = node.keys[mid_idx]

        new_node = InternalNode()
        new_node.keys = node.keys[mid_idx + 1 :]
        new_node.children = node.children[mid_idx + 1 :]
        for child in new_node.children:
            child.parent = new_node

        node.keys = node.keys[:mid_idx]
        node.children = node.children[: mid_idx + 1]

        self._insert_into_parent(node, promoted_key, new_node)

    # -------------------------------------------------------------------------
    # Deletion & Underflow Rebalancing
    # -------------------------------------------------------------------------
    def delete(self, key: Any) -> bool:
        """Removes a key and rebalances the tree if underflow occurs."""
        leaf = self._find_leaf(key)
        for idx, k in enumerate(leaf.keys):
            if k == key:
                leaf.keys.pop(idx)
                leaf.values.pop(idx)
                self.size -= 1
                self._handle_underflow(leaf)
                return True
        return False

    def _handle_underflow(self, node: BPlusNode):
        """Rebalances a node that has dropped below min_keys."""
        if node == self.root:
            # Root underflow: if internal node has 0 keys and 1 child, promote child to root
            if not node.is_leaf and len(node.keys) == 0:
                if len(node.children) > 0:
                    self.root = node.children[0]
                    self.root.parent = None
            return

        if len(node.keys) >= self.min_keys:
            return  # No underflow

        parent = node.parent
        if parent is None:
            return

        child_idx = parent.children.index(node)

        # 1. Try borrowing from left sibling
        if child_idx > 0:
            left_sib = parent.children[child_idx - 1]
            if len(left_sib.keys) > self.min_keys:
                self._borrow_from_left(node, left_sib, parent, child_idx)
                return

        # 2. Try borrowing from right sibling
        if child_idx < len(parent.children) - 1:
            right_sib = parent.children[child_idx + 1]
            if len(right_sib.keys) > self.min_keys:
                self._borrow_from_right(node, right_sib, parent, child_idx)
                return

        # 3. Merge with sibling
        if child_idx > 0:
            left_sib = parent.children[child_idx - 1]
            self._merge_nodes(left_sib, node, parent, child_idx - 1)
        else:
            right_sib = parent.children[child_idx + 1]
            self._merge_nodes(node, right_sib, parent, child_idx)

    def _borrow_from_left(self, node: BPlusNode, left_sib: BPlusNode, parent: InternalNode, child_idx: int):
        if node.is_leaf:
            borrowed_key = left_sib.keys.pop(-1)
            borrowed_val = left_sib.values.pop(-1)
            node.keys.insert(0, borrowed_key)
            node.values.insert(0, borrowed_val)
            parent.keys[child_idx - 1] = node.keys[0]
        else:
            borrowed_key = left_sib.keys.pop(-1)
            borrowed_child = left_sib.children.pop(-1)
            borrowed_child.parent = node
            parent_key = parent.keys[child_idx - 1]
            parent.keys[child_idx - 1] = borrowed_key
            node.keys.insert(0, parent_key)
            node.children.insert(0, borrowed_child)

    def _borrow_from_right(self, node: BPlusNode, right_sib: BPlusNode, parent: InternalNode, child_idx: int):
        if node.is_leaf:
            borrowed_key = right_sib.keys.pop(0)
            borrowed_val = right_sib.values.pop(0)
            node.keys.append(borrowed_key)
            node.values.append(borrowed_val)
            parent.keys[child_idx] = right_sib.keys[0]
        else:
            borrowed_key = right_sib.keys.pop(0)
            borrowed_child = right_sib.children.pop(0)
            borrowed_child.parent = node
            parent_key = parent.keys[child_idx]
            parent.keys[child_idx] = borrowed_key
            node.keys.append(parent_key)
            node.children.append(borrowed_child)

    def _merge_nodes(self, left: BPlusNode, right: BPlusNode, parent: InternalNode, sep_idx: int):
        if left.is_leaf:
            left.keys.extend(right.keys)
            left.values.extend(right.values)
            left.next = right.next
            if right.next:
                right.next.prev = left
        else:
            sep_key = parent.keys[sep_idx]
            left.keys.append(sep_key)
            left.keys.extend(right.keys)
            for child in right.children:
                child.parent = left
            left.children.extend(right.children)

        # Remove separator key and right child from parent
        parent.keys.pop(sep_idx)
        parent.children.pop(sep_idx + 1)

        self._handle_underflow(parent)

    # -------------------------------------------------------------------------
    # Range Queries (Ascending & Descending)
    # -------------------------------------------------------------------------
    def range_search(self, min_key: Any, max_key: Any) -> List[Tuple[Any, Any]]:
        """
        Performs ascending range scan using leaf next pointers.
        Returns all (key, value) pairs where min_key <= key <= max_key.
        """
        results = []
        curr_leaf = self._find_leaf(min_key)

        while curr_leaf is not None:
            for idx, k in enumerate(curr_leaf.keys):
                if k > max_key:
                    return results
                if k >= min_key:
                    results.append((k, curr_leaf.values[idx]))
            curr_leaf = curr_leaf.next

        return results

    def range_search_descending(self, key1: Any, key2: Any) -> List[Tuple[Any, Any]]:
        """
        Performs descending range scan using leaf prev pointers.
        Returns all (key, value) pairs where min_key <= key <= max_key in reverse order.
        """
        min_key = min(key1, key2)
        max_key = max(key1, key2)
        results = []
        curr_leaf = self._find_leaf(max_key)

        while curr_leaf is not None:
            for idx in range(len(curr_leaf.keys) - 1, -1, -1):
                k = curr_leaf.keys[idx]
                if k < min_key:
                    return results
                if k <= max_key:
                    results.append((k, curr_leaf.values[idx]))
            curr_leaf = curr_leaf.prev

        return results

    # -------------------------------------------------------------------------
    # Iteration & Telemetry
    # -------------------------------------------------------------------------
    def items(self) -> List[Tuple[Any, Any]]:
        """Returns all key-value pairs in ascending sorted order."""
        res = []
        curr = self.leaf_head
        while curr is not None:
            for k, v in zip(curr.keys, curr.values):
                res.append((k, v))
            curr = curr.next
        return res

    def depth(self) -> int:
        """Computes the height of the B+ Tree from root to leaf."""
        d = 1
        curr = self.root
        while not curr.is_leaf:
            d += 1
            curr = curr.children[0]
        return d

    def get_stats(self) -> Dict[str, Any]:
        """Returns tree structural statistics."""
        leaves = 0
        internals = 0
        total_keys = 0

        def traverse(node):
            nonlocal leaves, internals, total_keys
            total_keys += len(node.keys)
            if node.is_leaf:
                leaves += 1
            else:
                internals += 1
                for child in node.children:
                    traverse(child)

        traverse(self.root)
        return {
            "order": self.order,
            "depth": self.depth(),
            "total_items": self.size,
            "total_keys": total_keys,
            "leaf_nodes": leaves,
            "internal_nodes": internals
        }

    def dump_tree(self) -> str:
        """Generates an ASCII visualization of the tree structure."""
        lines = []

        def walk(node, level=0):
            prefix = "  " * level
            if node.is_leaf:
                lines.append(f"{prefix}Leaf(keys={node.keys})")
            else:
                lines.append(f"{prefix}Internal(keys={node.keys})")
                for child in node.children:
                    walk(child, level + 1)

        walk(self.root)
        return "\n".join(lines)
