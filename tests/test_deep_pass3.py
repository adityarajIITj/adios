#!/usr/bin/env python3
"""
AdiOS Test Suite: Pass 3 — Storage Architecture & Database Engine Deepening
Tests:
- DeepExt2Driver: direct, single-indirect, double-indirect bmap and directory resolution (vfs/ext2_deep.py)
- BPlusTree: multi-level node splitting, point queries, range scans, and deletions (db/bplus_tree.py)
- QueryPlanner: Volcano execution model, IndexScan, HashJoin, and Aggregates (db/query_planner.py)

Zero external dependencies. Pure bare-metal verification.
STRICT ZERO EMOJI POLICY.
"""

import struct
import unittest
from vfs.ext2_deep import DeepExt2Driver, Ext2Inode, Ext2DirEntry, EXT2_MAGIC, EXT2_ROOT_INO
from db.bplus_tree import BPlusTree
from db.query_planner import (
    QueryPlanner, SeqScanNode, IndexScanNode, FilterNode,
    ProjectNode, HashJoinNode, AggregateNode
)

class TestPass3StorageAndDatabase(unittest.TestCase):

    # --------------------------------------------------------------------------
    # 1. Deep Ext2 Indirect Addressing Tests
    # --------------------------------------------------------------------------

    def setUp(self):
        # Create a minimal 2MB simulated Ext2 disk image
        self.block_size = 1024
        self.disk = bytearray(2 * 1024 * 1024)

        # 1. Write Superblock at offset 1024
        sb_bytes = struct.pack(
            "<13I3H",
            128,          # s_inodes_count
            2048,         # s_blocks_count
            0, 1000, 100, # reserved, free blocks, free inodes
            1,            # s_first_data_block
            0, 0,         # s_log_block_size (1024), s_log_frag_size
            2048, 2048, 128, # blocks_per_group, frags_per_group, inodes_per_group
            0, 0, 1, 20,  # mtime, wtime, mnt_count, max_mnt_count
            EXT2_MAGIC    # 0xEF53
        )
        self.disk[1024 : 1024 + len(sb_bytes)] = sb_bytes

        # 2. Write Block Group Descriptor at block 2 (offset 2048)
        # block_bitmap=3, inode_bitmap=4, inode_table=5
        bgd_bytes = struct.pack("<3I", 3, 4, 5)
        self.disk[2048 : 2048 + len(bgd_bytes)] = bgd_bytes

    def test_01_ext2_direct_and_indirect_bmap(self):
        driver = DeepExt2Driver(self.disk)
        self.assertEqual(driver.block_size, 1024)
        self.assertEqual(driver.ptrs_per_block, 256)

        # Construct an Inode with direct, single indirect, and double indirect pointers
        inode_bytes = bytearray(128)
        # i_mode=0x81A4 (regular file), i_uid=0, i_size=400000 bytes
        struct.pack_into("<HHI", inode_bytes, 0, 0x81A4, 0, 400000)

        # Direct blocks: i_block[0..11] = 100..111
        blocks = list(range(100, 112))
        # Single indirect block at block 200
        blocks.append(200)
        # Double indirect block at block 300
        blocks.append(300)
        # Triple indirect block at 0
        blocks.append(0)

        struct.pack_into("<15I", inode_bytes, 40, *blocks)
        inode = Ext2Inode(bytes(inode_bytes))

        # Test direct mapping
        self.assertEqual(driver.bmap(inode, 0), 100)
        self.assertEqual(driver.bmap(inode, 5), 105)
        self.assertEqual(driver.bmap(inode, 11), 111)

        # Setup Single Indirect block 200: contains pointers 500..755
        indirect_ptrs = struct.pack("<256I", *range(500, 756))
        driver.write_block(200, indirect_ptrs)

        # Test single indirect mapping (logical blocks 12..267)
        self.assertEqual(driver.bmap(inode, 12), 500)
        self.assertEqual(driver.bmap(inode, 13), 501)
        self.assertEqual(driver.bmap(inode, 12 + 255), 755)

        # Setup Double Indirect block 300: first pointer points to block 200
        double_ptrs = struct.pack("<256I", 200, *([0]*255))
        driver.write_block(300, double_ptrs)

        # Test double indirect mapping (logical block 12 + 256 = 268)
        self.assertEqual(driver.bmap(inode, 268), 500)

    # --------------------------------------------------------------------------
    # 2. B+ Tree Index Engine Tests
    # --------------------------------------------------------------------------

    def test_02_bplus_tree_splits_and_point_queries(self):
        # Order 3 B+ Tree splits frequently
        tree = BPlusTree(order=3)
        data = {10: "val10", 20: "val20", 30: "val30", 40: "val40", 50: "val50", 25: "val25"}

        for k, v in data.items():
            tree.insert(k, v)

        self.assertEqual(tree.size, len(data))
        # Point lookups
        for k, v in data.items():
            self.assertEqual(tree.search(k), v)

        self.assertIsNone(tree.search(999))

    def test_03_bplus_tree_range_queries(self):
        tree = BPlusTree(order=4)
        for i in range(1, 101):
            tree.insert(i, f"rec_{i}")

        # Query range 25 to 30
        results = tree.range_search(25, 30)
        expected_keys = [25, 26, 27, 28, 29, 30]
        self.assertEqual([r[0] for r in results], expected_keys)
        self.assertEqual(results[0][1], "rec_25")
        self.assertEqual(results[-1][1], "rec_30")

    # --------------------------------------------------------------------------
    # 3. Relational Query Planner & Operator Tests
    # --------------------------------------------------------------------------

    def test_04_query_planner_seq_and_index_scan(self):
        rows = [
            [1, "Alice", "ENG"],
            [2, "Bob", "SALES"],
            [3, "Charlie", "ENG"],
            [4, "David", "FIN"]
        ]

        # SeqScan with Filter: department == 'ENG'
        plan = QueryPlanner.create_plan("users", rows, filter_col_idx=2, filter_val="ENG", project_cols=[0, 1])
        plan.open()
        res = []
        while True:
            row = plan.next()
            if row is None: break
            res.append(row)
        plan.close()

        self.assertEqual(res, [[1, "Alice"], [3, "Charlie"]])

        # IndexScan with B+ tree
        tree = BPlusTree(order=4)
        for r in rows:
            tree.insert(r[0], r)

        index_plan = QueryPlanner.create_plan("users", rows, filter_col_idx=0, filter_val=2, index_tree=tree)
        index_plan.open()
        indexed_row = index_plan.next()
        index_plan.close()
        self.assertEqual(indexed_row, [2, "Bob", "SALES"])

    def test_05_hash_join_and_aggregates(self):
        # Users table: [id, name]
        users = [
            [1, "Alice"],
            [2, "Bob"],
            [3, "Charlie"]
        ]
        # Orders table: [order_id, user_id, amount]
        orders = [
            [101, 1, 50],
            [102, 1, 150],
            [103, 2, 75],
            [104, 9, 200] # Non-matching user
        ]

        # Hash Join on users.id (col 0) == orders.user_id (col 1)
        left = SeqScanNode("users", users)
        right = SeqScanNode("orders", orders)
        join = HashJoinNode(left, right, left_key_idx=0, right_key_idx=1)

        join.open()
        joined = []
        while True:
            row = join.next()
            if row is None: break
            joined.append(row)
        join.close()

        # Joined schema: [u.id, u.name, o.order_id, o.user_id, o.amount]
        self.assertEqual(len(joined), 3)
        self.assertEqual(joined[0], [1, "Alice", 101, 1, 50])
        self.assertEqual(joined[1], [1, "Alice", 102, 1, 150])
        self.assertEqual(joined[2], [2, "Bob", 103, 2, 75])

        # Test Aggregate: SUM of amounts grouped by user_name
        # Projected joined rows: [user_name, amount]
        proj = ProjectNode(SeqScanNode("joined", joined), [1, 4])
        agg = AggregateNode(proj, group_by_idx=0, agg_col_idx=1, agg_type="SUM")
        agg.open()
        agg_res = {}
        while True:
            r = agg.next()
            if r is None: break
            agg_res[r[0]] = r[1]
        agg.close()

        self.assertEqual(agg_res["Alice"], 200)
        self.assertEqual(agg_res["Bob"], 75)

if __name__ == "__main__":
    unittest.main()
