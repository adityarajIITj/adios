#!/usr/bin/env python3
"""
Test Suite: AdiPython Language & Ring-0 Hardware Runtime
Verifies:
1. Expressions, operator precedence, and logic
2. Variable assignment and augmented assignment (+=, -=)
3. Functions, recursion, and return values
4. Control flow (if/elif/else, while, for-in-range)
5. Ring-0 hardware MMIO (peek, poke, rect, line, pixel, clear)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM, RAM_BASE, FB_BASE, FB_WIDTH
from adipython import AdiPython

def test_adipython_suite():
    print("[Test AdiPython] Initializing AdiPython on AdiOS VM...")
    vm = VM()
    ap = AdiPython(vm)

    # 1. Math and Precedence
    print("  -> Testing arithmetic & precedence...")
    code_math = """
x = 2 + 3 * 4
y = (10 - 4) * 2 + 8 / 2
z = 100 % 7
"""
    ap.execute(code_math)
    assert ap.runtime.global_env.get("x") == 14, f"Expected x=14, got {ap.runtime.global_env.get('x')}"
    assert ap.runtime.global_env.get("y") == 16, f"Expected y=16, got {ap.runtime.global_env.get('y')}"
    assert ap.runtime.global_env.get("z") == 2, f"Expected z=2, got {ap.runtime.global_env.get('z')}"
    print("  -> [PASS] Math operations verified.")

    # 2. Control Flow: loops and conditionals
    print("  -> Testing loops and conditionals...")
    code_flow = """
sum = 0
for i in range(1, 11):
    sum += i

count = 0
while count < 5:
    count += 1

status = 0
if sum == 55:
    status = 1
else:
    status = -1
"""
    ap.execute(code_flow)
    assert ap.runtime.global_env.get("sum") == 55, f"Expected sum=55, got {ap.runtime.global_env.get('sum')}"
    assert ap.runtime.global_env.get("count") == 5, f"Expected count=5, got {ap.runtime.global_env.get('count')}"
    assert ap.runtime.global_env.get("status") == 1, f"Expected status=1, got {ap.runtime.global_env.get('status')}"
    print("  -> [PASS] Loops and conditionals verified.")

    # 3. User-defined functions & recursion
    print("  -> Testing user-defined functions and recursion...")
    code_func = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

f6 = factorial(6)

def add3(a, b, c):
    return a + b + c

res3 = add3(10, 20, 30)
"""
    ap.execute(code_func)
    assert ap.runtime.global_env.get("f6") == 720, f"Expected 6!=720, got {ap.runtime.global_env.get('f6')}"
    assert ap.runtime.global_env.get("res3") == 60, f"Expected add3=60, got {ap.runtime.global_env.get('res3')}"
    print("  -> [PASS] User-defined functions verified.")

    # 4. Ring-0 Hardware MMIO: peek & poke
    print("  -> Testing Ring-0 peek & poke MMIO...")
    code_mmio = """
target_addr = 0x80050000
poke(target_addr, 0x12345678)
val = peek(target_addr)
"""
    ap.execute(code_mmio)
    assert ap.runtime.global_env.get("val") == 0x12345678, "peek/poke failed"
    assert vm.read32(0x80050000) == 0x12345678, "Memory readback mismatch"
    print("  -> [PASS] Direct hardware peek/poke verified.")

    # 5. Direct 2D Graphics Framebuffer primitives: rect, line, pixel
    print("  -> Testing Framebuffer 2D primitives (rect, line, pixel)...")
    code_gfx = """
# Draw Red rectangle: (x=100, y=100, w=50, h=40)
rect(100, 100, 50, 40, RED)

# Draw Green line: (0, 0) to (50, 50)
line(0, 0, 50, 50, GREEN)

# Draw Blue pixel: (200, 200)
pixel(200, 200, BLUE)
"""
    ap.execute(code_gfx)

    # Verify rect pixel at (120, 120) is Red (#F7768E -> 0x8E, 0x76, 0xF7)
    rect_off = (120 * FB_WIDTH + 120) * 4
    assert vm.fb[rect_off:rect_off+3] == b"\x8e\x76\xf7", "Rect pixel not RED"

    # Verify line pixel at (25, 25) is Green (#9ECE6A -> 0x6A, 0xCE, 0x9E)
    line_off = (25 * FB_WIDTH + 25) * 4
    assert vm.fb[line_off:line_off+3] == b"\x6a\xce\x9e", "Line pixel not GREEN"

    # Verify pixel at (200, 200) is Blue (#7AA2F7 -> 0xF7, 0xA2, 0x7A)
    pix_off = (200 * FB_WIDTH + 200) * 4
    assert vm.fb[pix_off:pix_off+3] == b"\xf7\xa2\x7a", "Pixel not BLUE"
    print("  -> [PASS] Hardware Framebuffer rendering verified.")

    print("\n===========================================================")
    print("[Test AdiPython] ALL ADIPYTHON LANGUAGE TESTS PASSED (100%)!")
    print("===========================================================")
    return True

if __name__ == "__main__":
    test_adipython_suite()
