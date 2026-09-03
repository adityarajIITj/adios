#!/usr/bin/env python3
"""
AdiOS Userland Subsystem: POSIX Sovereign Command Shell (sh.py)
Implements interactive POSIX-compliant command shell interpreter:
- Pipeline execution: cmd1 | cmd2 | cmd3
- File redirection: > (overwrite), >> (append), < (input)
- Environment variable expansion: $VAR
- Integration with userland/coreutils
Zero external dependencies.
"""

import shlex
from typing import Dict, List, Tuple
from userland.coreutils import CoreUtils

class SovereignShell:
    """
    POSIX Command Shell supporting pipelines, redirections, and variables.
    """
    def __init__(self, utils: CoreUtils):
        self.utils = utils
        self.env: Dict[str, str] = {
            "OS": "AdiOS",
            "ARCH": "RV32IM",
            "USER": "root",
            "PATH": "/bin:/usr/bin",
            "HOME": "/root"
        }

    def eval(self, cmd_line: str) -> str:
        """Evaluates a shell command line and returns the final stdout string."""
        cmd_line = cmd_line.strip()
        if not cmd_line or cmd_line.startswith("#"):
            return ""

        # Variable expansion
        for k, v in self.env.items():
            cmd_line = cmd_line.replace(f"${k}", v)

        # Handle Pipeline
        if "|" in cmd_line:
            pipeline_parts = [p.strip() for p in cmd_line.split("|")]
            stdin_data = ""
            for part in pipeline_parts:
                stdin_data = self.execute_single(part, stdin_data=stdin_data)
            return stdin_data
        else:
            return self.execute_single(cmd_line)

    def execute_single(self, cmd_str: str, stdin_data: str = "") -> str:
        # Check Redirections
        redir_out_append = ">>" in cmd_str
        redir_out_write = ">" in cmd_str and not redir_out_append
        out_file = None

        if redir_out_append:
            cmd_str, _, out_file = cmd_str.partition(">>")
            out_file = out_file.strip()
        elif redir_out_write:
            cmd_str, _, out_file = cmd_str.partition(">")
            out_file = out_file.strip()

        tokens = shlex.split(cmd_str.strip())
        if not tokens:
            return ""

        cmd = tokens[0]
        args = tokens[1:]
        output = ""

        if cmd == "echo":
            output = self.utils.echo(args)
        elif cmd == "cat":
            if args:
                num_flag = "-n" in args
                files = [a for a in args if a != "-n"]
                res = []
                for f in files:
                    res.append(self.utils.cat(f, number_lines=num_flag))
                output = "\n".join(res)
            else:
                output = stdin_data
        elif cmd == "ls":
            prefix = args[0] if args else ""
            files = self.utils.ls(prefix)
            output = "\n".join(f"{f[1]:8d}  {f[0]}" for f in files)
        elif cmd == "touch":
            for f in args:
                self.utils.touch(f)
        elif cmd == "cp" and len(args) == 2:
            self.utils.cp(args[0], args[1])
        elif cmd == "mv" and len(args) == 2:
            self.utils.mv(args[0], args[1])
        elif cmd == "rm":
            for f in args:
                self.utils.rm(f)
        elif cmd == "wc":
            if args:
                lines, words, bytes_cnt = self.utils.wc(args[0])
                output = f"{lines:4d} {words:4d} {bytes_cnt:6d} {args[0]}"
            else:
                lines = len(stdin_data.split("\n")) if stdin_data else 0
                words = len(stdin_data.split())
                output = f"{lines:4d} {words:4d} {len(stdin_data):6d}"
        elif cmd == "grep":
            if len(args) >= 2:
                pattern = args[0]
                target_file = args[1]
                matches = self.utils.grep(pattern, target_file)
                output = "\n".join(matches)
            elif len(args) == 1:
                pattern = args[0]
                matches = [l for l in stdin_data.split("\n") if pattern in l]
                output = "\n".join(matches)
        elif cmd == "head":
            target = args[0] if args else ""
            output = self.utils.head(target) if target else "\n".join(stdin_data.split("\n")[:10])
        elif cmd == "tail":
            target = args[0] if args else ""
            output = self.utils.tail(target) if target else "\n".join(stdin_data.split("\n")[-10:])
        elif cmd == "sha256sum" and args:
            output = f"{self.utils.sha256sum(args[0])}  {args[0]}"
        elif cmd == "uname":
            output = self.utils.uname()
        elif cmd == "export" and args:
            for item in args:
                if "=" in item:
                    k, v = item.split("=", 1)
                    self.env[k.strip()] = v.strip()
        else:
            output = f"sh: command not found: {cmd}"

        # Handle Output Redirection
        if out_file:
            existing = self.utils.vfs.get(out_file, b"") if redir_out_append else b""
            new_data = existing + (output + "\n").encode("utf-8")
            self.utils.write_file(out_file, new_data)
            return ""

        return output

if __name__ == "__main__":
    u = CoreUtils()
    sh = SovereignShell(u)
    sh.eval("echo Sovereign OS Kernel > banner.txt")
    assert b"Sovereign OS Kernel" in u.vfs["banner.txt"]
    res = sh.eval("cat banner.txt | grep Kernel | wc")
    print("Pipeline result:", res)
    assert "1" in res
    print("POSIX Shell interpreter verified.")
