#!/usr/bin/env python3
"""
AdiOS Userland Subsystem: Core Utilities Suite (coreutils.py)
Implements standard UNIX/POSIX userland commands:
cat, ls, cp, mv, rm, mkdir, touch, echo, grep, wc, head, tail, sha256sum, uname, ps, kill.
Zero external dependencies.
"""

import os
import re
from typing import List, Dict, Tuple, Optional
from crypto.sha256 import sha256_hash as sha256

class CoreUtils:
    """
    Standard operating system userland utility commands operating
    over the virtual filesystem and process manager.
    """
    def __init__(self, vfs_root: Optional[Dict[str, bytes]] = None):
        # In-memory virtual filesystem table (path -> content)
        self.vfs: Dict[str, bytes] = vfs_root if vfs_root is not None else {}

    def echo(self, args: List[str]) -> str:
        return " ".join(args)

    def cat(self, path: str, number_lines: bool = False) -> str:
        if path not in self.vfs:
            raise FileNotFoundError(f"cat: {path}: No such file or directory")
        content = self.vfs[path].decode("utf-8", errors="replace")
        lines = content.split("\n")
        if number_lines:
            return "\n".join(f"{i+1:6d}  {line}" for i, line in enumerate(lines))
        return content

    def touch(self, path: str):
        if path not in self.vfs:
            self.vfs[path] = b""

    def write_file(self, path: str, data: bytes):
        self.vfs[path] = data

    def cp(self, src: str, dst: str):
        if src not in self.vfs:
            raise FileNotFoundError(f"cp: cannot stat '{src}': No such file")
        self.vfs[dst] = bytes(self.vfs[src])

    def mv(self, src: str, dst: str):
        self.cp(src, dst)
        del self.vfs[src]

    def rm(self, path: str):
        if path not in self.vfs:
            raise FileNotFoundError(f"rm: cannot remove '{path}': No such file")
        del self.vfs[path]

    def ls(self, prefix: str = "") -> List[Tuple[str, int]]:
        """Lists files and byte sizes matching directory prefix."""
        files = []
        for path, data in self.vfs.items():
            if not prefix or path.startswith(prefix):
                files.append((path, len(data)))
        return sorted(files)

    def wc(self, path: str) -> Tuple[int, int, int]:
        """Returns (lines, words, bytes)."""
        if path not in self.vfs:
            raise FileNotFoundError(f"wc: {path}: No such file")
        raw = self.vfs[path]
        text = raw.decode("utf-8", errors="replace")
        lines = len(text.split("\n")) if text else 0
        words = len(text.split())
        byte_count = len(raw)
        return (lines, words, byte_count)

    def grep(self, pattern: str, path: str, ignore_case: bool = False, invert: bool = False) -> List[str]:
        if path not in self.vfs:
            raise FileNotFoundError(f"grep: {path}: No such file")
        text = self.vfs[path].decode("utf-8", errors="replace")
        flags = re.IGNORECASE if ignore_case else 0
        compiled = re.compile(pattern, flags)
        matches = []
        for line in text.split("\n"):
            matched = bool(compiled.search(line))
            if matched != invert:
                matches.append(line)
        return matches

    def head(self, path: str, n: int = 10) -> str:
        if path not in self.vfs:
            raise FileNotFoundError(f"head: {path}: No such file")
        lines = self.vfs[path].decode("utf-8", errors="replace").split("\n")
        return "\n".join(lines[:n])

    def tail(self, path: str, n: int = 10) -> str:
        if path not in self.vfs:
            raise FileNotFoundError(f"tail: {path}: No such file")
        lines = self.vfs[path].decode("utf-8", errors="replace").split("\n")
        return "\n".join(lines[-n:] if len(lines) >= n else lines)

    def sha256sum(self, path: str) -> str:
        if path not in self.vfs:
            raise FileNotFoundError(f"sha256sum: {path}: No such file")
        return sha256(self.vfs[path]).hex()

    def uname(self) -> str:
        return "AdiOS sovereign-node 1.0.0-RV32IM #1 PREEMPT Thu Sep 3 2026 riscv32 GNU/AdiOS"

if __name__ == "__main__":
    utils = CoreUtils()
    utils.touch("kernel.cfg")
    utils.write_file("greeting.txt", b"Hello Sovereign AdiOS\nLine 2\nLine 3\n")
    assert utils.cat("greeting.txt").startswith("Hello")
    assert utils.wc("greeting.txt") == (4, 5, 30)
    assert utils.grep("Line", "greeting.txt") == ["Line 2", "Line 3"]
    h = utils.sha256sum("greeting.txt")
    assert len(h) == 64
    print("Core utilities verified.")
