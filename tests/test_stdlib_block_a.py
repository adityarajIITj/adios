#!/usr/bin/env python3
"""
Test Suite: Block A Systems Standard Library
Verifies:
1. Self-Balancing Binary Search Trees (trees.ap)
2. Open-Addressed Hash Table (hashmap.ap)
3. Binary Min-Heap Priority Queue (heap.ap)
4. 4x4 Matrix Transformations & Vectors (matrix3d.ap)
5. Slab Allocator & Arena Memory Pools (memory_pool.ap)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from adipython import AdiPython

def test_block_a_suite():
    print("[Test Block A] Initializing Systems Standard Library Verification...")
    vm = VM()
    ap = AdiPython(vm)

    # 1. Test Self-Balancing BST (trees.ap)
    print("  -> Testing Balanced Binary Search Trees (trees.ap)...")
    code_trees = """
#include "adipython/stdlib/mem.ap"
#include "adipython/stdlib/trees.ap"

root = 0
root = bst_insert(root, 30, 300)
root = bst_insert(root, 20, 200)
root = bst_insert(root, 40, 400)
root = bst_insert(root, 10, 100)
root = bst_insert(root, 25, 250)

v30 = bst_search(root, 30)
v25 = bst_search(root, 25)
c40 = bst_contains(root, 40)
c99 = bst_contains(root, 99)
t_count = bst_count(root)
"""
    ap.execute(code_trees)
    assert ap.runtime.global_env.get("v30") == 300, f"bst_search(30) failed: {ap.runtime.global_env.get('v30')}"
    assert ap.runtime.global_env.get("v25") == 250, f"bst_search(25) failed: {ap.runtime.global_env.get('v25')}"
    assert ap.runtime.global_env.get("c40") == 1, "bst_contains(40) failed"
    assert ap.runtime.global_env.get("c99") == 0, "bst_contains(99) failed"
    assert ap.runtime.global_env.get("t_count") == 5, f"bst_count failed: {ap.runtime.global_env.get('t_count')}"
    print("  -> [PASS] trees.ap verified.")

    # 2. Test HashMap (hashmap.ap)
    print("  -> Testing High-Performance Hash Table (hashmap.ap)...")
    code_hashmap = """
#include "adipython/stdlib/mem.ap"
#include "adipython/stdlib/hashmap.ap"

hm = hashmap_create(16)
hashmap_put(hm, 101, 777)
hashmap_put(hm, 202, 888)
hashmap_put(hm, 303, 999)

val101 = hashmap_get(hm, 101)
val202 = hashmap_get(hm, 202)
val303 = hashmap_get(hm, 303)
hm_cnt = hashmap_count(hm)
has101 = hashmap_contains(hm, 101)
has404 = hashmap_contains(hm, 404)
"""
    ap.execute(code_hashmap)
    assert ap.runtime.global_env.get("val101") == 777, f"hashmap_get(101) failed"
    assert ap.runtime.global_env.get("val202") == 888, f"hashmap_get(202) failed"
    assert ap.runtime.global_env.get("val303") == 999, f"hashmap_get(303) failed"
    assert ap.runtime.global_env.get("hm_cnt") == 3, f"hashmap_count failed"
    assert ap.runtime.global_env.get("has101") == 1, f"has101 failed"
    assert ap.runtime.global_env.get("has404") == 0, f"has404 failed"
    print("  -> [PASS] hashmap.ap verified.")

    # 3. Test Binary Min-Heap Priority Queue (heap.ap)
    print("  -> Testing Binary Min-Heap Priority Queue (heap.ap)...")
    code_heap = """
#include "adipython/stdlib/mem.ap"
#include "adipython/stdlib/heap.ap"

h = heap_create(16)
heap_push(h, 50, 5000)
heap_push(h, 10, 1000)
heap_push(h, 30, 3000)
heap_push(h, 20, 2000)

p_min = heap_peek_min(h)
pop1 = heap_pop_min(h) # should be 1000 (priority 10)
pop2 = heap_pop_min(h) # should be 2000 (priority 20)
pop3 = heap_pop_min(h) # should be 3000 (priority 30)
pop4 = heap_pop_min(h) # should be 5000 (priority 50)
h_rem = heap_size(h)
"""
    ap.execute(code_heap)
    assert ap.runtime.global_env.get("p_min") == 1000, f"heap_peek_min failed"
    assert ap.runtime.global_env.get("pop1") == 1000, f"pop1 expected 1000, got {ap.runtime.global_env.get('pop1')}"
    assert ap.runtime.global_env.get("pop2") == 2000, f"pop2 expected 2000, got {ap.runtime.global_env.get('pop2')}"
    assert ap.runtime.global_env.get("pop3") == 3000, f"pop3 expected 3000, got {ap.runtime.global_env.get('pop3')}"
    assert ap.runtime.global_env.get("pop4") == 5000, f"pop4 expected 5000, got {ap.runtime.global_env.get('pop4')}"
    assert ap.runtime.global_env.get("h_rem") == 0, f"heap_size remaining failed"
    print("  -> [PASS] heap.ap verified.")

    # 4. Test 4x4 Matrix Transformations (matrix3d.ap)
    print("  -> Testing 4x4 Matrix Mathematics (matrix3d.ap)...")
    code_matrix = """
