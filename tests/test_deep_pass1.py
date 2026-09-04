#!/usr/bin/env python3
"""
AdiOS Test Suite: Pass 1 — Systems & Core Foundations Deepening
Tests:
- CPreprocessor: macros, conditionals, includes, stringification
- CType: struct alignment, padding, unions, pointer scale, cast validation
- PhysicalPageAllocator, ClockEvictionEngine & Copy-On-Write Manager
- ThreadControlBlock, Mutex, CondVar, Semaphore & ThreadScheduler

Zero external dependencies. Pure bare-metal verification.
STRICT ZERO EMOJI POLICY.
"""

import unittest
from compiler.preprocessor import CPreprocessor
from compiler.c_types import (
    TypeRegistry, StructType, UnionType, PointerType, ArrayType,
    TYPE_INT, TYPE_CHAR, TYPE_SHORT, TYPE_DOUBLE
)
from mmu.page_alloc import (
    PhysicalPageAllocator, ClockEvictionEngine, CopyOnWriteManager,
    PAGE_SIZE, RAM_BASE
)
from proc.threads import (
    ThreadScheduler, ThreadState, Mutex, ConditionVariable, CountingSemaphore
)

class TestPass1SystemsDeepening(unittest.TestCase):

    # --------------------------------------------------------------------------
    # 1. Compiler Preprocessor Tests
    # --------------------------------------------------------------------------

    def test_01_preprocessor_macros(self):
        vfs = {
            "defs.h": "#define OS_NAME \"AdiOS\"\n#define VERSION 1\n",
            "math.h": "#define SQUARE(x) ((x) * (x))\n#define STR(s) #s\n"
        }
        pp = CPreprocessor(vfs=vfs)

        src = (
            "#include \"defs.h\"\n"
            "#include \"math.h\"\n"
            "int x = SQUARE(5);\n"
            "const char* s = STR(hello);\n"
        )
        out = pp.process(src)
        self.assertIn("((5) * (5))", out)
        self.assertIn('"hello"', out)
        self.assertIn("int x =", out)

    def test_02_preprocessor_conditionals(self):
        pp = CPreprocessor()
        src = (
            "#define FEATURE_SMP 1\n"
            "#ifdef FEATURE_SMP\n"
            "int harts = 4;\n"
            "#else\n"
            "int harts = 1;\n"
            "#endif\n"
            "#ifndef FEATURE_DEBUG\n"
            "int debug = 0;\n"
            "#endif\n"
        )
        out = pp.process(src)
        self.assertIn("int harts = 4;", out)
        self.assertNotIn("int harts = 1;", out)
        self.assertIn("int debug = 0;", out)

    # --------------------------------------------------------------------------
    # 2. C Type System & Struct Alignment Tests
    # --------------------------------------------------------------------------

    def test_03_struct_alignment_and_padding(self):
        # struct Test { char a; int b; short c; };
        # Offset a = 0 (1 byte)
        # Padding = 3 bytes
        # Offset b = 4 (4 bytes)
        # Offset c = 8 (2 bytes)
        # Trailing padding = 2 bytes (to multiple of max align 4)
        # Total size = 12 bytes, alignment = 4
        fields = [
            ("a", TYPE_CHAR),
            ("b", TYPE_INT),
            ("c", TYPE_SHORT)
        ]
        st = StructType("Test", fields, packed=False)
        self.assertEqual(st.size, 12)
        self.assertEqual(st.alignment, 4)
        self.assertEqual(st.get_member("a").offset, 0)
        self.assertEqual(st.get_member("b").offset, 4)
        self.assertEqual(st.get_member("c").offset, 8)

        # Packed struct has size = 7, alignment = 1
        st_packed = StructType("TestPacked", fields, packed=True)
        self.assertEqual(st_packed.size, 7)
        self.assertEqual(st_packed.alignment, 1)

    def test_04_union_and_pointer_scale(self):
        fields = [
            ("c", TYPE_CHAR),
            ("i", TYPE_INT),
            ("d", TYPE_DOUBLE)
        ]
        u = UnionType("Val", fields)
        self.assertEqual(u.size, 8) # size of double
        self.assertEqual(u.alignment, 4)

        reg = TypeRegistry()
        ptr_int = reg.pointer_to(TYPE_INT)
        self.assertEqual(reg.pointer_step(ptr_int), 4)

        ptr_double = reg.pointer_to(TYPE_DOUBLE)
        self.assertEqual(reg.pointer_step(ptr_double), 8)
        self.assertTrue(reg.can_cast(ptr_int, ptr_double))

    # --------------------------------------------------------------------------
    # 3. Physical Page Allocator, CLOCK Eviction & COW Tests
    # --------------------------------------------------------------------------

    def test_05_page_frame_allocator(self):
        alloc = PhysicalPageAllocator()
        paddr1 = alloc.alloc_page()
        self.assertIsNotNone(paddr1)
        self.assertEqual(alloc.get_ref_count(paddr1), 1)

        paddr2 = alloc.alloc_page()
        self.assertNotEqual(paddr1, paddr2)

        alloc.retain_page(paddr1)
        self.assertEqual(alloc.get_ref_count(paddr1), 2)

        alloc.free_page(paddr1)
        self.assertEqual(alloc.get_ref_count(paddr1), 1)
        alloc.free_page(paddr1)
        self.assertEqual(alloc.get_ref_count(paddr1), 0)

    def test_06_clock_eviction(self):
        alloc = PhysicalPageAllocator()
        clock = ClockEvictionEngine(alloc)

        p1 = alloc.alloc_page()
        p2 = alloc.alloc_page()
        p3 = alloc.alloc_page()

        clock.register_page(p1, 0x1000)
        clock.register_page(p2, 0x2000)
        clock.register_page(p3, 0x3000)

        # Clear ref bit on p2
        idx2 = (p2 - alloc.base_addr) // PAGE_SIZE
        alloc.frames[idx2].ref_bit = False

        # First victim should be p2 because its ref_bit was 0
        victim = clock.select_victim()
        self.assertIsNotNone(victim)
        victim_paddr, victim_vaddr, _ = victim
        self.assertEqual(victim_paddr, p2)
        self.assertEqual(victim_vaddr, 0x2000)

    def test_07_copy_on_write_duplication(self):
        mem = bytearray(64 * 1024 * 1024)
        alloc = PhysicalPageAllocator()
        cow = CopyOnWriteManager(alloc, mem)

        paddr = alloc.alloc_page()
        off = paddr - alloc.base_addr
        mem[off : off + 8] = b"ORIGINAL"

        # Fork shares page
        cow.fork_share_page(paddr)
        self.assertEqual(alloc.get_ref_count(paddr), 2)

        # Store page fault triggers copy
        new_paddr = cow.handle_cow_store_fault(paddr)
        self.assertNotEqual(new_paddr, paddr)
        self.assertEqual(alloc.get_ref_count(paddr), 1) # parent decremented
        self.assertEqual(alloc.get_ref_count(new_paddr), 1) # child is 1

        # Check data copied to new frame
        new_off = new_paddr - alloc.base_addr
        self.assertEqual(mem[new_off : new_off + 8], b"ORIGINAL")

    # --------------------------------------------------------------------------
    # 4. Kernel Threading, Mutex, CondVar & Semaphore Tests
    # --------------------------------------------------------------------------

    def test_08_thread_scheduler_priority(self):
        sched = ThreadScheduler()
        t1 = sched.create_thread(pid=1, name="worker_low", priority=1)
        t2 = sched.create_thread(pid=1, name="worker_high", priority=5)
        t3 = sched.create_thread(pid=1, name="worker_mid", priority=3)

        # schedule_next should pick t2 (priority 5) first
        next_t = sched.schedule_next()
        self.assertEqual(next_t.tid, t2.tid)
        self.assertEqual(next_t.state, ThreadState.RUNNING)

        # next should pick t3 (priority 3)
        next_t2 = sched.schedule_next()
        self.assertEqual(next_t2.tid, t3.tid)

    def test_09_mutex_wait_queue(self):
        m = Mutex("test_mutex")
        # Thread 1 acquires
        self.assertTrue(m.acquire(tid=1))
        self.assertTrue(m.locked)
        self.assertEqual(m.owner_tid, 1)

        # Thread 2 tries to acquire and must block
        self.assertFalse(m.acquire(tid=2))
        self.assertEqual(m.wait_queue, [2])

        # Thread 1 releases, transferring lock to thread 2
        woken_tid = m.release(tid=1)
        self.assertEqual(woken_tid, 2)
        self.assertTrue(m.locked)
        self.assertEqual(m.owner_tid, 2)

        # Thread 2 releases
        woken_tid2 = m.release(tid=2)
        self.assertIsNone(woken_tid2)
        self.assertFalse(m.locked)

    def test_10_semaphore_counting(self):
        sem = CountingSemaphore(initial_value=2)
        self.assertTrue(sem.wait(tid=1))
        self.assertTrue(sem.wait(tid=2))
        # Third wait blocks
        self.assertFalse(sem.wait(tid=3))
        self.assertEqual(sem.wait_queue, [3])

        # Post wakes thread 3
        woken = sem.post()
        self.assertEqual(woken, 3)

if __name__ == "__main__":
    unittest.main()
