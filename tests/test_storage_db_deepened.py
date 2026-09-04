#!/usr/bin/env python3
"""
AdiOS Test Suite: Deepened Storage, B+ Tree & Relational Query Planner (Subsystem 49)
Verifies:
1. FAT32 multi-cluster file creation, cluster allocation, directory traversal, and formatting.
2. Ext2 inode bitmap allocation, block allocation, direct and indirect block writes.
3. B+ Tree node splitting, underflow borrowing, sibling merging, and bidirectional range scans.
4. Relational Query Planner Volcano iterators (SeqScan, Filter, Sort, LimitOffset, Explain).
5. SovereignSQL ACID transactions, nested savepoints, B+ Tree index acceleration, and WAL recovery.
Zero external dependencies. STRICT ZERO EMOJI POLICY.
"""

import unittest
from vfs.fat32 import FAT32Driver
from vfs.ext2_deep import DeepExt2Driver
from db.bplus_tree import BPlusTree
from db.query_planner import (
    SeqScanNode, FilterNode, SortNode, LimitOffsetNode, QueryPlanner
)
from db.engine import SovereignDB


class TestDeepenedStorageAndDB(unittest.TestCase):

    def test_fat32_driver_end_to_end(self):
        # Format a 4MB FAT32 disk image
        fs = FAT32Driver.create_formatted_disk(size_mb=4, volume_label="ADIOS_TEST")
        root_entries = fs.list_root_directory()
        self.assertEqual(len(root_entries), 0)

        # Write small file (single cluster)
        fs.write_file("HELLO.TXT", b"AdiOS Sovereign Workstation")
        content = fs.read_file("HELLO.TXT")
        self.assertEqual(content, b"AdiOS Sovereign Workstation")

        # Write large multi-cluster file (spanning across multiple 4KB clusters)
        large_payload = b"CLUSTER_DATA_" * 1000 # 13,000 bytes > 3 clusters
        fs.write_file("LARGE.DAT", large_payload)
        read_large = fs.read_file("LARGE.DAT")
        self.assertEqual(read_large, large_payload)

        # Create subdirectory and navigate
        sub_c = fs.mkdir("SYSTEM")
        self.assertGreaterEqual(sub_c, 2)
        fs.write_file("CONFIG.SYS", b"FILES=64\nBUFFERS=32", dir_cluster=sub_c)
        sub_content = fs.read_file("CONFIG.SYS", dir_cluster=sub_c)
        self.assertEqual(sub_content, b"FILES=64\nBUFFERS=32")

        # Delete file and verify absence
        fs.delete_file("HELLO.TXT")
        with self.assertRaises(FileNotFoundError):
            fs.read_file("HELLO.TXT")

    def test_ext2_deepened_driver(self):
        # Format a 2MB Ext2 disk image
        fs = DeepExt2Driver.create_formatted_image(size_blocks=2048, block_size=1024)
        self.assertEqual(fs.sb.s_magic, 0xEF53)

        # Create file and write payload requiring direct blocks
        fs.create_file("/kernel.bin", b"\x7FELF_MOCK_KERNEL_PAYLOAD")
        data = fs.read_file("/kernel.bin")
        self.assertEqual(data, b"\x7FELF_MOCK_KERNEL_PAYLOAD")

        # Write file requiring single indirect blocks (> 12 blocks * 1024 = 12KB)
        large_fs_data = b"EXT2_BLOCK_CHUNK_" * 1000 # 17,000 bytes > 16 blocks
        fs.create_file("/driver.dat", large_fs_data)
        read_back = fs.read_file("/driver.dat")
        self.assertEqual(read_back, large_fs_data)

    def test_bplus_tree_underflow_and_range_scans(self):
        tree = BPlusTree(order=4)

        # Insert sequential and random keys
        keys = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 25, 35, 45]
        for k in keys:
            tree.insert(k, f"val_{k}")

        self.assertEqual(len(tree), len(keys))
        for k in keys:
            self.assertEqual(tree.search(k), f"val_{k}")

        # Test ascending range query
        range_pairs = tree.range_search(25, 65)
        range_keys = [p[0] for p in range_pairs]
        self.assertEqual(range_keys, [25, 30, 35, 40, 45, 50, 60])

        # Test descending range query
        desc_pairs = tree.range_search_descending(25, 65)
        desc_keys = [p[0] for p in desc_pairs]
        self.assertEqual(desc_keys, [60, 50, 45, 40, 35, 30, 25])

        # Test deletions and underflow rebalancing
        for k in [40, 50, 60, 70]:
            deleted = tree.delete(k)
            self.assertTrue(deleted)
            self.assertIsNone(tree.search(k))

        # Remaining keys must still be intact and queryable
        for k in [10, 20, 25, 30, 35, 45, 80, 90, 100]:
            self.assertEqual(tree.search(k), f"val_{k}")

    def test_query_planner_volcano_operators(self):
        # Create dataset
        data = [
            [1, "Alice", 95000, "Engineering"],
            [2, "Bob", 62000, "Support"],
            [3, "Charlie", 120000, "Engineering"],
            [4, "Diana", 88000, "Design"],
            [5, "Evan", 74000, "Support"],
            [6, "Fiona", 110000, "Engineering"],
        ]

        # Scan -> Filter (Salary > 80000) -> Sort (Salary DESC) -> Limit (2)
        scan = SeqScanNode("employees", data)
        filt = FilterNode(scan, lambda r: r[2] > 80000, "salary > 80000")
        sort = SortNode(filt, [(2, False)]) # col 2 DESC
        lim = LimitOffsetNode(sort, limit=2, offset=0)

        lim.open()
        res = []
        while True:
            row = lim.next()
            if row is None:
                break
            res.append(row)
        lim.close()

        self.assertEqual(len(res), 2)
        self.assertEqual(res[0][1], "Charlie") # 120000
        self.assertEqual(res[1][1], "Fiona")   # 110000

        # Verify EXPLAIN visualization
        explain_lines = lim.explain(0)
        explain_str = "\n".join(explain_lines)
        self.assertIn("LimitOffset", explain_str)
        self.assertIn("Sort", explain_str)
        self.assertIn("Filter", explain_str)
        self.assertIn("SeqScan on 'employees'", explain_str)

    def test_sovereigndb_acid_transactions_and_savepoints(self):
        db = SovereignDB()
        db.execute("CREATE TABLE accounts (id INT PRIMARY KEY, owner VARCHAR, balance FLOAT)")
        db.execute("INSERT INTO accounts VALUES (101, 'Ada Lovelace', 1500.0)")
        db.execute("INSERT INTO accounts VALUES (102, 'Alan Turing', 2200.0)")

        # Create B+ Tree index
        db.execute("CREATE INDEX idx_balance ON accounts (balance)")

        # Fast lookup via index
        q1 = db.execute("SELECT owner, balance FROM accounts WHERE balance = 2200.0")
        self.assertEqual(q1["count"], 1)
        self.assertEqual(q1["rows"][0][0], "Alan Turing")

        # Test Transaction and Savepoint Rollback
        db.execute("BEGIN")
        db.execute("UPDATE accounts SET balance = 3000.0 WHERE id = 101")
        db.execute("SAVEPOINT sp_before_bad_op")
        db.execute("UPDATE accounts SET balance = 0.0 WHERE id = 102")

        # Verify interim state
        q_interim = db.execute("SELECT balance FROM accounts WHERE id = 102")
        self.assertEqual(q_interim["rows"][0][0], 0.0)

        # Rollback to savepoint
        db.execute("ROLLBACK TO SAVEPOINT sp_before_bad_op")
        q_after_sp = db.execute("SELECT balance FROM accounts WHERE id = 102")
        self.assertEqual(q_after_sp["rows"][0][0], 2200.0)

        # Commit remaining transaction
        db.execute("COMMIT")
        q_final = db.execute("SELECT balance FROM accounts WHERE id = 101")
        self.assertEqual(q_final["rows"][0][0], 3000.0)

        # Test WAL Recovery
        wal_log = [
            "CREATE TABLE audits (id INT PRIMARY KEY, note VARCHAR)",
            "INSERT INTO audits VALUES (1, 'System Boot Verified')",
            "INSERT INTO audits VALUES (2, 'Storage Subsystem Initialized')"
        ]
        db.recover_from_wal(wal_log)
        q_audit = db.execute("SELECT note FROM audits WHERE id = 2")
        self.assertEqual(q_audit["rows"][0][0], "Storage Subsystem Initialized")


if __name__ == "__main__":
    unittest.main()
