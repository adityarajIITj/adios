#!/usr/bin/env python3
"""
AdiPython Execution Engine & Ring-0 Hardware Runtime
Directly executes AST with full hardware MMIO access to memory, framebuffer, sound, and serial.
"""

import sys
import time
from .parser import (
    Program, Assign, AugAssign, FunctionDef, Return, If, While, For,
    ExprStmt, Call, BinaryOp, UnaryOp, Number, String, Identifier
)

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

class Environment:
    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable '{name}'")

    def set(self, name, value):
        self.vars[name] = value

    def assign(self, name, value):
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent:
            self.parent.assign(name, value)
            return
        self.vars[name] = value

class AdiFunction:
    def __init__(self, func_def, closure):
        self.func_def = func_def
        self.closure = closure

    def call(self, runtime, args):
        env = Environment(self.closure)
        for param, arg in zip(self.func_def.params, args):
            env.set(param, arg)
        try:
            runtime.execute_block(self.func_def.body, env)
        except ReturnSignal as ret:
            return ret.value
        return 0

class Runtime:
    def __init__(self, vm=None):
        self.vm = vm
        self.global_env = Environment()
        self._init_builtins()

    def _init_builtins(self):
        env = self.global_env
        env.set("print", self._builtin_print)
        env.set("peek", self._builtin_peek)
        env.set("poke", self._builtin_poke)
        env.set("pixel", self._builtin_pixel)
        env.set("rect", self._builtin_rect)
        env.set("line", self._builtin_line)
        env.set("clear", self._builtin_clear)
        env.set("cls", self._builtin_clear)
        env.set("tone", self._builtin_tone)
        env.set("sleep", self._builtin_sleep)

        # Standard Color Constants
        env.set("BLACK",  0x00000000)
        env.set("WHITE",  0x00FFFFFF)
        env.set("RED",    0x00F7768E)
        env.set("GREEN",  0x009ECE6A)
        env.set("YELLOW", 0x00E0AF68)
        env.set("BLUE",   0x007AA2F7)
        env.set("MAGENTA",0x00BB9AF7)
        env.set("CYAN",   0x007DCFFF)

    # -------------------------------------------------------------------------
    # Hardware MMIO Built-in Functions
    # -------------------------------------------------------------------------
    def _builtin_print(self, *args):
        text = " ".join(str(a) for a in args)
        if self.vm:
            for ch in text + "\n":
                self.vm.write8(0x10000000, ord(ch))
        else:
            print(text)
        return 0

    def _builtin_peek(self, addr):
        if self.vm:
            return self.vm.read32(int(addr) & 0xFFFFFFFF)
        return 0

    def _builtin_poke(self, addr, val):
        if self.vm:
            self.vm.write32(int(addr) & 0xFFFFFFFF, int(val) & 0xFFFFFFFF)
        return 0

    def _builtin_pixel(self, x, y, color):
        x, y = int(x), int(y)
        if 0 <= x < 640 and 0 <= y < 480:
            if self.vm:
                addr = 0x20000000 + (y * 640 + x) * 4
                self.vm.write32(addr, int(color) & 0xFFFFFFFF)
        return 0

    def _builtin_rect(self, x, y, w, h, color):
        x, y, w, h, color = int(x), int(y), int(w), int(h), int(color)
        if not self.vm: return 0
        x0 = max(0, min(639, x))
        y0 = max(0, min(479, y))
        x1 = max(0, min(640, x + w))
        y1 = max(0, min(480, y + h))

        fb = self.vm.fb
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, (color >> 24) & 0xFF])
        row_bytes = c_bytes * (x1 - x0)

        for cy in range(y0, y1):
            offset = (cy * 640 + x0) * 4
            fb[offset : offset + len(row_bytes)] = row_bytes
        return 0

    def _builtin_line(self, x0, y0, x1, y1, color):
        """High-speed Bresenham 2D Line Rasterizer."""
        x0, y0, x1, y1, color = int(x0), int(y0), int(x1), int(y1), int(color)
        if not self.vm: return 0

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            if 0 <= x0 < 640 and 0 <= y0 < 480:
                off = (y0 * 640 + x0) * 4
                self.vm.fb[off : off + 4] = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, (color >> 24) & 0xFF])

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
        return 0

    def _builtin_clear(self, color=0x001A1B26):
        if self.vm:
            c = int(color)
            c_bytes = bytes([c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF, (c >> 24) & 0xFF])
            self.vm.fb[:] = c_bytes * (640 * 480)
        return 0

    def _builtin_tone(self, freq, duration=100):
        if self.vm:
            self.vm.write32(0x10000050, int(freq))
            self.vm.write32(0x10000054, int(duration))
        return 0

    def _builtin_sleep(self, ms):
        time.sleep(int(ms) / 1000.0)
        return 0

    # -------------------------------------------------------------------------
    # Evaluation Engine
    # -------------------------------------------------------------------------
    def run(self, node, env=None):
        if env is None: env = self.global_env

        if isinstance(node, Program):
            result = None
            for stmt in node.stmts:
                result = self.run(stmt, env)
            return result

        if isinstance(node, FunctionDef):
            func = AdiFunction(node, env)
            env.set(node.name, func)
            return func

        if isinstance(node, Assign):
            val = self.eval_expr(node.value, env)
            env.assign(node.target, val)
            return val

        if isinstance(node, AugAssign):
            old = env.get(node.target)
            val = self.eval_expr(node.value, env)
            if node.op == "+": new_val = old + val
            elif node.op == "-": new_val = old - val
            elif node.op == "*": new_val = old * val
            elif node.op == "/": new_val = int(old / val)
            env.assign(node.target, new_val)
            return new_val

        if isinstance(node, Return):
            val = self.eval_expr(node.value, env) if node.value else 0
            raise ReturnSignal(val)

        if isinstance(node, If):
            cond = self.eval_expr(node.cond, env)
            if cond:
                return self.execute_block(node.then_body, env)
            for e_cond, e_body in node.elif_list:
                if self.eval_expr(e_cond, env):
                    return self.execute_block(e_body, env)
            if node.else_body:
                return self.execute_block(node.else_body, env)
            return None

        if isinstance(node, While):
            while self.eval_expr(node.cond, env):
                self.execute_block(node.body, env)
            return None

        if isinstance(node, For):
            start = self.eval_expr(node.start, env)
            end = self.eval_expr(node.end, env)
            step = self.eval_expr(node.step, env)
            for i in range(start, end, step):
                env.set(node.var, i)
                self.execute_block(node.body, env)
            return None

        if isinstance(node, ExprStmt):
            return self.eval_expr(node.expr, env)

        return None

    def execute_block(self, stmts, env):
        res = None
        for stmt in stmts:
            res = self.run(stmt, env)
        return res

    def eval_expr(self, expr, env):
        if isinstance(expr, Number):
            return expr.value
        if isinstance(expr, String):
            return expr.value
        if isinstance(expr, Identifier):
            return env.get(expr.name)

        if isinstance(expr, BinaryOp):
            l = self.eval_expr(expr.left, env)
            r = self.eval_expr(expr.right, env)
            op = expr.op
            if op == "+":   return l + r
            if op == "-":   return l - r
            if op == "*":   return l * r
            if op == "/":   return int(l / r) if r != 0 else 0
            if op == "%":   return l % r if r != 0 else 0
            if op == "&":   return l & r
            if op == "|":   return l | r
            if op == "^":   return l ^ r
            if op == "<<":  return l << r
            if op == ">>":  return l >> r
            if op == "==":  return 1 if l == r else 0
            if op == "!=":  return 1 if l != r else 0
            if op == "<":   return 1 if l < r else 0
            if op == "<=":  return 1 if l <= r else 0
            if op == ">":   return 1 if l > r else 0
            if op == ">=":  return 1 if l >= r else 0
            if op == "and": return 1 if (l and r) else 0
            if op == "or":  return 1 if (l or r) else 0

        if isinstance(expr, UnaryOp):
            v = self.eval_expr(expr.operand, env)
            if expr.op == "-": return -v
            if expr.op == "~": return ~v
            if expr.op in ("!", "not"): return 1 if not v else 0

        if isinstance(expr, Call):
            callee = env.get(expr.name)
            args = [self.eval_expr(a, env) for a in expr.args]
            if callable(callee):
                return callee(*args)
            if isinstance(callee, AdiFunction):
                return callee.call(self, args)
            raise TypeError(f"'{expr.name}' is not callable")

        return 0
