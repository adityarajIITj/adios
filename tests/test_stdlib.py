#!/usr/bin/env python3
"""
Test Suite: AdiPython Standard Library
Verifies:
1. math.ap: Integer square root, trigonometry, 3D vector math
2. mem.ap: Memory block copying, fill, comparison, heap malloc
3. collections.ap: Dynamic arrays and circular queues
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from adipython import AdiPython

def test_stdlib_suite():
    print("[Test Stdlib] Testing AdiPython Standard Library Modules...")
    vm = VM()
    ap = AdiPython(vm)

    # 1. Test math.ap
    print("  -> Testing math.ap (isqrt, trigonometry, 3D vectors)...")
    code_math = """
#include "adipython/stdlib/math.ap"

s144 = isqrt(144)
s100 = isqrt(100)
s25  = isqrt(25)

sin90 = sin_deg(90)
cos0  = cos_deg(0)

d345 = vec3_dist(0, 0, 0, 3, 4, 0)
"""
    ap.execute(code_math)
    assert ap.runtime.global_env.get("s144") == 12, f"isqrt(144) failed: {ap.runtime.global_env.get('s144')}"
    assert ap.runtime.global_env.get("s100") == 10, f"isqrt(100) failed: {ap.runtime.global_env.get('s100')}"
    assert ap.runtime.global_env.get("s25") == 5, f"isqrt(25) failed: {ap.runtime.global_env.get('s25')}"
    assert ap.runtime.global_env.get("sin90") == 256, f"sin_deg(90) failed: {ap.runtime.global_env.get('sin90')}"
    assert ap.runtime.global_env.get("cos0") == 256, f"cos_deg(0) failed: {ap.runtime.global_env.get('cos0')}"
    assert ap.runtime.global_env.get("d345") == 5, f"vec3_dist failed: {ap.runtime.global_env.get('d345')}"
    print("  -> [PASS] math.ap verified.")

    # 2. Test mem.ap
    print("  -> Testing mem.ap (memset32, memcpy32, memcmp32, malloc)...")
    code_mem = """
#include "adipython/stdlib/mem.ap"

# Test Malloc
buf1 = malloc(64)
buf2 = malloc(64)

# Test Memset
memset32(buf1, 0x11223344, 16)
val1 = peek(buf1)

# Test Memcpy
memcpy32(buf2, buf1, 16)
val2 = peek(buf2)

# Test Memcmp
cmp_res = memcmp32(buf1, buf2, 16)
"""
    ap.execute(code_mem)
    assert ap.runtime.global_env.get("val1") == 0x11223344, "memset failed"
    assert ap.runtime.global_env.get("val2") == 0x11223344, "memcpy failed"
    assert ap.runtime.global_env.get("cmp_res") == 0, "memcmp failed"
    print("  -> [PASS] mem.ap verified.")

    # 3. Test collections.ap
    print("  -> Testing collections.ap (dynamic arrays and circular queues)...")
    code_coll = """
#include "adipython/stdlib/mem.ap"
#include "adipython/stdlib/collections.ap"

# Test Dynamic Array
arr = array_create(10)
array_push(arr, 100)
array_push(arr, 200)
array_push(arr, 300)

a_len = array_len(arr)
e1 = array_get(arr, 1)
popped = array_pop(arr)
new_len = array_len(arr)

# Test Circular Queue
q = queue_create(8)
queue_enqueue(q, 42)
queue_enqueue(q, 99)
q_cnt = queue_count(q)
q_item1 = queue_dequeue(q)
q_cnt_after = queue_count(q)
"""
    ap.execute(code_coll)
    assert ap.runtime.global_env.get("a_len") == 3, f"array_len failed: {ap.runtime.global_env.get('a_len')}"
    assert ap.runtime.global_env.get("e1") == 200, f"array_get failed: {ap.runtime.global_env.get('e1')}"
    assert ap.runtime.global_env.get("popped") == 300, f"array_pop failed: {ap.runtime.global_env.get('popped')}"
    assert ap.runtime.global_env.get("new_len") == 2, f"new_len failed: {ap.runtime.global_env.get('new_len')}"

    assert ap.runtime.global_env.get("q_cnt") == 2, f"queue_count failed: {ap.runtime.global_env.get('q_cnt')}"
    assert ap.runtime.global_env.get("q_item1") == 42, f"queue_dequeue failed: {ap.runtime.global_env.get('q_item1')}"
    assert ap.runtime.global_env.get("q_cnt_after") == 1, f"queue_count after failed: {ap.runtime.global_env.get('q_cnt_after')}"
    print("  -> [PASS] collections.ap verified.")

    print("\n[Test Stdlib] ALL ADIPYTHON STDLIB TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_stdlib_suite()
