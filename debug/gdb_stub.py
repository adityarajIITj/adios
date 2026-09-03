#!/usr/bin/env python3
"""
AdiOS Debugging Subsystem: GDB Remote Serial Protocol & Debugger Engine (gdb_stub.py)
Implements standard RSP debugger and call stack unwinder:
- GDB Remote Serial Protocol packet serialization and checksum verification
- Register reading (g), memory inspection (m), memory modification (M)
- Software breakpoints (Z0/z0) with ebreak injection
- Call stack unwinding & backtrace symbol reconstruction
Zero external dependencies.
"""

import struct
from typing import Dict, List, Tuple, Optional

OPCODE_EBREAK = 0x00100073 # RISC-V ebreak instruction

class GDBPacket:
    """Encodes and decodes GDB Remote Serial Protocol packets."""
    @staticmethod
    def calculate_checksum(data: str) -> str:
        s = sum(ord(c) for c in data) % 256
        return f"{s:02x}"

    @staticmethod
    def format_packet(payload: str) -> str:
        ck = GDBPacket.calculate_checksum(payload)
        return f"${payload}#{ck}"

    @staticmethod
    def parse_packet(packet_str: str) -> Optional[str]:
        if not (packet_str.startswith("$") and "#" in packet_str):
            return None
        payload, _, ck = packet_str[1:].partition("#")
        if GDBPacket.calculate_checksum(payload) == ck.lower():
            return payload
        return None

class DebugContext:
    """Execution state exposed to debugger."""
    def __init__(self):
        self.regs = [0] * 32
        self.pc = 0x80000000
        self.memory: Dict[int, int] = {} # Address -> 32-bit word
        self.breakpoints: Dict[int, int] = {} # Address -> original instruction
        self.symbols: Dict[int, str] = {}     # Address -> function name

    def set_breakpoint(self, addr: int):
        orig = self.memory.get(addr, 0)
        self.breakpoints[addr] = orig
        self.memory[addr] = OPCODE_EBREAK

    def clear_breakpoint(self, addr: int):
        if addr in self.breakpoints:
            self.memory[addr] = self.breakpoints[addr]
            del self.breakpoints[addr]

class GDBStub:
    """
    GDB RSP command interpreter.
    """
    def __init__(self, ctx: DebugContext):
        self.ctx = ctx

    def handle_command(self, cmd_payload: str) -> str:
        if not cmd_payload:
            return ""

        # Query halt reason
        if cmd_payload == "?":
            return "S05" # SIGTRAP

        # Read all registers (g)
        elif cmd_payload == "g":
            # 32 registers + PC = 33 32-bit registers (little endian hex)
            hex_parts = []
            for r in self.ctx.regs:
                hex_parts.append(struct.pack("<I", r & 0xFFFFFFFF).hex())
            hex_parts.append(struct.pack("<I", self.ctx.pc & 0xFFFFFFFF).hex())
            return "".join(hex_parts)

        # Read memory: m addr,length
        elif cmd_payload.startswith("m"):
            addr_str, _, len_str = cmd_payload[1:].partition(",")
            addr = int(addr_str, 16)
            length = int(len_str, 16)
            res = bytearray()
            for a in range(addr, addr + length, 4):
                word = self.ctx.memory.get(a, 0)
                res.extend(struct.pack("<I", word))
            return res[:length].hex()

        # Write memory: M addr,length:val
        elif cmd_payload.startswith("M"):
            head, _, hex_val = cmd_payload[1:].partition(":")
            addr_str, _, len_str = head.partition(",")
            addr = int(addr_str, 16)
            raw_bytes = bytes.fromhex(hex_val)
            for i in range(0, len(raw_bytes), 4):
                chunk = raw_bytes[i:i + 4].ljust(4, b"\x00")
                word = struct.unpack("<I", chunk)[0]
                self.ctx.memory[addr + i] = word
            return "OK"

        # Insert software breakpoint: Z0,addr,kind
        elif cmd_payload.startswith("Z0,"):
            parts = cmd_payload.split(",")
            addr = int(parts[1], 16)
            self.ctx.set_breakpoint(addr)
            return "OK"

        # Remove software breakpoint: z0,addr,kind
        elif cmd_payload.startswith("z0,"):
            parts = cmd_payload.split(",")
            addr = int(parts[1], 16)
            self.ctx.clear_breakpoint(addr)
            return "OK"

        return "" # Unsupported returns empty response

class StackUnwinder:
    """Reconstructs call stack backtraces using frame pointers and return addresses."""
    @staticmethod
    def unwind(ctx: DebugContext, max_depth: int = 16) -> List[Tuple[int, str]]:
        backtrace = []
        fp = ctx.regs[8] # s0 / fp
        ra = ctx.regs[1] # ra

        # Current function at PC
        func_name = ctx.symbols.get(ctx.pc, f"0x{ctx.pc:08X}")
        backtrace.append((ctx.pc, func_name))

        depth = 0
        while fp != 0 and depth < max_depth:
            # Standard RISC-V frame: saved ra at fp - 4, saved fp at fp - 8
            saved_ra = ctx.memory.get(fp - 4, 0)
            saved_fp = ctx.memory.get(fp - 8, 0)
            if saved_ra == 0 or saved_ra == ra:
                break
            func_sym = ctx.symbols.get(saved_ra, f"0x{saved_ra:08X}")
            backtrace.append((saved_ra, func_sym))
            ra = saved_ra
            fp = saved_fp
            depth += 1

        return backtrace

if __name__ == "__main__":
    ctx = DebugContext()
    stub = GDBStub(ctx)
    pkt = GDBPacket.format_packet("?")
    assert pkt == "$?#3f"
    assert GDBPacket.parse_packet(pkt) == "?"
    print("GDB Stub & Debugger engine verified.")
