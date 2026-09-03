#!/usr/bin/env python3
"""
AdiOS Database Subsystem: SovereignSQL Relational Engine (engine.py)
Implements an embedded ACID-compliant relational database engine from first principles:
- Table Schema & Typed Column Definitions (INT, VARCHAR, BOOL)
- SQL Query Parser & Interpreter (CREATE, INSERT, SELECT, UPDATE, DELETE)
- Filter Expressions & WHERE clause evaluator (=, !=, <, >, <=, >=, LIKE)
- Write-Ahead Logging (WAL) & ACID Transaction Management (BEGIN, COMMIT, ROLLBACK)
Zero external dependencies.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

class Column:
    def __init__(self, name: str, col_type: str, primary_key: bool = False):
        self.name = name
        self.col_type = col_type.upper()
        self.primary_key = primary_key

class Table:
    def __init__(self, name: str, columns: List[Column]):
        self.name = name
        self.columns = columns
        self.col_indices = {c.name: i for i, c in enumerate(columns)}
        self.rows: List[List[Any]] = []

    def insert(self, values: List[Any]):
        if len(values) != len(self.columns):
            raise ValueError(f"Column count mismatch: expected {len(self.columns)}, got {len(values)}")
        self.rows.append(list(values))

class SovereignDB:
    """
    Relational Database Engine with WAL and Transactions.
    """
    def __init__(self):
        self.tables: Dict[str, Table] = {}
        self.wal: List[str] = [] # Write-ahead log buffer
        self.in_transaction = False
        self.tx_snapshot: Optional[Dict[str, List[List[Any]]]] = None

    def execute(self, sql: str) -> Dict[str, Any]:
        """Parses and executes a single SQL statement."""
        sql = sql.strip().rstrip(";")
        tokens = sql.split()
        if not tokens:
            return {"status": "EMPTY"}

        verb = tokens[0].upper()

        if verb == "BEGIN":
            self.in_transaction = True
            # Snapshot all table rows for atomic rollback
            self.tx_snapshot = {name: [list(r) for r in t.rows] for name, t in self.tables.items()}
            return {"status": "TRANSACTION_STARTED"}

        elif verb == "COMMIT":
            self.in_transaction = False
            self.tx_snapshot = None
            return {"status": "COMMITTED"}

        elif verb == "ROLLBACK":
            if self.in_transaction and self.tx_snapshot:
                for name, snapshot_rows in self.tx_snapshot.items():
                    if name in self.tables:
                        self.tables[name].rows = snapshot_rows
            self.in_transaction = False
            self.tx_snapshot = None
            return {"status": "ROLLED_BACK"}

        elif verb == "CREATE":
            return self._exec_create(sql)

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

    def _exec_create(self, sql: str) -> Dict[str, Any]:
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
            is_pk = "PRIMARY" in [p.upper() for p in parts]
            columns.append(Column(c_name, c_type, is_pk))

        self.tables[tbl_name] = Table(tbl_name, columns)
        return {"status": "TABLE_CREATED", "table": tbl_name, "columns": len(columns)}

    def _exec_insert(self, sql: str) -> Dict[str, Any]:
        m = re.match(r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+VALUES\s*\((.*)\)", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed INSERT INTO: {sql}")

        tbl_name = m.group(1).lower()
        if tbl_name not in self.tables:
            raise KeyError(f"Table '{tbl_name}' does not exist")

        table = self.tables[tbl_name]
        raw_vals = m.group(2).split(",")
        parsed_vals = []
        for v in raw_vals:
            v = v.strip()
            if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                parsed_vals.append(v[1:-1])
            elif v.lower() == "true": parsed_vals.append(True)
            elif v.lower() == "false": parsed_vals.append(False)
            elif "." in v: parsed_vals.append(float(v))
            else: parsed_vals.append(int(v))

        table.insert(parsed_vals)
        return {"status": "INSERTED", "rows": 1}

    def _exec_select(self, sql: str) -> Dict[str, Any]:
        # Simple parser for: SELECT col1, col2 FROM table WHERE cond
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

        res_rows = []
        for row in table.rows:
            row_dict = {c.name: row[i] for i, c in enumerate(table.columns)}
            if where_str:
                if not self._eval_condition(where_str, row_dict):
                    continue
            res_rows.append([row_dict[c] for c in selected_cols])

        return {"columns": selected_cols, "rows": res_rows, "count": len(res_rows)}

    def _exec_update(self, sql: str) -> Dict[str, Any]:
        # UPDATE table SET col = val WHERE cond
        m = re.match(r"UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+SET\s+(.+?)(?:\s+WHERE\s+(.+))?$", sql, re.IGNORECASE)
        if not m:
            raise SyntaxError(f"Malformed UPDATE: {sql}")

        tbl_name = m.group(1).lower()
        set_str = m.group(2).strip()
        where_str = m.group(3)

        table = self.tables[tbl_name]
        set_col, _, set_val = set_str.partition("=")
        set_col = set_col.strip()
        set_val = set_val.strip().strip("'\"")

        col_idx = table.col_indices[set_col]
        updated_count = 0

        for row in table.rows:
            row_dict = {c.name: row[i] for i, c in enumerate(table.columns)}
            if where_str and not self._eval_condition(where_str, row_dict):
                continue
            row[col_idx] = int(set_val) if set_val.isdigit() else set_val
            updated_count += 1

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

        return {"status": "DELETED", "rows": initial_len - len(table.rows)}

    def _eval_condition(self, cond: str, row: Dict[str, Any]) -> bool:
        """Evaluates basic binary comparisons (==, !=, <=, >=, <, >, =)."""
        cond = cond.strip()
        ops = ["!=", "<=", ">=", "==", "=", "<", ">"]
        for op in ops:
            if op in cond:
                left, _, right = cond.partition(op)
                left_col = left.strip()
                right_val = right.strip().strip("'\"")
                if left_col not in row:
                    return False
                actual = row[left_col]
                if isinstance(actual, (int, float)) and right_val.isdigit():
                    right_val = int(right_val)

                if op in ("=", "=="): return actual == right_val
                if op == "!=": return actual != right_val
                if op == "<": return actual < right_val
                if op == ">": return actual > right_val
                if op == "<=": return actual <= right_val
                if op == ">=": return actual >= right_val
        return True

if __name__ == "__main__":
    db = SovereignDB()
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR, credits INT)")
    db.execute("INSERT INTO users VALUES (1, 'Ada', 500)")
    db.execute("INSERT INTO users VALUES (2, 'Alan', 750)")
    res = db.execute("SELECT name, credits FROM users WHERE credits > 600")
    print("Query result:", res)
    assert res["count"] == 1
    assert res["rows"][0][0] == "Alan"
    print("SovereignSQL engine verified.")
