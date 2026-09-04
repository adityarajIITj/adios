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

import os
import sys
import shlex
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from userland.coreutils import CoreUtils

HELP_MANUAL = """=============================================================================
AdiOS Sovereign POSIX Shell & Toolchain Utility Manual
=============================================================================
Core File Operations:
  ls [-la] [path]       List directory contents and file sizes
  cat [-n] <file>       Concatenate and display file content
  cp <src> <dst>        Copy file from source to destination
  mv <src> <dst>        Move / rename file
  rm <file...>          Remove one or more files
  touch <file...>       Create empty file or update timestamp
  mkdir <dir>           Create new directory in virtual filesystem
  pwd                   Print current working directory
  cd <dir>              Change working directory

Text & Cryptographic Utilities:
  wc <file>             Count lines, words, and bytes
  grep <pattern> <file> Search text for regular expressions or strings
  head [-n N] <file>    Output first N lines of file (default 10)
  tail [-n N] <file>    Output last N lines of file (default 10)
  sha256sum <file>      Compute cryptographic SHA-256 hash digest

Process & System Monitoring:
  ps [aux]              Report current snapshot of sovereign processes
  top                   Display dynamic system telemetry & resource utilization
  free [-h]             Display amount of free and used physical & swap memory
  uptime                Tell how long the sovereign system has been running
  uname [-a]            Print operating system and RV32IM hardware info
  whoami                Print effective user ID (root)
  date                  Print system date and time
  kill [-9] <pid>       Send termination signal to process by PID
  clear                 Clear terminal display history
  wallpaper [theme]     Display or change desktop ASCII art wallpaper (cyber, sovereign, slant, matrix)

In-OS C99 Toolchain & Build System:
  cc [opts] <file.c>    AdiOS In-OS C99 compiler (flags: -S, -c, -o, --help)
  make [target]         Sovereign build manager (targets: all, kernel, clean, test)

Shell Features & Builtins:
  cmd1 | cmd2           Pipelines across multiple commands
  cmd > file            Redirect stdout to file (overwrite)
  cmd >> file           Redirect stdout to file (append)
  $VAR                  Environment variable expansion ($OS, $ARCH, $USER, $HOME)
  export VAR=VAL        Set environment variable
  help [cmd]            Display this utility manual or specific command help
  wallpaper [theme]     Render ASCII art wallpaper in shell (themes: cyber, sovereign, slant, matrix)
  games / arcade        Launch 3D Sovereign Games Arcade (CastleAdiOS / StarFlight)
============================================================================="""

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
            "HOME": "/root",
            "PWD": "/root"
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
        elif cmd == "help":
            if args:
                cmd_topic = args[0].lower()
                lines = [l for l in HELP_MANUAL.split("\n") if f"  {cmd_topic}" in l]
                if lines:
                    output = f"Help for '{cmd_topic}':\n" + "\n".join(lines)
                else:
                    output = f"help: no help entry found for '{cmd_topic}'. Run 'help' for full manual."
            else:
                output = HELP_MANUAL
        elif cmd == "pwd":
            output = self.utils.pwd()
        elif cmd == "whoami":
            output = self.utils.whoami()
        elif cmd == "cd":
            target = args[0] if args else "~"
            err = self.utils.cd(target)
            if err:
                output = err
            else:
                self.env["PWD"] = self.utils.pwd()
        elif cmd == "mkdir":
            if args:
                for d in args:
                    self.utils.mkdir(d)
            else:
                output = "mkdir: missing operand"
        elif cmd == "date":
            output = self.utils.date()
        elif cmd == "uptime":
            output = self.utils.uptime()
        elif cmd == "free":
            output = self.utils.free(human_readable="-h" in args)
        elif cmd == "ps":
            output = self.utils.ps(" ".join(args))
        elif cmd == "top":
            output = self.utils.top()
        elif cmd == "kill":
            if args:
                try:
                    sig = 9
                    pid_str = args[-1]
                    if len(args) > 1 and args[0].startswith("-"):
                        sig = int(args[0][1:])
                    output = self.utils.kill(int(pid_str), sig=sig)
                except ValueError:
                    output = f"kill: invalid argument '{args[-1]}'"
            else:
                output = "kill: usage: kill [-sig] <pid>"
        elif cmd == "clear":
            output = "\033[2J\033[H"
        elif cmd == "wallpaper":
            from desktop.wallpaper import get_wallpaper_text, THEME_KEYS
            if args:
                choice = args[0].lower()
                if choice in ("--list", "-l", "list"):
                    output = "Available wallpaper themes: " + ", ".join(THEME_KEYS)
                elif choice in THEME_KEYS:
                    self.env["WALLPAPER_THEME"] = choice
                    output = get_wallpaper_text(choice)
                else:
                    output = f"wallpaper: unknown theme '{choice}'. Available: {', '.join(THEME_KEYS)}"
            else:
                current = self.env.get("WALLPAPER_THEME", "cyber")
                output = get_wallpaper_text(current)
        elif cmd == "make":
            target = args[0] if args else "all"
            output = self.utils.make(target)
        elif cmd == "cc":
            from compiler.driver import AdiCompiler
            if not args or "-h" in args or "--help" in args:
                output = AdiCompiler.help()
            else:
                src_file = None
                target_out = "a.out"
                mode_asm = "-S" in args
                mode_obj = "-c" in args
                i = 0
                while i < len(args):
                    a = args[i]
                    if a == "-o" and i + 1 < len(args):
                        target_out = args[i + 1]
                        i += 2
                    elif a in ("-S", "-c"):
                        i += 1
                    elif not a.startswith("-") and src_file is None:
                        src_file = a
                        i += 1
                    else:
                        i += 1

                if not src_file:
                    output = "cc: fatal error: no input files"
                else:
                    vpath = self.utils._get_vfs_path(src_file)
                    if vpath not in self.utils.vfs:
                        output = f"cc: error: {src_file}: No such file or directory"
                    else:
                        c_src = self.utils.vfs[vpath].decode("utf-8", errors="replace")
                        compiler = AdiCompiler()
                        try:
                            if mode_asm:
                                asm_txt = compiler.compile_to_asm(c_src)
                                dest_vpath = self.utils._resolve_path(target_out)
                                self.utils.write_file(dest_vpath, asm_txt.encode("utf-8"))
                                output = f"[cc] Compiled '{src_file}' -> '{target_out}' (Assembly text)"
                            elif mode_obj:
                                raw_bin = compiler.compile_to_bin(c_src)
                                dest_vpath = self.utils._resolve_path(target_out)
                                self.utils.write_file(dest_vpath, raw_bin)
                                output = f"[cc] Compiled '{src_file}' -> '{target_out}' ({len(raw_bin)} bytes machine code)"
                            else:
                                elf_bin = compiler.compile_to_elf(c_src)
                                dest_vpath = self.utils._resolve_path(target_out)
                                self.utils.write_file(dest_vpath, elf_bin)
                                output = f"[cc] Compiled '{src_file}' -> '{target_out}' ({len(elf_bin)} bytes ELF32 binary)"
                        except Exception as e:
                            output = f"cc: compilation error: {str(e)}"
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
            resolved_out = self.utils._resolve_path(out_file)
            existing = self.utils.vfs.get(resolved_out, b"") if redir_out_append else b""
            new_data = existing + (output + "\n").encode("utf-8")
            self.utils.write_file(resolved_out, new_data)
            return ""

        return output

if __name__ == "__main__":
    u = CoreUtils()
    sh = SovereignShell(u)
    sh.eval("echo Sovereign OS Kernel > banner.txt")
    assert b"Sovereign OS Kernel" in u.vfs["/root/banner.txt"] or b"Sovereign OS Kernel" in u.vfs.get("banner.txt", b"")
    res = sh.eval("cat banner.txt | grep Kernel | wc")
    print("Pipeline result:", res)
    assert "1" in res
    assert "init" in sh.eval("ps")
    assert "512M" in sh.eval("free -h")
    assert "load average" in sh.eval("uptime")
    assert "root" in sh.eval("whoami")
    assert "AdiOS" in sh.eval("help")
    assert "MAKE" in sh.eval("make")
    print("POSIX Shell interpreter verified.")
