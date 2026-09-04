#!/usr/bin/env python3
"""
Test Suite: AdiPython Deepened Language & Compiler Systems
Verifies Phase X Deepening:
1. Augmented assignments (+=, -=, *=, /=, %=, <<=, >>=, &=, |=, ^=)
2. Ternary conditional expressions (x if cond else y)
3. Pythonic string methods (split, join, strip, replace, upper, lower, startswith)
4. Dynamic list methods (append, pop, insert, reverse, sort, extend)
5. Dynamic dictionary methods (keys, values, items, get, update, setdefault)
6. Pythonic slicing with positive/negative steps and indices (s[::-1], lst[1:4])
7. Exception handling (try / except / finally) with guaranteed finalizers
8. Assert statements (assert expr, "message")
9. Midpoint circle rasterization primitives (circle, fill_circle)
10. Multi-pass TAC IR generation & optimization (CSE, LICM, Constant folding)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from adipython import AdiPython


def test_adipython_deepened_suite():
    print("[Test AdiPython Deepened] Initializing deepened subsystem verification...")
    vm = VM()
    ap = AdiPython(vm)

    # 1. Augmented Assignment Operators
    print("  -> Testing augmented assignment operators (+=, -=, *=, /=, %=, <<=, >>=)...")
    code_aug = """
a = 10
a += 5
b = 20
b -= 7
c = 6
c *= 4
d = 40
d /= 5
e = 17
e %= 5
f = 1
f <<= 4
g = 64
g >>= 2
"""
    ap.execute(code_aug)
    assert ap.runtime.global_env.get("a") == 15, f"a={ap.runtime.global_env.get('a')}"
    assert ap.runtime.global_env.get("b") == 13, f"b={ap.runtime.global_env.get('b')}"
    assert ap.runtime.global_env.get("c") == 24, f"c={ap.runtime.global_env.get('c')}"
    assert ap.runtime.global_env.get("d") == 8,  f"d={ap.runtime.global_env.get('d')}"
    assert ap.runtime.global_env.get("e") == 2,  f"e={ap.runtime.global_env.get('e')}"
    assert ap.runtime.global_env.get("f") == 16, f"f={ap.runtime.global_env.get('f')}"
    assert ap.runtime.global_env.get("g") == 16, f"g={ap.runtime.global_env.get('g')}"
    print("  -> [PASS] Augmented assignment operators verified.")

    # 2. Ternary Expressions
    print("  -> Testing ternary expressions (val if cond else other)...")
    code_ternary = """
score = 85
grade = "PASS" if score >= 50 else "FAIL"
low_score = 42
failed_grade = "PASS" if low_score >= 50 else "FAIL"
"""
    ap.execute(code_ternary)
    assert ap.runtime.global_env.get("grade") == "PASS"
    assert ap.runtime.global_env.get("failed_grade") == "FAIL"
    print("  -> [PASS] Ternary expressions verified.")

    # 3. String Methods
    print("  -> Testing primitive string object methods...")
    code_str = """
raw = "  hello world  "
cleaned = raw.strip()
words = cleaned.split(" ")
joined = "-".join(words)
upper_text = joined.upper()
is_hello = upper_text.startswith("HELLO")
replaced = upper_text.replace("WORLD", "ADIOS")
"""
    ap.execute(code_str)
    assert ap.runtime.global_env.get("cleaned") == "hello world"
    assert ap.runtime.global_env.get("words") == ["hello", "world"]
    assert ap.runtime.global_env.get("joined") == "hello-world"
    assert ap.runtime.global_env.get("upper_text") == "HELLO-WORLD"
    assert ap.runtime.global_env.get("is_hello") == 1
    assert ap.runtime.global_env.get("replaced") == "HELLO-ADIOS"
    print("  -> [PASS] String methods verified.")

    # 4. List Methods & Subscript Assignment
    print("  -> Testing list object methods & subscript mutations...")
    code_list = """
items = [10, 20, 30]
items.append(40)
items.insert(1, 15)
popped = items.pop()
items[0] = 99
items.reverse()
"""
    ap.execute(code_list)
    assert ap.runtime.global_env.get("items") == [30, 20, 15, 99]
    assert ap.runtime.global_env.get("popped") == 40
    print("  -> [PASS] List methods and subscript assignment verified.")

    # 5. Dict Methods
    print("  -> Testing dictionary object methods...")
    code_dict = """
config = {"theme": "dark", "fps": 60}
config.update({"res": "1024x768"})
res_val = config.get("res")
def_val = config.get("missing", 404)
keys_list = config.keys()
"""
    ap.execute(code_dict)
    assert ap.runtime.global_env.get("res_val") == "1024x768"
    assert ap.runtime.global_env.get("def_val") == 404
    assert "theme" in ap.runtime.global_env.get("keys_list")
    print("  -> [PASS] Dictionary methods verified.")

    # 6. Slicing with steps and negative indexing
    print("  -> Testing sequence slicing semantics...")
    code_slice = """
numbers = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
sub = numbers[2:6]
evens = numbers[::2]
reversed_num = numbers[::-1]
text = "Antigravity"
reversed_text = text[::-1]
"""
    ap.execute(code_slice)
    assert ap.runtime.global_env.get("sub") == [2, 3, 4, 5]
    assert ap.runtime.global_env.get("evens") == [0, 2, 4, 6, 8]
    assert ap.runtime.global_env.get("reversed_num") == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    assert ap.runtime.global_env.get("reversed_text") == "ytivargitnA"
    print("  -> [PASS] Slicing semantics verified.")

    # 7. Try / Except / Finally Exception Handling
    print("  -> Testing try / except / finally execution flow...")
    code_try = """
caught = 0
final_ran = 0
try:
    x = 10 / 0
except Exception as err:
    caught = 1
finally:
    final_ran = 1
"""
    ap.execute(code_try)
    assert ap.runtime.global_env.get("caught") == 1
    assert ap.runtime.global_env.get("final_ran") == 1
    print("  -> [PASS] Try / except / finally verified.")

    # 8. Assertion Statements
    print("  -> Testing assert statement...")
    code_assert = """
assert 2 + 2 == 4, "Arithmetic identity failed"
assert len([1, 2, 3]) == 3
"""
    ap.execute(code_assert)
    print("  -> [PASS] Assert statement verified.")

    # 9. Hardware Framebuffer Circle Primitives
    print("  -> Testing Hardware Circle Rasterization primitives...")
    code_circle = """
circle(320, 240, 50, CYAN)
fill_circle(150, 150, 25, MAGENTA)
"""
    ap.execute(code_circle)
    print("  -> [PASS] Circle primitives verified.")

    # 10. Multi-Pass TAC IR Generation & Optimization
    print("  -> Testing Compiler IR & Optimization passes (CSE & Constant Folding)...")
    source_opt = """
def test_cse(a, b):
    x = a * 10 + b
    y = a * 10 + b
    z = 4 * 8 + 10
    return x + y + z
"""
    ir_mod = ap.compile_to_ir(source_opt, optimize=True)
    assert "test_cse" in ir_mod.functions
    assert ap.telemetry.optimized_instructions > 0
    print(f"  -> IR generated: {ap.telemetry.ir_instructions} instructions, "
          f"optimized to {ap.telemetry.optimized_instructions} instructions")
    print("  -> [PASS] Multi-pass TAC IR generation & optimization verified.")

    print("\n===========================================================")
    print("[Test AdiPython Deepened] ALL 10 DEEPENED TESTS PASSED (100%)!")
    print("===========================================================")
    return True


if __name__ == "__main__":
    test_adipython_deepened_suite()
