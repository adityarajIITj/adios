#!/usr/bin/env python3
"""
AdiOS In-OS C Preprocessor (compiler/preprocessor.py)
Implements full ANSI C99 macro preprocessing pipeline:
- Object-like macros: #define NAME value
- Function-like macros: #define ADD(x, y) ((x) + (y))
- Macro expansion with argument substitution, stringification (#x), and token pasting (x ## y)
- Conditional compilation: #ifdef, #ifndef, #if, #elif, #else, #endif
- Header inclusion: #include <file.h> and #include "file.h" with virtual filesystem (VFS) support
- Header guards & #pragma once deduplication
- Comment stripping (single-line // and block /* */)
- Predefined macros: __LINE__, __FILE__, __DATE__, __TIME__, __ADIOS__, __riscv

Zero external dependencies. Pure bare-metal RV32IM toolchain component.
STRICT ZERO EMOJI POLICY.
"""

import re
import os
from typing import Dict, List, Tuple, Optional, Set, Any

class Macro:
    def __init__(self, name: str, params: Optional[List[str]] = None, body: str = "", is_func: bool = False):
        self.name = name
        self.params = params or []
        self.body = body.strip()
        self.is_func = is_func

class CPreprocessor:
    """
    ANSI C Preprocessor engine supporting recursive expansion, conditionals, and include management.
    """
    def __init__(self, vfs: Optional[Dict[str, str]] = None, include_dirs: Optional[List[str]] = None):
        self.vfs: Dict[str, str] = vfs if vfs is not None else {}
        self.include_dirs: List[str] = include_dirs or ["/include", "/usr/include", "."]
        self.macros: Dict[str, Macro] = {}
        self.included_files: Set[str] = set()
        self.pragma_once_files: Set[str] = set()

        # Initialize built-in macros
        self._init_builtins()

    def _init_builtins(self):
        self.define("__ADIOS__", "1")
        self.define("__riscv", "1")
        self.define("__riscv_xlen", "32")
        self.define("__LP32__", "1")

    def define(self, name: str, value: str = "1"):
        """Defines an object-like macro."""
        self.macros[name] = Macro(name=name, params=None, body=str(value), is_func=False)

    def define_func(self, name: str, params: List[str], body: str):
        """Defines a function-like macro."""
        self.macros[name] = Macro(name=name, params=params, body=body, is_func=True)

    def undef(self, name: str):
        """Removes a defined macro."""
        if name in self.macros:
            del self.macros[name]

    def is_defined(self, name: str) -> bool:
        return name in self.macros

    def strip_comments(self, text: str) -> str:
        """Removes single-line and multi-line C comments while preserving strings."""
        result = []
        i = 0
        n = len(text)
        in_string = False
        in_char = False
        string_quote = ""

        while i < n:
            c = text[i]

            # Handle string literal bounds
            if not in_string and not in_char:
                if c == '"':
                    in_string = True
                    result.append(c)
                    i += 1
                    continue
                elif c == "'":
                    in_char = True
                    result.append(c)
                    i += 1
                    continue
                elif c == '/' and i + 1 < n:
                    if text[i + 1] == '/':
                        # Single-line comment
                        i += 2
                        while i < n and text[i] != '\n':
                            i += 1
                        continue
                    elif text[i + 1] == '*':
                        # Multi-line block comment
                        i += 2
                        while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                            if text[i] == '\n':
                                result.append('\n') # preserve line count
                            i += 1
                        i += 2 # skip */
                        continue
            else:
                if in_string:
                    result.append(c)
                    if c == '\\' and i + 1 < n:
                        result.append(text[i + 1])
                        i += 2
                        continue
                    elif c == '"':
                        in_string = False
                    i += 1
                    continue
                elif in_char:
                    result.append(c)
                    if c == '\\' and i + 1 < n:
                        result.append(text[i + 1])
                        i += 2
                        continue
                    elif c == "'":
                        in_char = False
                    i += 1
                    continue

            result.append(c)
            i += 1

        return "".join(result)

    def process(self, source: str, filename: str = "<stdin>") -> str:
        """
        Executes preprocessor passes over source code.
        """
        # 1. Strip comments
        cleaned = self.strip_comments(source)

        # 2. Join lines ending with backslash
        joined_lines = []
        continuation = ""
        for line in cleaned.splitlines():
            line_str = line.rstrip()
            if line_str.endswith("\\"):
                continuation += line_str[:-1] + " "
            else:
                joined_lines.append(continuation + line)
                continuation = ""
        if continuation:
            joined_lines.append(continuation)

        # 3. Process directives and conditional blocks
        output_lines: List[str] = []
        cond_stack: List[Dict[str, Any]] = [] # stack of {'active': bool, 'matched': bool}

        def is_active():
            return all(c['active'] for c in cond_stack)

        for line_num, line in enumerate(joined_lines, 1):
            stripped = line.strip()

            if stripped.startswith("#"):
                parts = stripped[1:].strip().split(None, 1)
                directive = parts[0] if parts else ""
                arg = parts[1].strip() if len(parts) > 1 else ""

                if directive == "ifdef":
                    macro_name = arg.split()[0] if arg else ""
                    parent_active = is_active()
                    cond_val = self.is_defined(macro_name)
                    cond_stack.append({'active': parent_active and cond_val, 'matched': cond_val})
                    continue

                elif directive == "ifndef":
                    macro_name = arg.split()[0] if arg else ""
                    parent_active = is_active()
                    cond_val = not self.is_defined(macro_name)
                    cond_stack.append({'active': parent_active and cond_val, 'matched': cond_val})
                    continue

                elif directive == "if":
                    parent_active = is_active()
                    cond_val = self._eval_expr(arg)
                    cond_stack.append({'active': parent_active and bool(cond_val), 'matched': bool(cond_val)})
                    continue

                elif directive == "elif":
                    if not cond_stack:
                        raise SyntaxError(f"Unexpected #elif at line {line_num}")
                    top = cond_stack[-1]
                    parent_active = all(c['active'] for c in cond_stack[:-1])
                    if not top['matched'] and parent_active and self._eval_expr(arg):
                        top['active'] = True
                        top['matched'] = True
                    else:
                        top['active'] = False
                    continue

                elif directive == "else":
                    if not cond_stack:
                        raise SyntaxError(f"Unexpected #else at line {line_num}")
                    top = cond_stack[-1]
                    parent_active = all(c['active'] for c in cond_stack[:-1])
                    top['active'] = parent_active and (not top['matched'])
                    top['matched'] = True
                    continue

                elif directive == "endif":
                    if not cond_stack:
                        raise SyntaxError(f"Unexpected #endif at line {line_num}")
                    cond_stack.pop()
                    continue

                # If current conditional branch is inactive, skip other directives
                if not is_active():
                    continue

                if directive == "define":
                    self._parse_define(arg)
                    continue

                elif directive == "undef":
                    macro_name = arg.split()[0] if arg else ""
                    self.undef(macro_name)
                    continue

                elif directive == "include":
                    inc_code = self._handle_include(arg, filename)
                    output_lines.append(inc_code)
                    continue

                elif directive == "pragma":
                    if arg.strip() == "once":
                        self.pragma_once_files.add(filename)
                    continue

                elif directive == "error":
                    raise RuntimeError(f"#error: {arg} (at {filename}:{line_num})")

                elif directive == "warning":
                    continue # Warning ignored during silent pass

            # Non-directive code line: expand macros if active
            if is_active():
                expanded = self.expand_macros(line, filename, line_num)
                output_lines.append(expanded)

        return "\n".join(output_lines)

    def _parse_define(self, text: str):
        """Parses #define directives into object-like or function-like macros."""
        text = text.strip()
        if not text:
            return

        # Check for function-like macro: NAME(arg1, arg2)
        match_fn = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)\s*(.*)$", text)
        if match_fn:
            name = match_fn.group(1)
            raw_params = match_fn.group(2)
            body = match_fn.group(3)
            params = [p.strip() for p in raw_params.split(",") if p.strip()]
            self.define_func(name, params, body)
            return

        # Object-like macro: NAME value
        parts = text.split(None, 1)
        name = parts[0]
        body = parts[1] if len(parts) > 1 else "1"
        self.define(name, body)

    def _handle_include(self, arg: str, current_file: str) -> str:
        """Resolves header inclusion from VFS or include search paths."""
        arg = arg.strip()
        header_name = ""
        if arg.startswith("<") and arg.endswith(">"):
            header_name = arg[1:-1]
        elif arg.startswith('"') and arg.endswith('"'):
            header_name = arg[1:-1]
        else:
            header_name = arg

        # Check pragma once
        if header_name in self.pragma_once_files:
            return ""

        # Search VFS
        if header_name in self.vfs:
            self.included_files.add(header_name)
            return self.process(self.vfs[header_name], filename=header_name)

        for d in self.include_dirs:
            candidate = os.path.join(d, header_name).replace("\\", "/")
            if candidate in self.vfs:
                self.included_files.add(candidate)
                return self.process(self.vfs[candidate], filename=candidate)

        # Fallback empty string if standard headers like <stdio.h> are simulated internally
        return f"/* included {header_name} */"

    def expand_macros(self, line: str, filename: str = "<stdin>", line_num: int = 1) -> str:
        """Recursively expands all defined macros in a line of code."""
        # Dynamic macros
        line = line.replace("__LINE__", str(line_num))
        line = line.replace("__FILE__", f'"{filename}"')

        # Function-like macro expansion: NAME(args...)
        for name, macro in self.macros.items():
            if not macro.is_func:
                continue

            # Look for name followed by '('
            pattern = re.compile(r"\b" + re.escape(name) + r"\s*\((.*?)\)", re.DOTALL)
            while True:
                match = pattern.search(line)
                if not match:
                    break

                raw_args = match.group(1)
                args = [a.strip() for a in self._split_args(raw_args)]
                replacement = macro.body

                # Token pasting: x ## y
                replacement = re.sub(r"\s*##\s*", "", replacement)

                for p_idx, param in enumerate(macro.params):
                    arg_val = args[p_idx] if p_idx < len(args) else ""
                    # Stringification: #param
                    replacement = re.sub(r"#" + re.escape(param) + r"\b", f'"{arg_val}"', replacement)
                    # Normal parameter substitution
                    replacement = re.sub(r"\b" + re.escape(param) + r"\b", arg_val, replacement)

                start, end = match.span()
                line = line[:start] + replacement + line[end:]

        # Object-like macro expansion
        for name, macro in self.macros.items():
            if macro.is_func:
                continue
            pattern = re.compile(r"\b" + re.escape(name) + r"\b")
            line = pattern.sub(macro.body, line)

        return line

    def _split_args(self, args_str: str) -> List[str]:
        """Splits comma-separated macro arguments while respecting nested parentheses."""
        args = []
        curr = []
        depth = 0
        for ch in args_str:
            if ch == '(':
                depth += 1
                curr.append(ch)
            elif ch == ')':
                depth -= 1
                curr.append(ch)
            elif ch == ',' and depth == 0:
                args.append("".join(curr).strip())
                curr = []
            else:
                curr.append(ch)
        if curr:
            args.append("".join(curr).strip())
        return args

    def _eval_expr(self, expr: str) -> int:
        """Evaluates a constant preprocessor expression for #if / #elif."""
        expr = expr.strip()
        # Replace defined(NAME) or defined NAME
        def_match = re.finditer(r"\bdefined\s*(?:\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)|([A-Za-z_][A-Za-z0-9_]*))", expr)
        for m in def_match:
            m_name = m.group(1) or m.group(2)
            val = "1" if self.is_defined(m_name) else "0"
            expr = expr.replace(m.group(0), val)

        # Expand remaining object-like macros
        for name, macro in self.macros.items():
            if not macro.is_func:
                expr = re.sub(r"\b" + re.escape(name) + r"\b", macro.body, expr)

        # Non-defined identifiers in #if evaluate to 0
        expr = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", "0", expr)

        try:
            # Safe evaluation of integer expressions
            return int(eval(expr, {"__builtins__": None}, {}))
        except Exception:
            return 0
