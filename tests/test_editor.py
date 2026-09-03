#!/usr/bin/env python3
"""
Test Suite: In-OS Code Editor (AdiIDE)
Verifies:
1. Syntax highlighting tokenization (keywords, numbers, strings, comments)
2. Live AdiPython compilation and execution from editor buffer
3. Saving buffer to virtual disk via AdiFS
4. Toolbar button click routing
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from desktop.editor import CodeEditor, COLOR_KEYWORD, COLOR_NUMBER, COLOR_COMMENT

def test_editor_suite():
    print("[Test Editor] Testing In-OS Code Editor (AdiIDE)...")
    vm = VM()

    # 1. Test Syntax Highlighting
    print("  -> Testing syntax highlighting tokenization...")
    test_code = "def compute(x): # calculate\n    return x + 42"
    ed = CodeEditor("test_prog.ap", test_code, vm=vm)

    line1_toks = ed.highlight_line(ed.lines[0])
    # Check 'def' keyword colored purple
    assert any(t[0] == "def" and t[1] == COLOR_KEYWORD for t in line1_toks), "Keyword 'def' not highlighted"
    # Check comment colored cyan
    assert any("# calculate" in t[0] and t[1] == COLOR_COMMENT for t in line1_toks), "Comment not highlighted"

    line2_toks = ed.highlight_line(ed.lines[1])
    # Check '42' number colored yellow
    assert any(t[0] == "42" and t[1] == COLOR_NUMBER for t in line2_toks), "Number '42' not highlighted"
    print("  -> [PASS] Syntax tokenization verified.")

    # 2. Test Live Compilation & Execution
    print("  -> Testing live compilation and execution...")
    ed_run_code = """
def answer():
    return 7 * 6

ans = answer()
"""
    ed_runner = CodeEditor("run_test.ap", ed_run_code, vm=vm)
    ed_runner.run_code()
    assert "SUCCESS" in ed_runner.status, f"Run failed: {ed_runner.status}"
    print(f"  -> Execution status: {ed_runner.status}")
    print("  -> [PASS] Live code execution verified.")

    # 3. Test Save to Disk via AdiFS
    print("  -> Testing buffer save to virtual hard disk via AdiFS...")
    save_ok = ed_runner.save_to_disk()
    assert save_ok, f"Save failed: {ed_runner.status}"
    assert "SAVED" in ed_runner.status
    # Verify file actually exists on AdiFS
    assert ed_runner.adifs.exists("run_test.ap"), "Saved file not found on disk"
    readback = ed_runner.adifs.read_file("run_test.ap").decode("utf-8")
    assert "def answer():" in readback, "Readback content mismatch"
    print(f"  -> Save status: {ed_runner.status}")
    print("  -> [PASS] Virtual disk persistence verified.")

    # 4. Test Toolbar Click Dispatch
    print("  -> Testing toolbar button clicks...")
    # Click [RUN] button at rel_x=20, rel_y=10
    act_run = ed_runner.handle_click(20, 10)
    assert act_run == "run", f"Click [RUN] expected 'run', got {act_run}"
    # Click [SAVE] button at rel_x=80, rel_y=10
    act_save = ed_runner.handle_click(80, 10)
    assert act_save == "save", f"Click [SAVE] expected 'save', got {act_save}"
    print("  -> [PASS] Toolbar clicks verified.")

    print("\n[Test Editor] ALL CODE EDITOR TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_editor_suite()
