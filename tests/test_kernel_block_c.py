#!/usr/bin/env python3
"""
Test Suite: Block C Bare-Metal Kernel
Verifies:
1. Bare-metal Assembly Scheduler (sched.s): Task creation, TCB chaining, PID allocation
2. Bare-metal Memory Manager (mem_manager.s): 16,384 4KB page frame bitmap allocator, page_alloc, page_free
3. Bare-metal Virtual Filesystem & AdiFS Driver (vfs.s): MMIO disk reading, superblock mount, file search, and contiguous DMA streaming
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fs.adifs import AdiFS
from toolchain.assembler import Assembler
from vm.vm import VM

def test_kernel_block_c_suite():
    print("[Test Kernel Block C] Initializing Bare-Metal Kernel Verification...")

    # 1. Ensure disk image has AdiFS with test file
    print("  -> Preparing AdiFS disk image with test payload...")
    fs = AdiFS("disk.img")
    try:
        fs.get_superblock()
    except Exception:
        fs.format_disk()

    if not fs.exists("run_test.ap"):
        fs.create_file("run_test.ap", "print('Block C kernel payload verification')\n")
    print("  -> [PASS] Disk image verified.")

    # 2. Assemble kernel/test_block_c.s
    print("  -> Assembling kernel/test_block_c.s with custom RV32 toolchain...")
    asm = Assembler()
    bin_path = "block_c_kernel.bin"
    asm.assemble_file("kernel/test_block_c.s", bin_path)
    assert os.path.exists(bin_path), "Assembly output binary not found"
    print(f"  -> Assembled '{bin_path}' ({os.path.getsize(bin_path)} bytes).")

    # 3. Boot VM and run bare-metal kernel
    print("  -> Booting VM and running bare-metal tests...")
    vm = VM()
    vm.load_binary(bin_path)

    # Capture UART output
    uart_output = []
    def uart_sink(val):
        uart_output.append(chr(val & 0xFF))

    vm.uart_callback = uart_sink

    # Run for up to 500,000 cycles
    for _ in range(500000):
        if not vm.step():
            break
        output_str = "".join(uart_output)
        if "ALL BARE-METAL KERNEL TESTS PASSED" in output_str:
            break
        if "TEST FAILED" in output_str:
            print("UART Dump:", output_str)
            assert False, "Kernel Block C test failed!"

    final_output = "".join(uart_output)
    assert "ALL BARE-METAL KERNEL TESTS PASSED" in final_output, f"Kernel test did not pass. Output: {final_output}"
    print(f"  -> {final_output.strip()}")

    print("\n[Test Kernel Block C] ALL BLOCK C BARE-METAL KERNEL TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_kernel_block_c_suite()
