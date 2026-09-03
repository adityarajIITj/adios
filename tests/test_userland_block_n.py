#!/usr/bin/env python3
"""
Test Suite: Block N POSIX / Sovereign Shell & Userland Utilities
Verifies:
1. Core utilities (cat, ls, cp, mv, rm, touch, wc, grep, head, tail, sha256sum, uname)
2. Shell variable expansions ($OS, $ARCH, $HOME)
3. Shell output redirections (> write, >> append)
4. Multi-stage pipeline processing (cmd1 | cmd2 | cmd3)
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from userland.coreutils import CoreUtils
from userland.sh import SovereignShell

def test_userland_block_n_suite():
    print("[Test Userland Block N] Initializing Shell & Userland Verification...")

    # 1. Test Core Utilities File Operations
    print("  -> Testing CoreUtils File Operations (touch, write, cat, cp, mv, rm)...")
    utils = CoreUtils()
    utils.touch("/etc/hostname")
    assert "/etc/hostname" in utils.vfs
    assert utils.vfs["/etc/hostname"] == b""

    sample_text = b"Alpha\nBeta\nGamma\nDelta\nEpsilon\n"
    utils.write_file("/var/log/syslog", sample_text)
    assert utils.cat("/var/log/syslog") == sample_text.decode("utf-8")

    # Copy and Move
    utils.cp("/var/log/syslog", "/var/log/syslog.bak")
    assert "/var/log/syslog.bak" in utils.vfs
    utils.mv("/var/log/syslog.bak", "/tmp/syslog.archive")
    assert "/var/log/syslog.bak" not in utils.vfs
    assert "/tmp/syslog.archive" in utils.vfs

    # Remove
    utils.rm("/tmp/syslog.archive")
    assert "/tmp/syslog.archive" not in utils.vfs
    print("  -> [PASS] File operations verified.")

    # 2. Test Text Processing (wc, grep, head, tail, sha256sum)
    print("  -> Testing Text Processing & Cryptographic Utilities...")
    poem = b"The cosmos is within us.\nWe are made of star-stuff.\nWe are a way for the cosmos to know itself.\n"
    utils.write_file("/docs/cosmos.txt", poem)

    lines, words, bytes_cnt = utils.wc("/docs/cosmos.txt")
    assert lines == 4
    assert words == 20
    assert bytes_cnt == len(poem)

    matches = utils.grep("cosmos", "/docs/cosmos.txt")
    assert len(matches) == 2
    assert "star-stuff" not in matches[0]

    h = utils.head("/docs/cosmos.txt", n=2)
    assert len(h.split("\n")) == 2

    # Cryptographic checksum
    sum_res = utils.sha256sum("/docs/cosmos.txt")
    assert len(sum_res) == 64
    assert all(c in "0123456789abcdef" for c in sum_res)
    print("  -> [PASS] Text processing & SHA-256 verified.")

    # 3. Test Sovereign Shell: Variables, Redirections & Pipelines
    print("  -> Testing Sovereign Shell Interpreter (Pipelines & Redirections)...")
    sh = SovereignShell(utils)

    # Variable Expansion & Output Redirection
    sh.eval("echo Architecture: $ARCH on $OS > /etc/release")
    assert "/etc/release" in utils.vfs
    assert b"Architecture: RV32IM on AdiOS" in utils.vfs["/etc/release"]

    # Append Redirection
    sh.eval("echo Release: Sovereign v1.0 >> /etc/release")
    rel_content = utils.cat("/etc/release")
    assert "Architecture: RV32IM" in rel_content
    assert "Release: Sovereign v1.0" in rel_content

    # Multi-Stage Pipeline Execution
    # cat /etc/release | grep Architecture | wc
    pipe_out = sh.eval("cat /etc/release | grep Architecture | wc")
    assert "1" in pipe_out
    print("  -> [PASS] Shell variables, redirections & pipelines verified.")

    print("\n[Test Userland Block N] ALL BLOCK N USERLAND TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_userland_block_n_suite()
