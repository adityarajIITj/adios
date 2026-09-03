#!/usr/bin/env python3
"""
Test Suite: Block U In-OS Debugger & GDB Remote Serial Protocol
Verifies:
1. debug/gdb_stub: GDB RSP packet framing & checksum verification
2. debug/gdb_stub: Register inspection (g) & memory read/write (m/M)
3. debug/gdb_stub: Software breakpoints (Z0/z0) with ebreak injection
4. debug/gdb_stub: Call stack unwinding & backtrace symbol resolution
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from debug.gdb_stub import GDBPacket, DebugContext, GDBStub, StackUnwinder, OPCODE_EBREAK

def test_debug_block_u_suite():
    print("[Test Debug Block U] Initializing In-OS Debugger & RSP Verification...")

    # 1. Test GDB RSP Packet Framing & Checksums
    print("  -> Testing GDB RSP Packet Framing & Checksums...")
    # '?' -> sum is ord('?') = 63 = 0x3f
    pkt_q = GDBPacket.format_packet("?")
    assert pkt_q == "$?#3f"
    assert GDBPacket.parse_packet(pkt_q) == "?"

    # Check invalid checksum rejection
    bad_pkt = "$?#42"
    assert GDBPacket.parse_packet(bad_pkt) is None
    print("  -> [PASS] GDB packet format & checksum verified.")

    # 2. Test Register Inspection & Halt Reason
    print("  -> Testing Register Inspection & Status Queries...")
    ctx = DebugContext()
    ctx.regs[1] = 0x80001000 # ra
    ctx.regs[2] = 0x80004000 # sp
    ctx.regs[10] = 42        # a0
    ctx.pc = 0x80000200
    stub = GDBStub(ctx)

    # Status query
    status = stub.handle_command("?")
    assert status == "S05" # SIGTRAP

    # Read registers
    g_resp = stub.handle_command("g")
    assert len(g_resp) == 33 * 8 # 33 registers * 8 hex chars = 264
    # Verify a0 (x10) is 42 (0x2a000000)
    a0_hex = g_resp[10 * 8:11 * 8]
    assert a0_hex == "2a000000"
    print("  -> [PASS] Register inspection verified.")

    # 3. Test Memory Read & Write Commands
    print("  -> Testing Memory Inspection (m) & Modification (M)...")
    # Write 8 bytes (0x12345678, 0x9ABCDEF0) to 0x80002000
    w_resp = stub.handle_command("M80002000,8:78563412f0debc9a")
    assert w_resp == "OK"
    assert ctx.memory[0x80002000] == 0x12345678
    assert ctx.memory[0x80002004] == 0x9ABCDEF0

    # Read memory back
    m_resp = stub.handle_command("m80002000,8")
    assert m_resp.lower() == "78563412f0debc9a"
    print("  -> [PASS] Memory read/write verified.")

    # 4. Test Software Breakpoints
    print("  -> Testing Software Breakpoints (Z0/z0) with ebreak...")
    target_addr = 0x80000500
    original_insn = 0x00A58513 # addi a0, a1, 10
    ctx.memory[target_addr] = original_insn

    # Insert breakpoint Z0
    z0_resp = stub.handle_command(f"Z0,{target_addr:x},4")
    assert z0_resp == "OK"
    assert ctx.memory[target_addr] == OPCODE_EBREAK

    # Remove breakpoint z0
    clr_resp = stub.handle_command(f"z0,{target_addr:x},4")
    assert clr_resp == "OK"
    assert ctx.memory[target_addr] == original_insn
    print("  -> [PASS] Breakpoint injection & clean restoration verified.")

    # 5. Test Stack Unwinder & Backtrace
    print("  -> Testing Call Stack Unwinder & Symbol Resolution...")
    ctx.symbols[0x80000100] = "main"
    ctx.symbols[0x80000250] = "kernel_init"
    ctx.symbols[0x80000400] = "quantum_driver_start"

    # Frame 1: quantum_driver_start at PC 0x80000400, fp = 0x80003000
    ctx.pc = 0x80000400
    ctx.regs[8] = 0x80003000 # current fp
    ctx.regs[1] = 0x80000250 # caller ra (kernel_init)

    # Stack memory for Frame 1
    # fp - 4 = saved ra (0x80000100 -> main)
    # fp - 8 = saved fp (0x80003100)
    ctx.memory[0x80003000 - 4] = 0x80000100
    ctx.memory[0x80003000 - 8] = 0x80003100

    # Stack memory for Frame 2
    # fp - 4 = 0 (bottom of stack)
    # fp - 8 = 0
    ctx.memory[0x80003100 - 4] = 0
    ctx.memory[0x80003100 - 8] = 0

    bt = StackUnwinder.unwind(ctx)
    assert len(bt) == 2
    assert bt[0] == (0x80000400, "quantum_driver_start")
    assert bt[1] == (0x80000100, "main")
    print("  -> [PASS] Call stack unwinding & symbol resolution verified.")

    print("\n[Test Debug Block U] ALL BLOCK U DEBUGGER & RSP TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_debug_block_u_suite()
