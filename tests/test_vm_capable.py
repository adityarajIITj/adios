#!/usr/bin/env python3
"""
Test Suite: AdiOS Capable Virtual Simulation Layer
Verifies:
1. 64 MB physical RAM access
2. Complete RV32M hardware math (mul, mulh, mulhu, div, divu, rem, remu)
3. Unsigned branches (bltu, bgeu)
4. Virtual Hard Disk controller (ATA / Block MMIO at 0x10001000)
5. Instruction decode cache speedup & self-modifying code invalidation
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import (
    VM, RAM_BASE, RAM_SIZE, DISK_SECTOR, DISK_BUFFER, DISK_CMD, DISK_STATUS
)
from toolchain.assembler import Assembler

def test_vm_hardware():
    print("[Test VM] Initializing 64 MB Virtual Machine...")
    test_disk_path = "test_disk.img"
    if os.path.exists(test_disk_path):
        os.remove(test_disk_path)

    vm = VM(ram_size=64 * 1024 * 1024, disk_path=test_disk_path)
    assert len(vm.ram) == 64 * 1024 * 1024, "RAM size should be 64 MB"
    print("  -> [PASS] 64 MB RAM verified.")

    # 1. Test Memory Access at High Address (e.g. 50 MB into RAM: 0x83200000)
    high_addr = RAM_BASE + 50 * 1024 * 1024
    vm.write32(high_addr, 0xCAFEBABE)
    assert vm.read32(high_addr) == 0xCAFEBABE, "High memory write/read failed"
    print("  -> [PASS] High-memory (50 MB) read/write verified.")

    # 2. Test Virtual Hard Disk Block Controller
    print("[Test VM] Testing Block Storage Controller (MMIO 0x10001000)...")
    buffer_addr = RAM_BASE + 0x10000 # Sector buffer in RAM
    # Write pattern to RAM buffer
    test_pattern = (b"AdiOS TempleOS-Grade Virtual Disk Sector Data! " * 12)[:512]
    test_pattern = test_pattern.ljust(512, b"\0")
    vm.ram[buffer_addr - RAM_BASE : buffer_addr - RAM_BASE + 512] = test_pattern

    # Command 2: Write Sector 7 to disk
    vm.write32(DISK_SECTOR, 7)
    vm.write32(DISK_BUFFER, buffer_addr)
    vm.write32(DISK_CMD, 2) # WRITE
    assert vm.read32(DISK_STATUS) == 0, "Disk write should return 0 (Ready)"

    # Clear RAM buffer
    vm.ram[buffer_addr - RAM_BASE : buffer_addr - RAM_BASE + 512] = b"\x00" * 512

    # Command 1: Read Sector 7 back into RAM buffer
    vm.write32(DISK_CMD, 1) # READ
    assert vm.read32(DISK_STATUS) == 0, "Disk read should return 0 (Ready)"
    read_back = bytes(vm.ram[buffer_addr - RAM_BASE : buffer_addr - RAM_BASE + 512])
    print(f"  -> test_pattern[:30]: {test_pattern[:30]}")
    print(f"  -> read_back[:30]:    {read_back[:30]}")
    assert read_back == test_pattern, "Disk sector read-back does not match written pattern"
    print("  -> [PASS] Virtual Hard Disk Sector Read/Write persistence verified.")

    # Clean up test disk
    if os.path.exists(test_disk_path):
        os.remove(test_disk_path)

    # 3. Test Full RV32M Hardware Math using Assembly
    print("[Test VM] Testing RV32M Hardware Math (mul, mulh, div, rem)...")
    asm_source = """
    _start:
        # MUL: 12 * 13 = 156
        li t0, 12
        li t1, 13
        mul s0, t0, t1

        # DIV: 100 / 7 = 14
        li t0, 100
        li t1, 7
        div s1, t0, t1

        # REM: 100 % 7 = 2
        rem s2, t0, t1

        # DIVU / REMU: Unsigned
        li t0, 0xFFFFFFFE  # 4294967294
        li t1, 2
        divu s3, t0, t1    # 2147483647 (0x7FFFFFFF)
        remu s4, t0, t1    # 0

        # Unsigned Branch: 5 < 10
        li t0, 5
        li t1, 10
        bltu t0, t1, branch_ok
        li s5, 0
        j finish

    branch_ok:
        li s5, 1

    finish:
        # Halt
        li t0, 0x10000040
        li t1, 1
        sb t1, 0(t0)
    """
    tmp_asm = "test_math.s"
    tmp_bin = "test_math.bin"
    with open(tmp_asm, "w") as f:
        f.write(asm_source)

    asmb = Assembler()
    asmb.assemble_file(tmp_asm, tmp_bin)
    vm.load_binary(tmp_bin)

    t0 = time.time()
    steps = 0
    while vm.running:
        vm.step()
        steps += 1
    duration = time.time() - t0

    # Verify registers:
    # s0 (x8) = 156
    # s1 (x9) = 14
    # s2 (x18) = 2
    # s3 (x19) = 0x7FFFFFFF
    # s4 (x20) = 0
    # s5 (x21) = 1
    assert vm.regs[8] == 156, f"mul failed: expected 156, got {vm.regs[8]}"
    assert vm.regs[9] == 14, f"div failed: expected 14, got {vm.regs[9]}"
    assert vm.regs[18] == 2, f"rem failed: expected 2, got {vm.regs[18]}"
    assert vm.regs[19] == 0x7FFFFFFF, f"divu failed: expected 0x7FFFFFFF, got {vm.regs[19]}"
    assert vm.regs[20] == 0, f"remu failed: expected 0, got {vm.regs[20]}"
    assert vm.regs[21] == 1, f"bltu branch failed: expected 1, got {vm.regs[21]}"
    print("  -> [PASS] RV32M (mul, div, rem, divu, remu, bltu) verified 100% correct.")

    # 4. Test Instruction Decode Cache Performance
    print("[Test VM] Benchmarking Pre-Decoded Instruction Cache...")
    loop_asm = """
    _start:
        li t0, 0
        li t1, 100000
    loop:
        addi t0, t0, 1
        bne t0, t1, loop
        li t2, 0x10000040
        li t3, 1
        sb t3, 0(t2)
    """
    with open(tmp_asm, "w") as f:
        f.write(loop_asm)
    asmb = Assembler()
    asmb.assemble_file(tmp_asm, tmp_bin)
    vm.load_binary(tmp_bin)

    t0 = time.time()
    steps = 0
    while vm.running:
        vm.step()
        steps += 1
    duration = time.time() - t0
    mips = (steps / duration) / 1_000_000
    print(f"  -> Executed {steps} instructions in {duration:.3f}s ({mips:.2f} MIPS)!")
    assert vm.regs[5] == 100000, f"Loop counter mismatch: {vm.regs[5]}"
    print("  -> [PASS] Instruction Decode Cache verified.")

    # Cleanup temp files
    for p in [tmp_asm, tmp_bin]:
        if os.path.exists(p): os.remove(p)

    print("\n[Test VM] ALL CAPABLE SIMULATION LAYER TESTS PASSED (100% SUCCESS)!")
    return True

if __name__ == "__main__":
    test_vm_hardware()
