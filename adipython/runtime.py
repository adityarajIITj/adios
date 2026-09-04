#!/usr/bin/env python3
"""
AdiPython Execution Engine & Ring-0 Hardware Runtime (Deepened Architecture)
Directly executes AST with full hardware MMIO access to memory, framebuffer,
sound, and serial, with Python standard object methods, exceptions, and slicing.

Core Subsystems:
1. Environment lexical scope chains with variable lookup and assignment.
2. Call stack frames, exception unwinding, and traceback generation.
3. Full object method dispatch on strings, lists, and dictionaries:
   - String: split, join, strip, replace, startswith, endswith, upper, lower, find
   - List: append, extend, pop, insert, reverse, sort, count, index, clear, copy
   - Dict: keys, values, items, get, pop, update, setdefault, clear, copy
4. Comprehensive subscripting and Pythonic slicing with step and negative indices.
5. Control flow: If/elif/else, While/else, For/else, Try/except/finally, Assert.
6. Ring-0 Hardware MMIO: peek, poke, pixel, line, rect, circle, clear, tone, sleep.
"""

import sys
import time
import math
from .parser import (
    Program, Assign, AugAssign, FunctionDef, Return, If, While, For,
    ExprStmt, Call, BinaryOp, UnaryOp, Number, String, Identifier,
    Break, Continue, Pass, Global, IfExp, Subscript, Slice,
    Attribute, ListLiteral, DictLiteral, TupleLiteral,
    Try, ExceptHandler, Raise, Assert
)


# =============================================================================
# Runtime Control Signals & Exceptions
# =============================================================================

class ReturnSignal(Exception):
    """Raised when a return statement is executed."""
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    """Raised when a break statement is executed."""
    pass


class ContinueSignal(Exception):
    """Raised when a continue statement is executed."""
    pass


class RaiseSignal(Exception):
    """Raised when an explicit raise statement or runtime error occurs."""
    def __init__(self, exc_val, exc_name: str = "Exception"):
        self.exc_val = exc_val
        self.exc_name = exc_name
        self.traceback = []

    def __repr__(self) -> str:
        return f"{self.exc_name}: {self.exc_val}"


# =============================================================================
# Lexical Scope Environment
# =============================================================================

class Environment:
    """Represents a scoped symbol table with hierarchical parent delegation."""
    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}

    def get(self, name: str):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable '{name}'")

    def set(self, name: str, value):
        """Binds a variable in the local scope."""
        self.vars[name] = value

    def assign(self, name: str, value):
        """Mutates an existing variable in the innermost enclosing scope."""
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent:
            self.parent.assign(name, value)
            return
        self.vars[name] = value


# =============================================================================
# Function & Method Representations
# =============================================================================

class AdiFunction:
    """Represents a user-defined function closure."""
    def __init__(self, func_def: FunctionDef, closure: Environment):
        self.func_def = func_def
        self.closure = closure
        self.name = func_def.name

    def call(self, runtime, args):
        env = Environment(self.closure)
        for param, arg in zip(self.func_def.params, args):
            env.set(param, arg)
        try:
            runtime.push_frame(self.name, self.func_def.lineno)
            runtime.execute_block(self.func_def.body, env)
        except ReturnSignal as ret:
            return ret.value
        finally:
            runtime.pop_frame()
        return 0

    def __repr__(self) -> str:
        return f"<AdiFunction {self.name}({', '.join(self.func_def.params)})>"


class BoundMethod:
    """Wraps a primitive object method invocation."""
    def __init__(self, target, method_name: str, method_fn):
        self.target = target
        self.method_name = method_name
        self.method_fn = method_fn

    def __call__(self, *args, **kwargs):
        return self.method_fn(self.target, *args, **kwargs)

    def __repr__(self) -> str:
        return f"<BoundMethod {self.method_name} of {type(self.target).__name__}>"


# =============================================================================
# Execution Engine & Ring-0 Hardware Runtime
# =============================================================================