#include "adipython/stdlib/mem.ap"
#include "adipython/stdlib/math.ap"
#include "adipython/stdlib/matrix3d.ap"

m_ident = mat4_create_identity()
diag0 = mat4_get(m_ident, 0, 0)
diag3 = mat4_get(m_ident, 3, 3)

# Test Translation
m_trans = mat4_create_translation(10, 20, 30)
tx_val = mat4_get(m_trans, 0, 3) # should be 10 * 256 = 2560

# Test Vector Transform
x_res = mat4_transform_vec3(m_trans, 5, 5, 5)
y_res = mat4_transformed_y()
z_res = mat4_transformed_z()
"""
    ap.execute(code_matrix)
    assert ap.runtime.global_env.get("diag0") == 256, "Identity matrix diagonal failed"
    assert ap.runtime.global_env.get("diag3") == 256, "Identity matrix diagonal failed"
    assert ap.runtime.global_env.get("tx_val") == 2560, "Translation matrix failed"
    assert ap.runtime.global_env.get("x_res") == 15, f"Vector transform X failed: {ap.runtime.global_env.get('x_res')}"
    assert ap.runtime.global_env.get("y_res") == 25, f"Vector transform Y failed: {ap.runtime.global_env.get('y_res')}"
    assert ap.runtime.global_env.get("z_res") == 35, f"Vector transform Z failed: {ap.runtime.global_env.get('z_res')}"
    print("  -> [PASS] matrix3d.ap verified.")

    # 5. Test Memory Pools (memory_pool.ap)
    print("  -> Testing Slab Allocator & Arena Pools (memory_pool.ap)...")
    code_pool = """
#include "adipython/stdlib/mem.ap"
#include "adipython/stdlib/memory_pool.ap"

# Test Slab
slab = slab_create(32, 8)
c1 = slab_alloc(slab)
c2 = slab_alloc(slab)
c3 = slab_alloc(slab)
slab_f1 = slab_free_count(slab) # should be 8 - 3 = 5

slab_free(slab, c2)
slab_f2 = slab_free_count(slab) # should be 5 + 1 = 6

# Test Arena
arena = arena_create(256)
a1 = arena_alloc(arena, 40)
mark = arena_save(arena)
a2 = arena_alloc(arena, 60)
arena_restore(arena, mark)
a3 = arena_alloc(arena, 30)
"""
    ap.execute(code_pool)
    assert ap.runtime.global_env.get("slab_f1") == 5, f"Slab free count failed"
    assert ap.runtime.global_env.get("slab_f2") == 6, f"Slab free after free failed"
    assert ap.runtime.global_env.get("a3") == ap.runtime.global_env.get("a2"), "Arena rewind failed"
    print("  -> [PASS] memory_pool.ap verified.")

    # 6. Test String Utilities & StringBuilder (string_lib.ap)
    print("  -> Testing String Utilities & StringBuilder (string_lib.ap)...")
    code_str = """
#include "adipython/stdlib/mem.ap"
#include "adipython/stdlib/string_lib.ap"

# Test int_to_str
buf = malloc(16)
int_to_str(buf, 420)
s_len = str_len(buf)

# Test str_to_int
parsed_num = str_to_int(buf)

# Test StringBuilder
sb = sb_create(32)
sb_append_char(sb, 65) # 'A'
sb_append_char(sb, 66) # 'B'
sb_append_char(sb, 67) # 'C'
sb_len = sb_length(sb)
c0 = peek(sb_get_str(sb)) & 0xFF
c1 = peek(sb_get_str(sb) + 1) & 0xFF
"""
    ap.execute(code_str)
    assert ap.runtime.global_env.get("s_len") == 3, f"int_to_str length failed: {ap.runtime.global_env.get('s_len')}"
    assert ap.runtime.global_env.get("parsed_num") == 420, f"str_to_int failed: {ap.runtime.global_env.get('parsed_num')}"
    assert ap.runtime.global_env.get("sb_len") == 3, f"sb_length failed"
    assert ap.runtime.global_env.get("c0") == 65 and ap.runtime.global_env.get("c1") == 66, "sb string content failed"
    print("  -> [PASS] string_lib.ap verified.")

    print("\n[Test Block A] ALL BLOCK A SYSTEMS STDLIB TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_block_a_suite()
