#!/usr/bin/env python3
"""
AdiPython Macro Preprocessor
Handles #include, #define, #ifdef, #ifndef, #endif for multi-file AdiPython codebases.
Works seamlessly with both local filesystem files and AdiFS virtual disk files.
"""

import re
import os

class Preprocessor:
    def __init__(self, include_dirs=None, adifs=None):
        self.include_dirs = include_dirs or ["scripts", "games", "."]
        self.adifs = adifs
        self.defines = {}
        self.included_files = set()

    def define(self, name, value="1"):
        self.defines[name] = str(value)

    def undefine(self, name):
        if name in self.defines:
            del self.defines[name]

    def _resolve_include(self, filename):
        # 1. Check AdiFS virtual disk if available
        if self.adifs and self.adifs.exists(filename):
            return self.adifs.read_file(filename).decode("utf-8", errors="replace")

        # 2. Check local directories
        for d in self.include_dirs:
            p = os.path.join(d, filename)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()

        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        raise FileNotFoundError(f"Preprocessor: Cannot find include file '{filename}'")

    def process(self, source, current_file=None):
        """Processes macros and includes recursively."""
        lines = source.splitlines()
        output = []
        cond_stack = [True] # Stack of boolean conditions for ifdef/ifndef

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Handle #ifdef
            if stripped.startswith("#ifdef"):
                var = stripped.split()[1]
                active = cond_stack[-1] and (var in self.defines)
                cond_stack.append(active)
                continue

            # Handle #ifndef
            if stripped.startswith("#ifndef"):
                var = stripped.split()[1]
                active = cond_stack[-1] and (var not in self.defines)
                cond_stack.append(active)
                continue

            # Handle #else
            if stripped.startswith("#else"):
                if len(cond_stack) > 1:
                    prev = cond_stack.pop()
                    parent = cond_stack[-1]
                    cond_stack.append(parent and not prev)
                continue

            # Handle #endif
            if stripped.startswith("#endif"):
                if len(cond_stack) > 1:
                    cond_stack.pop()
                continue

            # If inside an inactive conditional block, skip line
            if not cond_stack[-1]:
                continue

            # Handle #define NAME VALUE
            if stripped.startswith("#define"):
                parts = stripped.split(maxsplit=2)
                name = parts[1]
                val = parts[2] if len(parts) > 2 else "1"
                self.defines[name] = val
                continue

            # Handle #undef NAME
            if stripped.startswith("#undef"):
                parts = stripped.split()
                name = parts[1]
                self.undefine(name)
                continue

            # Handle #include "filename" or #include <filename>
            if stripped.startswith("#include"):
                m = re.match(r'#include\s*["<]([^">]+)[">]', stripped)
                if not m:
                    raise SyntaxError(f"Invalid #include syntax at line {line_num}: {line}")
                inc_name = m.group(1)

                if inc_name in self.included_files:
                    continue # Prevent circular or duplicate includes
                self.included_files.add(inc_name)

                inc_content = self._resolve_include(inc_name)
                processed_inc = self.process(inc_content, current_file=inc_name)
                output.append(processed_inc)
                continue

            # Perform macro word replacements
            processed_line = line
            for name, val in self.defines.items():
                pattern = r'\b' + re.escape(name) + r'\b'
                processed_line = re.sub(pattern, val, processed_line)

            output.append(processed_line)

        return "\n".join(output)
