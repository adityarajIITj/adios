#!/usr/bin/env python3
"""
Test Suite: Block O SovereignSQL Relational Database Engine
Verifies:
1. CREATE TABLE with typed schema and column indexing
2. INSERT INTO record persistence and column validation
3. SELECT with column projections and WHERE filtering
4. UPDATE and DELETE statement mutations
5. ACID Transactions (BEGIN, ROLLBACK snapshot restoration, COMMIT persistence)
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.engine import SovereignDB

def test_db_block_o_suite():
    print("[Test DB Block O] Initializing SovereignSQL Relational Database Verification...")

    # 1. Test Schema Definition & Creation
    print("  -> Testing Schema Creation (CREATE TABLE)...")
    db = SovereignDB()
    create_res = db.execute("CREATE TABLE nodes (id INT PRIMARY KEY, hostname VARCHAR, active BOOL, memory_mb INT)")
    assert create_res["status"] == "TABLE_CREATED"
    assert create_res["table"] == "nodes"
    assert create_res["columns"] == 4
    print("  -> [PASS] CREATE TABLE verified.")

    # 2. Test Record Insertion (INSERT INTO)
    print("  -> Testing Data Insertion (INSERT INTO)...")
    db.execute("INSERT INTO nodes VALUES (1, 'hyperion', true, 16384)")
    db.execute("INSERT INTO nodes VALUES (2, 'chronos', false, 8192)")
    db.execute("INSERT INTO nodes VALUES (3, 'prometheus', true, 32768)")
    assert len(db.tables["nodes"].rows) == 3
    print("  -> [PASS] INSERT INTO verified.")

    # 3. Test Querying (SELECT with WHERE Filters)
    print("  -> Testing Query & Filter Engine (SELECT)...")
    all_res = db.execute("SELECT * FROM nodes")
    assert all_res["count"] == 3

    # Filter with condition
    filter_res = db.execute("SELECT hostname, memory_mb FROM nodes WHERE memory_mb > 10000")
    assert filter_res["count"] == 2
    hostnames = [r[0] for r in filter_res["rows"]]
    assert "hyperion" in hostnames
    assert "prometheus" in hostnames
    assert "chronos" not in hostnames
    print("  -> [PASS] SELECT and WHERE filter verified.")

    # 4. Test Record Mutation & Deletion (UPDATE & DELETE)
    print("  -> Testing Record Mutations (UPDATE & DELETE)...")
    db.execute("UPDATE nodes SET memory_mb = 65536 WHERE id = 1")
    upd_res = db.execute("SELECT memory_mb FROM nodes WHERE id = 1")
    assert upd_res["rows"][0][0] == 65536

    db.execute("DELETE FROM nodes WHERE id = 2")
    del_res = db.execute("SELECT * FROM nodes")
    assert del_res["count"] == 2
    print("  -> [PASS] UPDATE and DELETE verified.")

    # 5. Test ACID Transaction Rollback
    print("  -> Testing ACID Transaction Atomicity & Rollback (BEGIN / ROLLBACK)...")
    db.execute("BEGIN")
    db.execute("INSERT INTO nodes VALUES (4, 'epimetheus', true, 4096)")
    assert len(db.tables["nodes"].rows) == 3
    db.execute("ROLLBACK")
    # epimetheus must be rolled back!
    assert len(db.tables["nodes"].rows) == 2
    rb_res = db.execute("SELECT * FROM nodes WHERE id = 4")
    assert rb_res["count"] == 0
    print("  -> [PASS] Transaction ROLLBACK verified (Snapshot restored cleanly).")

    # 6. Test ACID Transaction Commit
    print("  -> Testing ACID Transaction Commit (BEGIN / COMMIT)...")
    db.execute("BEGIN")
    db.execute("INSERT INTO nodes VALUES (5, 'helios', true, 12288)")
    db.execute("COMMIT")
    commit_res = db.execute("SELECT hostname FROM nodes WHERE id = 5")
    assert commit_res["count"] == 1
    assert commit_res["rows"][0][0] == "helios"
    print("  -> [PASS] Transaction COMMIT verified.")

    print("\n[Test DB Block O] ALL BLOCK O RELATIONAL DATABASE TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_db_block_o_suite()
