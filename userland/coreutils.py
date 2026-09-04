#!/usr/bin/env python3
"""
AdiOS Userland Subsystem: Core Utilities Suite (coreutils.py)
Implements standard UNIX/POSIX userland commands:
cat, ls, cp, mv, rm, mkdir, touch, echo, grep, wc, head, tail, sha256sum, uname, ps, kill.
Zero external dependencies.
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from crypto.sha256 import sha256_hash as sha256

class CoreUtils:
    """
    Standard operating system userland utility commands operating
    over the virtual filesystem and process manager.
    """
    def __init__(self, vfs_root: Optional[Dict[str, bytes]] = None):
        # In-memory virtual filesystem table (path -> content)
        self.vfs: Dict[str, bytes] = vfs_root if vfs_root is not None else {}
        self.cwd: str = "/root"
        # Simulated sovereign process table
        self.processes = [
            {"pid": 1, "ppid": 0, "user": "root", "stat": "S", "cpu": 0.1, "mem": 1.2, "time": "00:04:12", "cmd": "init [ring0]"},
            {"pid": 2, "ppid": 1, "user": "root", "stat": "S", "cpu": 0.0, "mem": 0.4, "time": "00:00:02", "cmd": "ksoftirqd/0"},
            {"pid": 10, "ppid": 1, "user": "root", "stat": "S", "cpu": 0.2, "mem": 2.8, "time": "00:01:45", "cmd": "vfs_worker"},
            {"pid": 42, "ppid": 1, "user": "root", "stat": "R", "cpu": 1.8, "mem": 8.4, "time": "00:03:19", "cmd": "desktop_wm"},
            {"pid": 88, "ppid": 42, "user": "root", "stat": "S", "cpu": 0.5, "mem": 3.1, "time": "00:00:54", "cmd": "compositor"},
            {"pid": 101, "ppid": 88, "user": "root", "stat": "R+", "cpu": 0.8, "mem": 4.5, "time": "00:00:15", "cmd": "sh"}
        ]

    def _resolve_path(self, path: str) -> str:
        """Resolves relative or tilde path against current working directory."""
        if path.startswith("~"):
            path = "/root" + path[1:]
        if not path.startswith("/"):
            if self.cwd == "/":
                path = "/" + path
            else:
                path = f"{self.cwd}/{path}"
        parts = []
        for segment in path.split("/"):
            if segment == "" or segment == ".":
                continue
            elif segment == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(segment)
        return "/" + "/".join(parts)

    def _get_vfs_path(self, path: str) -> str:
        if path in self.vfs:
            return path
        resolved = self._resolve_path(path)
        if resolved in self.vfs:
            return resolved
        return path

    def echo(self, args: List[str]) -> str:
        return " ".join(args)

    def pwd(self) -> str:
        return self.cwd

    def whoami(self) -> str:
        return "root"

    def cd(self, path: str = "~") -> str:
        target = self._resolve_path(path)
        if target == "/" or target == "/root":
            self.cwd = target
            return ""
        dir_key = target.rstrip("/") + "/"
        has_entries = any(k.startswith(dir_key) or k == target for k in self.vfs)
        if has_entries or target in ("/bin", "/usr", "/usr/bin", "/etc", "/var", "/tmp"):
            self.cwd = target
            return ""
        self.cwd = target
        return ""

    def mkdir(self, path: str):
        target = self._resolve_path(path)
        dir_key = target.rstrip("/") + "/"
        self.vfs[dir_key] = b""

    def cat(self, path: str, number_lines: bool = False) -> str:
        vpath = self._get_vfs_path(path)
        if vpath not in self.vfs:
            raise FileNotFoundError(f"cat: {path}: No such file or directory")
        content = self.vfs[vpath].decode("utf-8", errors="replace")
        lines = content.split("\n")
        if number_lines:
            return "\n".join(f"{i+1:6d}  {line}" for i, line in enumerate(lines))
        return content

    def touch(self, path: str):
        vpath = self._resolve_path(path) if path not in self.vfs else path
        if vpath not in self.vfs:
            self.vfs[vpath] = b""

    def write_file(self, path: str, data: bytes):
        vpath = self._resolve_path(path) if path not in self.vfs else path
        self.vfs[vpath] = data

    def cp(self, src: str, dst: str):
        src_v = self._get_vfs_path(src)
        if src_v not in self.vfs:
            raise FileNotFoundError(f"cp: cannot stat '{src}': No such file")
        dst_v = self._resolve_path(dst) if dst not in self.vfs else dst
        self.vfs[dst_v] = bytes(self.vfs[src_v])

    def mv(self, src: str, dst: str):
        src_v = self._get_vfs_path(src)
        self.cp(src_v, dst)
        del self.vfs[src_v]

    def rm(self, path: str):
        vpath = self._get_vfs_path(path)
        if vpath not in self.vfs:
            raise FileNotFoundError(f"rm: cannot remove '{path}': No such file")
        del self.vfs[vpath]

    def ls(self, prefix: str = "") -> List[Tuple[str, int]]:
        """Lists files and byte sizes matching directory prefix."""
        files = []
        if not prefix:
            check_prefix = self.cwd.rstrip("/") + "/" if self.cwd != "/" else "/"
        else:
            check_prefix = self._resolve_path(prefix)
            if not check_prefix.endswith("/"):
                check_prefix += "/"

        # If prefix matches exactly in vfs or partial match
        matched_any = False
        for path, data in self.vfs.items():
            if path.startswith(check_prefix):
                files.append((path, len(data)))
                matched_any = True

        # Fallback to root or global prefix search
        if not matched_any:
            for path, data in self.vfs.items():
                if not prefix or path.startswith(prefix) or prefix in path:
                    files.append((path, len(data)))

        return sorted(files)

    def wc(self, path: str) -> Tuple[int, int, int]:
        """Returns (lines, words, bytes)."""
        vpath = self._get_vfs_path(path)
        if vpath not in self.vfs:
            raise FileNotFoundError(f"wc: {path}: No such file")
        raw = self.vfs[vpath]
        text = raw.decode("utf-8", errors="replace")
        lines = len(text.split("\n")) if text else 0
        words = len(text.split())
        byte_count = len(raw)
        return (lines, words, byte_count)

    def grep(self, pattern: str, path: str, ignore_case: bool = False, invert: bool = False) -> List[str]:
        vpath = self._get_vfs_path(path)
        if vpath not in self.vfs:
            raise FileNotFoundError(f"grep: {path}: No such file")
        text = self.vfs[vpath].decode("utf-8", errors="replace")
        flags = re.IGNORECASE if ignore_case else 0
        compiled = re.compile(pattern, flags)
        matches = []
        for line in text.split("\n"):
            matched = bool(compiled.search(line))
            if matched != invert:
                matches.append(line)
        return matches

    def head(self, path: str, n: int = 10) -> str:
        vpath = self._get_vfs_path(path)
        if vpath not in self.vfs:
            raise FileNotFoundError(f"head: {path}: No such file")
        lines = self.vfs[vpath].decode("utf-8", errors="replace").split("\n")
        return "\n".join(lines[:n])

    def tail(self, path: str, n: int = 10) -> str:
        vpath = self._get_vfs_path(path)
        if vpath not in self.vfs:
            raise FileNotFoundError(f"tail: {path}: No such file")
        lines = self.vfs[vpath].decode("utf-8", errors="replace").split("\n")
        return "\n".join(lines[-n:] if len(lines) >= n else lines)

    def sha256sum(self, path: str) -> str:
        vpath = self._get_vfs_path(path)
        if vpath not in self.vfs:
            raise FileNotFoundError(f"sha256sum: {path}: No such file")
        return sha256(self.vfs[vpath]).hex()

    def uname(self) -> str:
        return "AdiOS 1.0.0-sovereign riscv32 GNU/Sovereign (v1.1.0 Workstation)"

    def date(self) -> str:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        return now.strftime("%a %b %d %H:%M:%S UTC %Y")

    def uptime(self) -> str:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        time_str = now.strftime("%H:%M:%S")
        return f" {time_str} up 14:22,  1 user,  load average: 0.08, 0.05, 0.01"

    def free(self, human_readable: bool = False) -> str:
        if human_readable:
            return (
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:            512M         82M        384M        4.0M         45M        412M\n"
                "Swap:           128M          0B        128M"
            )
        else:
            return (
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:          524288       84582      393418        4096       46288      422314\n"
                "Swap:         131072           0      131072"
            )

    def ps(self, flags: str = "") -> str:
        header = f"{'PID':>5} {'PPID':>5} {'USER':<8} {'STAT':<5} {'%CPU':>5} {'%MEM':>5} {'TIME':>8} {'COMMAND'}"
        rows = [header]
        for p in self.processes:
            rows.append(
                f"{p['pid']:5d} {p['ppid']:5d} {p['user']:<8} {p['stat']:<5} {p['cpu']:5.1f} {p['mem']:5.1f} {p['time']:>8} {p['cmd']}"
            )
        return "\n".join(rows)

    def top(self) -> str:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        time_str = now.strftime("%H:%M:%S")
        total_p = len(self.processes)
        running_p = sum(1 for p in self.processes if "R" in p["stat"])
        sleeping_p = total_p - running_p
        lines = [
            f"top - {time_str} up 14:22,  1 user,  load average: 0.08, 0.05, 0.01",
            f"Tasks: {total_p} total, {running_p} running, {sleeping_p} sleeping, 0 stopped, 0 zombie",
            "%Cpu(s):  2.4 us,  1.1 sy,  0.0 ni, 96.5 id,  0.0 wa,  0.0 hi,  0.0 si",
            "MiB Mem :    512.0 total,    384.2 free,     82.6 used,     45.2 buff/cache",
            "MiB Swap:    128.0 total,    128.0 free,      0.0 used.    412.4 avail Mem",
            "",
            f"{'PID':>5} {'USER':<8} {'PR':>3} {'NI':>3} {'VIRT':>7} {'RES':>6} {'SHR':>5} {'S':<2} {'%CPU':>5} {'%MEM':>5} {'TIME+':>8} {'COMMAND'}"
        ]
        for p in self.processes:
            lines.append(
                f"{p['pid']:5d} {p['user']:<8}  20   0   16384   4096  2048 {p['stat'][0]:<2} {p['cpu']:5.1f} {p['mem']:5.1f} {p['time']:>8} {p['cmd']}"
            )
        return "\n".join(lines)

    def kill(self, pid: int, sig: int = 9) -> str:
        if pid == 1:
            return "kill: (1) - Operation not permitted: cannot kill init"
        for i, p in enumerate(self.processes):
            if p["pid"] == pid:
                killed = self.processes.pop(i)
                return f"[kill] Process {pid} ({killed['cmd']}) terminated with signal {sig}."
        return f"kill: ({pid}) - No such process"

    def make(self, target: str = "all") -> str:
        from compiler.driver import AdiCompiler
        compiler = AdiCompiler()
        return compiler.make(target)

    def wallpaper(self, style: str = "cyber") -> str:
        from desktop.wallpaper import get_wallpaper_text
        return get_wallpaper_text(style)

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    utils = CoreUtils()
    utils.touch("kernel.cfg")
    utils.write_file("greeting.txt", b"Hello Sovereign AdiOS\nLine 2\nLine 3\n")
    assert utils.cat("greeting.txt").startswith("Hello")
    assert utils.wc("greeting.txt") == (4, 7, 36)
    assert utils.grep("Line", "greeting.txt") == ["Line 2", "Line 3"]
    h = utils.sha256sum("greeting.txt")
    assert len(h) == 64
    assert "init" in utils.ps()
    assert "512M" in utils.free(human_readable=True)
    assert "load average" in utils.uptime()
    print("Core utilities verified.")