class Runtime:
    """
    Core Evaluation Engine for AdiPython.
    Executes AST nodes with hardware acceleration and standard built-in dispatch.
    """
    def __init__(self, vm=None):
        self.vm = vm
        self.global_env = Environment()
        self.call_stack = []
        self._init_builtins()

    def push_frame(self, func_name: str, lineno: int):
        self.call_stack.append((func_name, lineno))

    def pop_frame(self):
        if self.call_stack:
            return self.call_stack.pop()
        return None

    def _init_builtins(self):
        env = self.global_env

        # Ring-0 MMIO Hardware Primitives
        env.set("print", self._builtin_print)
        env.set("peek", self._builtin_peek)
        env.set("poke", self._builtin_poke)
        env.set("pixel", self._builtin_pixel)
        env.set("rect", self._builtin_rect)
        env.set("line", self._builtin_line)
        env.set("circle", self._builtin_circle)
        env.set("fill_circle", self._builtin_fill_circle)
        env.set("clear", self._builtin_clear)
        env.set("cls", self._builtin_clear)
        env.set("tone", self._builtin_tone)
        env.set("sleep", self._builtin_sleep)

        # Standard Mathematical & Sequence Functions
        env.set("len", lambda seq: len(seq))
        env.set("range", lambda *a: list(range(*a)))
        env.set("abs", lambda x: abs(x))
        env.set("min", lambda *a: min(*a) if len(a) > 1 else min(a[0]))
        env.set("max", lambda *a: max(*a) if len(a) > 1 else max(a[0]))
        env.set("sum", lambda seq, start=0: sum(seq, start))
        env.set("round", lambda x, n=0: round(x, n))
        env.set("pow", lambda x, y, z=None: pow(x, y, z) if z is not None else pow(x, y))

        # Iteration Helpers
        env.set("enumerate", lambda seq, start=0: list(enumerate(seq, start)))
        env.set("zip", lambda *seqs: [list(t) for t in zip(*seqs)])
        env.set("reversed", lambda seq: list(reversed(seq)))
        env.set("all", lambda seq: 1 if all(seq) else 0)
        env.set("any", lambda seq: 1 if any(seq) else 0)
        env.set("sorted", lambda seq, reverse=False: sorted(seq, reverse=bool(reverse)))

        # Type Conversions
        env.set("str", lambda x="": str(x))
        env.set("int", lambda x=0, b=10: int(x, b) if isinstance(x, str) else int(x))
        env.set("float", lambda x=0.0: float(x))
        env.set("bool", lambda x=False: 1 if bool(x) else 0)
        env.set("list", lambda x=(): list(x))
        env.set("dict", lambda x=(): dict(x))
        env.set("tuple", lambda x=(): tuple(x))
        env.set("chr", lambda i: chr(int(i)))
        env.set("ord", lambda c: ord(c[0]) if isinstance(c, str) and c else int(c))
        env.set("hex", lambda n: hex(int(n)))
        env.set("bin", lambda n: bin(int(n)))
        env.set("oct", lambda n: oct(int(n)))

        # Standard Color Palette Constants (RGBA 32-bit little endian)
        env.set("BLACK",       0x00000000)
        env.set("WHITE",       0x00FFFFFF)
        env.set("RED",         0x00F7768E)
        env.set("GREEN",       0x009ECE6A)
        env.set("YELLOW",      0x00E0AF68)
        env.set("BLUE",        0x007AA2F7)
        env.set("MAGENTA",     0x00BB9AF7)
        env.set("CYAN",        0x007DCFFF)
        env.set("DARK_GRAY",   0x0024283B)
        env.set("LIGHT_GRAY",  0x00A9B1D6)

    # -------------------------------------------------------------------------
    # Hardware MMIO Built-in Implementations
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
        fb_w = getattr(self.vm, "fb_width", 640) if self.vm else 640
        fb_h = getattr(self.vm, "fb_height", 480) if self.vm else 480
        if 0 <= x < fb_w and 0 <= y < fb_h:
            if self.vm:
                addr = 0x20000000 + (y * fb_w + x) * 4
                self.vm.write32(addr, int(color) & 0xFFFFFFFF)
        return 0

    def _builtin_rect(self, x, y, w, h, color):
        x, y, w, h, color = int(x), int(y), int(w), int(h), int(color)
        if not self.vm:
            return 0
        fb_w = getattr(self.vm, "fb_width", 640)
        fb_h = getattr(self.vm, "fb_height", 480)

        x0 = max(0, min(fb_w - 1, x))
        y0 = max(0, min(fb_h - 1, y))
        x1 = max(0, min(fb_w, x + w))
        y1 = max(0, min(fb_h, y + h))

        fb = self.vm.fb
        c_bytes = bytes([
            color & 0xFF,
            (color >> 8) & 0xFF,
            (color >> 16) & 0xFF,
            (color >> 24) & 0xFF
        ])
        row_bytes = c_bytes * (x1 - x0)

        for cy in range(y0, y1):
            offset = (cy * fb_w + x0) * 4
            fb[offset : offset + len(row_bytes)] = row_bytes
        return 0

    def _builtin_line(self, x0, y0, x1, y1, color):
        """Bresenham 2D Line Rasterizer."""
        x0, y0, x1, y1, color = int(x0), int(y0), int(x1), int(y1), int(color)
        if not self.vm:
            return 0
        fb_w = getattr(self.vm, "fb_width", 640)
        fb_h = getattr(self.vm, "fb_height", 480)

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        c_bytes = bytes([
            color & 0xFF,
            (color >> 8) & 0xFF,
            (color >> 16) & 0xFF,
            (color >> 24) & 0xFF
        ])

        while True:
            if 0 <= x0 < fb_w and 0 <= y0 < fb_h:
                off = (y0 * fb_w + x0) * 4
                self.vm.fb[off : off + 4] = c_bytes

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

    def _builtin_circle(self, cx, cy, r, color):
        """Midpoint Circle Drawing Algorithm."""
        cx, cy, r, color = int(cx), int(cy), int(r), int(color)
        x = 0
        y = r
        d = 1 - r

        def plot8(px, py):
            self._builtin_pixel(cx + px, cy + py, color)
            self._builtin_pixel(cx - px, cy + py, color)
            self._builtin_pixel(cx + px, cy - py, color)
            self._builtin_pixel(cx - px, cy - py, color)
            self._builtin_pixel(cx + py, cy + px, color)
            self._builtin_pixel(cx - py, cy + px, color)
            self._builtin_pixel(cx + py, cy - px, color)
            self._builtin_pixel(cx - py, cy - px, color)

        plot8(x, y)
        while x < y:
            x += 1
            if d < 0:
                d += 2 * x + 1
            else:
                y -= 1
                d += 2 * (x - y) + 1
            plot8(x, y)
        return 0

    def _builtin_fill_circle(self, cx, cy, r, color):
        """Filled Circle Rasterizer using horizontal scanlines."""
        cx, cy, r, color = int(cx), int(cy), int(r), int(color)
        for dy in range(-r, r + 1):
            dx = int(math.isqrt(r * r - dy * dy))
            self._builtin_line(cx - dx, cy + dy, cx + dx, cy + dy, color)
        return 0

    def _builtin_clear(self, color=0x001A1B26):
        if self.vm:
            fb_w = getattr(self.vm, "fb_width", 640)
            fb_h = getattr(self.vm, "fb_height", 480)
            c = int(color)
            c_bytes = bytes([
                c & 0xFF,
                (c >> 8) & 0xFF,
                (c >> 16) & 0xFF,
                (c >> 24) & 0xFF
            ])
            self.vm.fb[:] = c_bytes * (fb_w * fb_h)
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
    # Primitive Object Method Dispatch Table
    # -------------------------------------------------------------------------
    def dispatch_method(self, target, method_name: str):
        """Resolves built-in methods on strings, lists, and dicts."""
        if isinstance(target, str):
            str_methods = {
                "split": lambda s, sep=None, maxsplit=-1: s.split(sep, maxsplit),
                "join": lambda s, iterable: s.join(str(x) for x in iterable),
                "strip": lambda s, chars=None: s.strip(chars),
                "lstrip": lambda s, chars=None: s.lstrip(chars),
                "rstrip": lambda s, chars=None: s.rstrip(chars),
                "replace": lambda s, old, new, count=-1: s.replace(old, new, count),
                "startswith": lambda s, prefix: 1 if s.startswith(prefix) else 0,
                "endswith": lambda s, suffix: 1 if s.endswith(suffix) else 0,
                "find": lambda s, sub, start=0: s.find(sub, start),
                "index": lambda s, sub: s.index(sub),
                "upper": lambda s: s.upper(),
                "lower": lambda s: s.lower(),
                "title": lambda s: s.title(),
                "capitalize": lambda s: s.capitalize(),
                "isdigit": lambda s: 1 if s.isdigit() else 0,
                "isalpha": lambda s: 1 if s.isalpha() else 0,
                "isalnum": lambda s: 1 if s.isalnum() else 0,
                "isspace": lambda s: 1 if s.isspace() else 0,
                "count": lambda s, sub: s.count(sub),
            }
            if method_name in str_methods:
                return BoundMethod(target, method_name, str_methods[method_name])

        elif isinstance(target, list):
            list_methods = {
                "append": lambda lst, x: (lst.append(x) or 0),
                "extend": lambda lst, iterable: (lst.extend(iterable) or 0),
                "pop": lambda lst, idx=-1: lst.pop(idx),
                "insert": lambda lst, idx, x: (lst.insert(idx, x) or 0),
                "remove": lambda lst, x: (lst.remove(x) or 0),
                "reverse": lambda lst: (lst.reverse() or 0),
                "sort": lambda lst, reverse=False: (lst.sort(reverse=bool(reverse)) or 0),
                "count": lambda lst, x: lst.count(x),
                "index": lambda lst, x: lst.index(x),
                "clear": lambda lst: (lst.clear() or 0),
                "copy": lambda lst: list(lst),
            }
            if method_name in list_methods:
                return BoundMethod(target, method_name, list_methods[method_name])

        elif isinstance(target, dict):
            dict_methods = {
                "keys": lambda d: list(d.keys()),
                "values": lambda d: list(d.values()),
                "items": lambda d: [list(item) for item in d.items()],
                "get": lambda d, k, default=None: d.get(k, default),
                "pop": lambda d, k, default=None: d.pop(k, default),
                "update": lambda d, other: (d.update(other) or 0),
                "setdefault": lambda d, k, default=None: d.setdefault(k, default),
                "clear": lambda d: (d.clear() or 0),
                "copy": lambda d: dict(d),
            }
            if method_name in dict_methods:
                return BoundMethod(target, method_name, dict_methods[method_name])

        raise AttributeError(f"'{type(target).__name__}' object has no attribute '{method_name}'")

    # -------------------------------------------------------------------------
    # AST Evaluation Dispatcher
    # -------------------------------------------------------------------------
    def run(self, node, env=None):
        if env is None:
            env = self.global_env

        if isinstance(node, Program):
            res = None
            for stmt in node.stmts:
                res = self.run(stmt, env)
            return res

        if isinstance(node, FunctionDef):
            func = AdiFunction(node, env)
            env.set(node.name, func)
            return func

        if isinstance(node, Assign):
            val = self.eval_expr(node.value, env)
            if isinstance(node.target, str):
                env.assign(node.target, val)
            elif isinstance(node.target, Subscript):
                self.eval_subscript_assign(node.target, val, env)
            elif isinstance(node.target, Attribute):
                obj = self.eval_expr(node.target.value, env)
                if isinstance(obj, dict):
                    obj[node.target.attr] = val
                else:
                    setattr(obj, node.target.attr, val)
            return val

        if isinstance(node, AugAssign):
            val = self.eval_expr(node.value, env)
            if isinstance(node.target, str):
                old = env.get(node.target)
                new_val = self._apply_binary_op(node.op, old, val)
                env.assign(node.target, new_val)
                return new_val
            elif isinstance(node.target, Subscript):
                obj = self.eval_expr(node.target.value, env)
                idx = self.eval_expr(node.target.slice, env)
                old = obj[idx]
                new_val = self._apply_binary_op(node.op, old, val)
                obj[idx] = new_val
                return new_val
            elif isinstance(node.target, Attribute):
                obj = self.eval_expr(node.target.value, env)
                old = obj.get(node.target.attr) if isinstance(obj, dict) else getattr(obj, node.target.attr)
                new_val = self._apply_binary_op(node.op, old, val)
                if isinstance(obj, dict):
                    obj[node.target.attr] = new_val
                else:
                    setattr(obj, node.target.attr, new_val)
                return new_val

        if isinstance(node, Return):
            val = self.eval_expr(node.value, env) if node.value is not None else 0
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
            broke = False
            while self.eval_expr(node.cond, env):
                try:
                    self.execute_block(node.body, env)
                except BreakSignal:
                    broke = True
                    break
                except ContinueSignal:
                    continue
            if not broke and node.else_body:
                return self.execute_block(node.else_body, env)
            return None

        if isinstance(node, For):
            broke = False
            if node.iter_expr is not None:
                iterable = self.eval_expr(node.iter_expr, env)
            else:
                start = self.eval_expr(node.start, env)
                end = self.eval_expr(node.end, env)
                step = self.eval_expr(node.step, env)
                iterable = range(start, end, step)

            for item in iterable:
                env.set(node.var, item)
                try:
                    self.execute_block(node.body, env)
                except BreakSignal:
                    broke = True
                    break
                except ContinueSignal:
                    continue

            if not broke and node.else_body:
                return self.execute_block(node.else_body, env)
            return None

        if isinstance(node, Try):
            try:
                res = self.execute_block(node.body, env)
                if node.else_body:
                    res = self.execute_block(node.else_body, env)
                return res
            except Exception as e:
                # Handle ReturnSignal, BreakSignal, ContinueSignal by re-raising unless finally applies
                if isinstance(e, (ReturnSignal, BreakSignal, ContinueSignal)):
                    raise e
                handled = False
                for handler in node.handlers:
                    if handler.exc_type is None or handler.exc_type in (type(e).__name__, "Exception"):
                        if handler.name:
                            env.set(handler.name, e)
                        res = self.execute_block(handler.body, env)
                        handled = True
                        break
                if not handled:
                    raise e
            finally:
                if node.finalbody:
                    self.execute_block(node.finalbody, env)
            return None

        if isinstance(node, Raise):
            exc = self.eval_expr(node.exc, env) if node.exc else "RuntimeError"
            raise RaiseSignal(exc)

        if isinstance(node, Assert):
            cond = self.eval_expr(node.test, env)
            if not cond:
                msg = self.eval_expr(node.msg, env) if node.msg else "Assertion failed"
                raise AssertionError(str(msg))
            return 1

        if isinstance(node, Break):
            raise BreakSignal()

        if isinstance(node, Continue):
            raise ContinueSignal()

        if isinstance(node, Pass):
            return None

        if isinstance(node, Global):
            return None

        if isinstance(node, ExprStmt):
            return self.eval_expr(node.expr, env)

        return None

    def execute_block(self, stmts, env):
        res = None
        for stmt in stmts:
            res = self.run(stmt, env)
        return res

    def eval_subscript_assign(self, node: Subscript, val, env):
        obj = self.eval_expr(node.value, env)
        if isinstance(node.slice, Slice):
            lower = self.eval_expr(node.slice.lower, env) if node.slice.lower else None
            upper = self.eval_expr(node.slice.upper, env) if node.slice.upper else None
            step = self.eval_expr(node.slice.step, env) if node.slice.step else None
            obj[slice(lower, upper, step)] = val
        else:
            idx = self.eval_expr(node.slice, env)
            obj[idx] = val

    def eval_expr(self, expr, env):
        if isinstance(expr, Number):
            return expr.value
        if isinstance(expr, String):
            return expr.value
        if isinstance(expr, Identifier):
            return env.get(expr.name)

        if isinstance(expr, IfExp):
            cond = self.eval_expr(expr.cond, env)
            return self.eval_expr(expr.body, env) if cond else self.eval_expr(expr.orelse, env)

        if isinstance(expr, ListLiteral):
            return [self.eval_expr(e, env) for e in expr.elements]

        if isinstance(expr, DictLiteral):
            return {self.eval_expr(k, env): self.eval_expr(v, env)
                    for k, v in zip(expr.keys, expr.values)}

        if isinstance(expr, TupleLiteral):
            return tuple(self.eval_expr(e, env) for e in expr.elements)

        if isinstance(expr, Subscript):
            target = self.eval_expr(expr.value, env)
            if isinstance(expr.slice, Slice):
                lower = self.eval_expr(expr.slice.lower, env) if expr.slice.lower else None
                upper = self.eval_expr(expr.slice.upper, env) if expr.slice.upper else None
                step = self.eval_expr(expr.slice.step, env) if expr.slice.step else None
                return target[slice(lower, upper, step)]
            idx = self.eval_expr(expr.slice, env)
            return target[idx]

        if isinstance(expr, Attribute):
            target = self.eval_expr(expr.value, env)
            if isinstance(target, (str, list, dict)):
                return self.dispatch_method(target, expr.attr)
            if hasattr(target, expr.attr):
                val = getattr(target, expr.attr)
                return val
            if isinstance(target, dict) and expr.attr in target:
                return target[expr.attr]
            raise AttributeError(f"'{type(target).__name__}' object has no attribute '{expr.attr}'")

        if isinstance(expr, BinaryOp):
            l = self.eval_expr(expr.left, env)
            # Short-circuit logical evaluation
            if expr.op == "and":
                return self.eval_expr(expr.right, env) if l else 0
            if expr.op == "or":
                return l if l else self.eval_expr(expr.right, env)

            r = self.eval_expr(expr.right, env)
            return self._apply_binary_op(expr.op, l, r)

        if isinstance(expr, UnaryOp):
            v = self.eval_expr(expr.operand, env)
            if expr.op == "-":   return -v
            if expr.op == "+":   return +v
            if expr.op == "~":   return ~v
            if expr.op in ("!", "not"): return 1 if not v else 0
            return v

        if isinstance(expr, Call):
            # Target can be a string name or a dynamic callable expression
            if isinstance(expr.name, str):
                callee = env.get(expr.name)
            else:
                callee = self.eval_expr(expr.name, env)

            args = [self.eval_expr(a, env) for a in expr.args]
            if callable(callee):
                return callee(*args)
            if isinstance(callee, AdiFunction):
                return callee.call(self, args)
            raise TypeError(f"'{expr.name}' object is not callable")

        return 0

    def _apply_binary_op(self, op: str, l, r):
        """Applies binary operations with type conversions and zero-division protection."""
        if op in ("+", "+="):   return l + r
        if op in ("-", "-="):   return l - r
        if op in ("*", "*="):   return l * r
        if op in ("/", "/="):
            if r == 0:
                raise ZeroDivisionError("division by zero")
            return int(l / r)
        if op in ("//", "//="):
            if r == 0:
                raise ZeroDivisionError("integer division by zero")
            return l // r
        if op in ("%", "%="):
            if r == 0:
                raise ZeroDivisionError("integer modulo by zero")
            return l % r
        if op in ("**", "**="): return l ** r
        if op in ("&", "&="):   return int(l) & int(r)
        if op in ("|", "|="):   return int(l) | int(r)
        if op in ("^", "^="):   return int(l) ^ int(r)
        if op in ("<<", "<<="): return int(l) << int(r)
        if op in (">>", ">>="): return int(l) >> int(r)
        if op == "==":  return 1 if l == r else 0
        if op == "!=":  return 1 if l != r else 0
        if op == "<":   return 1 if l < r else 0
        if op == "<=":  return 1 if l <= r else 0
        if op == ">":   return 1 if l > r else 0
        if op == ">=":  return 1 if l >= r else 0
        if op == "in":  return 1 if l in r else 0
        if op == "is":  return 1 if l is r else 0
        return 0
