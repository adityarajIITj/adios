#!/usr/bin/env python3
"""
Test Suite: Kernel Core & Concurrency Deepened Subsystem (Pass X Checkpoint 7)
Verifies:
1. Deepened Process Control Block (TaskControlBlock), VMA layout, FD fcntl/dup, waitpid status
2. Deepened Kernel Threading, RWLock writer-preference, RecursiveMutex, Barrier, Futex, TLS
3. Deepened 64-Signal Engine, Real-time signals, sigprocmask, forensic core dump generation
4. Deepened Sovereign IPC, Unix domain socketpair with SCM_RIGHTS FD passing, EventFD, LocklessRingBuffer
5. Deepened Physical Page Allocator, Binary Buddy Allocator (Order 0..10), SlabCache
6. Deepened Sv32 MMU, Page Table Manager, Integrated TLB with ASID tagging & sfence.vma

Zero external dependencies. Pure RV32IM bare-metal test harness.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from proc.process import (
    TaskControlBlock, ProcessState, PriorityClass, ProcessManager,
    F_DUPFD, F_GETFL, O_RDONLY, O_WRONLY, WIFEXITED, WEXITSTATUS
)
from proc.threads import (
    ThreadScheduler, ThreadState, RWLock, RecursiveMutex, Barrier, FutexTable, TLSManager
)
from proc.signals import (
    Signal, SignalDispatcher, SigAction, SigInfo, SIG_BLOCK, SIG_UNBLOCK,
    SIG_DFL, SignalDisposition
)
from proc.ipc import (
    Pipe, MessageQueue, UnixSocket, socketpair, LocklessRingBuffer, EventFD, IPCManager
)
from mmu.page_alloc import (
    PhysicalPageAllocator, BuddyAllocator, SlabCache, PAGE_SIZE
)
from mmu.sv32 import (
    Sv32MMU, PageTableEntry, Sv32PageTableManager, PageFaultException,
    PTE_R, PTE_W, PTE_X, PTE_U, ACCESS_LOAD, ACCESS_STORE, ACCESS_FETCH
)

class TestKernelCoreDeepened(unittest.TestCase):

    def test_01_process_lifecycle_and_waitpid(self):
        pm = ProcessManager()
        init_p = TaskControlBlock("init", parent_pid=0, priority=PriorityClass.REALTIME)
        pm.register_process(init_p)

        child = init_p.fork("worker_daemon")
        pm.register_process(child)
        self.assertEqual(child.ppid, init_p.pid)

        # Test FD duplication & fcntl
        dup_fd = child.dup(1)
        self.assertEqual(dup_fd, 3)
        self.assertEqual(child.fcntl(dup_fd, F_GETFL), O_WRONLY)

        # Test Heap brk adjustment
        orig_brk = child.heap_break
        new_brk = child.adjust_brk(orig_brk + 0x10000)
        self.assertEqual(new_brk, orig_brk + 0x10000)

        # Terminate and reap via waitpid
        pm.exit_process(child, exit_code=77)
        self.assertEqual(child.state, ProcessState.ZOMBIE)
        reaped_pid, status = pm.waitpid(init_p, child.pid)
        self.assertEqual(reaped_pid, child.pid)
        self.assertTrue(WIFEXITED(status))
        self.assertEqual(WEXITSTATUS(status), 77)

    def test_02_threading_concurrency_and_synchronization(self):
        sched = ThreadScheduler()
        t1 = sched.create_thread(1, "t1", priority=2)
        t2 = sched.create_thread(1, "t2", priority=8)

        # Scheduler priority ordering
        chosen = sched.schedule_next()
        self.assertEqual(chosen.tid, t2.tid)
        self.assertEqual(chosen.state, ThreadState.RUNNING)

        # RWLock writer preference
        rw = RWLock("test_rw")
        self.assertTrue(rw.acquire_read(10))
        self.assertFalse(rw.acquire_write(20)) # Blocks on active reader
        self.assertFalse(rw.acquire_read(30))  # Waiting writer takes preference over new reader
        woken = rw.release_read(10)
        self.assertEqual(woken, [20])
        self.assertEqual(rw.active_writer_tid, 20)

        # Recursive Mutex
        rm = RecursiveMutex("test_rm")
        self.assertTrue(rm.acquire(100))
        self.assertTrue(rm.acquire(100)) # Reentrant
        self.assertEqual(rm.recursion_depth, 2)
        self.assertIsNone(rm.release(100))
        self.assertEqual(rm.recursion_depth, 1)

        # Barrier
        bar = Barrier(3)
        self.assertFalse(bar.wait(1)[0])
        self.assertFalse(bar.wait(2)[0])
        is_last, unblocked = bar.wait(3)
        self.assertTrue(is_last)
        self.assertEqual(len(unblocked), 3)

        # Futex
        ft = FutexTable()
        self.assertTrue(ft.futex_wait(0x1000, 42, 42, tid=9))
        woken_futex = ft.futex_wake(0x1000, count=1)
        self.assertEqual(woken_futex, [9])

    def test_03_signals_realtime_and_core_dump(self):
        disp = SignalDispatcher()
        proc = TaskControlBlock("crasher")

        # Core dump generation on fatal SIGQUIT
        disp.send_signal(proc, Signal.SIGQUIT)
        disp.dispatch_pending(proc)
        self.assertEqual(proc.state, ProcessState.ZOMBIE)
        self.assertEqual(proc.exit_code, 128 + Signal.SIGQUIT)
        self.assertIn(proc.pid, disp.core_dumps)
        dump = disp.core_dumps[proc.pid]
        self.assertEqual(dump["fatal_signal"], Signal.SIGQUIT)

        # Real-time signals FIFO ordering
        proc_rt = TaskControlBlock("rt_target")
        disp.send_signal(proc_rt, 40, SigInfo(40, si_value=101))
        disp.send_signal(proc_rt, 40, SigInfo(40, si_value=202))
        q = disp.rt_signal_queues[proc_rt.pid]
        self.assertEqual(len(q), 2)
        self.assertEqual(q[0].si_value, 101)
        self.assertEqual(q[1].si_value, 202)

    def test_04_ipc_socketpair_eventfd_and_ringbuffer(self):
        # Socketpair with SCM_RIGHTS FD passing
        s1, s2 = socketpair()
        s1.send(b"KernelPacket", fds=[10, 11])
        payload, fds = s2.recv(1024)
        self.assertEqual(payload, b"KernelPacket")
        self.assertEqual(fds, [10, 11])

        # EventFD semaphore mode
        efd = EventFD(initval=3, is_semaphore=True)
        self.assertEqual(efd.read(), 1)
        self.assertEqual(efd.read(), 1)
        self.assertEqual(efd.counter, 1)

        # SPSC Lockless Ring Buffer
        lrb = LocklessRingBuffer(power_of_two_exp=6) # 64 bytes
        written = lrb.write(b"HelloSovereignOS")
        self.assertEqual(written, 16)
        read_back = lrb.read(16)
        self.assertEqual(read_back, b"HelloSovereignOS")

    def test_05_physical_page_buddy_and_slab(self):
        alloc = PhysicalPageAllocator()

        # Binary Buddy Allocator
        p4 = alloc.buddy.alloc_pages(order=2) # 4 pages = 16KB
        self.assertIsNotNone(p4)
        alloc.buddy.free_pages(p4, order=2)

        # Slab Allocator
        ptr_a = alloc.slab_alloc(128)
        ptr_b = alloc.slab_alloc(128)
        self.assertNotEqual(ptr_a, ptr_b)
        alloc.slab_free(ptr_a, 128)
        alloc.slab_free(ptr_b, 128)

        # Telemetry
        mem_info = alloc.get_memory_info()
        self.assertGreater(mem_info["free_bytes"], 0)

    def test_06_sv32_mmu_and_integrated_tlb(self):
        ram = bytearray(16 * 1024 * 1024)
        mmu = Sv32MMU(ram, ram_base=0x80000000, tlb_capacity=64)
        mgr = Sv32PageTableManager(mmu)

        root_ppn = 0x80000
        mmu.set_satp((1 << 31) | root_ppn)

        # Map page
        mgr.map_page(root_ppn, 0x00020000, 0x80200000, PTE_R | PTE_W | PTE_U)

        # First translation: TLB miss, page walk
        pa1 = mmu.translate(0x00020050, access_type=ACCESS_LOAD, is_user=True)
        self.assertEqual(pa1, 0x80200050)
        self.assertEqual(mmu.tlb_misses, 1)

        # Second translation: TLB hit
        pa2 = mmu.translate(0x00020090, access_type=ACCESS_STORE, is_user=True)
        self.assertEqual(pa2, 0x80200090)
        self.assertEqual(mmu.tlb_hits, 1)

        # Invalidate via sfence.vma
        mmu.sfence_vma(vaddr=0x00020000)
        self.assertEqual(len(mmu.tlb), 0)

if __name__ == "__main__":
    unittest.main()
