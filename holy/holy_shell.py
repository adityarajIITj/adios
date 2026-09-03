#!/usr/bin/env python3
"""
AdiOS Sovereign Computing Subsystem: The Sovereign Cyber Shell (holy_shell.py)
Unified Interactive Command Environment fusing DolDoc, Hardware Entropy Oracle,
Polyphonic Baroque Synthesizer, 3D Cyber Citadel, Memory Allocator stats, and AdiFS Disk Inspection.
"""

import sys
import os
import time

from holy.oracle import CosmicOracle
from holy.hymn import BaroqueSynthesizer
from holy.sanctuary3d import CyberCitadel3D
from fs.adifs import AdiFS

class SovereignCyberShell:
    """
    Sovereign Command Interpreter of AdiOS.
    """
    def __init__(self, vm=None):
        self.vm = vm
        self.oracle = CosmicOracle(vm)
        self.synth = BaroqueSynthesizer()
        self.citadel = CyberCitadel3D(vm)
        self.running = True

    def execute_line(self, cmdline):
        """Parses and dispatches shell commands."""
        parts = cmdline.strip().split()
        if not parts:
            return ""

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            return self.cmd_help()
        elif cmd in ["oracle", "entropy", "words"]:
            count = int(args[0]) if args and args[0].isdigit() else 16
            return f"[Cosmic Oracle]\n{self.oracle.consult_oracle(count)}\n"
        elif cmd in ["axiom", "aphorism"]:
            return f"[Philosophical Axiom]\n\"{self.oracle.generate_aphorism()}\"\n"
        elif cmd in ["synth", "music", "chiptune"]:
            mode = args[0] if args else "Major"
            piece = self.synth.compose_piece(mode, 8)
            if self.vm:
                self.synth.play_to_speaker_mmio(self.vm, piece, 200)
            return self.synth.render_doldoc(piece)
        elif cmd in ["citadel", "3d"]:
            if self.vm:
                count = self.citadel.render_frame()
                return f"[Citadel 3D] Rendered {count} wireframe lines to 640x480 Framebuffer.\n"
            return "[Citadel 3D] Initialized (No VM attached).\n"
        elif cmd == "palloc":
            return self.cmd_palloc()
        elif cmd in ["tasks", "ps"]:
            return self.cmd_tasks()
        elif cmd == "matrix":
            return (
                "\n0 1 0 1 1 0 1 0   AdiOS CYBERSPACE   0 1 0 1 1 0 1 0\n"
                "1 0 0 1 0 1 1 0   Bare-Metal RISC-V  1 0 0 1 0 1 1 0\n"
                "0 1 1 0 1 0 0 1   Goodbye Bloat!     0 1 1 0 1 0 0 1\n"
            )
        elif cmd == "ls":
            return self.cmd_ls()
        elif cmd == "disk":
            return self.cmd_disk()
        elif cmd == "cat":
            if not args: return "Usage: cat <filename>\n"
            return self.cmd_cat(args[0])
        elif cmd in ["exit", "quit"]:
            self.running = False
            return "AdiOS Sovereign Cyber Shell Exiting.\n"
        else:
            return f"Unknown command: '{cmd}'. Type 'help' for command index.\n"

    def cmd_help(self):
        return (
            "===========================================================\n"
            "            AdiOS SOVEREIGN CYBER SHELL COMMANDS           \n"
            "===========================================================\n"
            "  oracle [n]      - Consult the Hardware Entropy Oracle\n"
            "  axiom           - Generate philosophical & scientific axiom\n"
            "  synth [mode]    - Algorithmic 4-part polyphonic baroque synthesis\n"
            "  citadel         - Render 3D Cyber Citadel & Quantum Core (640x480)\n"
            "  palloc          - Physical 4KB Page Frame Allocator stats (64MB)\n"
            "  tasks / ps      - Active Task Control Blocks & Scheduler status\n"
            "  matrix          - Display sovereign cyberpunk cyberspace banner\n"
            "  ls              - List contiguous files on AdiFS virtual disk\n"
            "  cat <file>      - Print contents of file from virtual hard disk\n"
            "  disk            - Display virtual block storage drive parameters\n"
            "  help            - Display this reference index\n"
            "  exit            - Terminate shell session\n"
            "===========================================================\n"
        )

    def cmd_palloc(self):
        return (
            "--- Dual-Heap Physical Page Frame Allocator ---\n"
            "  Total RAM:         64 MB (67,108,864 bytes)\n"
            "  Page Size:         4,096 bytes (4 KB)\n"
            "  Total Pages:       16,384 pages\n"
            "  Reserved Pages:    1,024 pages (First 4 MB: Kernel Text & MMIO)\n"
            "  Free Dynamic RAM:  15,360 pages (60 MB available for user tasks)\n"
            "  Allocation Bitmap: 2,048 bytes (512 words in .bss)\n"
            "  Status:            ONLINE & HEALTHY\n"
        )

    def cmd_tasks(self):
        return (
            "PID  NAME             STATE      QUANTUM  PRIORITY  STACK TOP\n"
            "--------------------------------------------------------------\n"
            "0    IdleTask         READY      1        Idle (2)  0x81800000\n"
            "1    AdamTask         RUNNING    5        Norm (1)  0x81000000\n"
            "2    CyberShell       READY      5        Norm (1)  0x81400000\n"
        )

    def cmd_ls(self):
        if not os.path.exists("disk.img"):
            return "No virtual hard disk attached.\n"
        fs = AdiFS("disk.img")
        entries = fs.list_files()
        lines = ["NAME                         SECTOR    SIZE      ATTR"]
        lines.append("-------------------------------------------------------")
        for e in entries:
            lines.append(f"{e.name:<28} {e.start_sector:<9} {e.size_bytes:<9} [CONTIGUOUS]")
        return "\n".join(lines) + "\n"

    def cmd_disk(self):
        if not os.path.exists("disk.img"):
            return "No virtual hard disk attached.\n"
        fs = AdiFS("disk.img")
        sb = fs.get_superblock()
        return (
            f"--- AdiFS Virtual Hard Disk Superblock ---\n"
            f"  Magic:            {sb.magic.decode('latin-1').strip(chr(0))}\n"
            f"  Sector Size:      {sb.sector_size} bytes\n"
            f"  Total Sectors:    {sb.total_sectors} (8 MB)\n"
            f"  Root Dir Sector:  {sb.root_dir_sector} (32 sectors)\n"
            f"  Data Sector:      {sb.data_start_sector}\n"
            f"  Free Pointer:     Sector {sb.free_sector_ptr}\n"
        )

    def cmd_cat(self, filename):
        if not os.path.exists("disk.img"):
            return "No virtual hard disk attached.\n"
        fs = AdiFS("disk.img")
        data = fs.read_file(filename)
        if data is None:
            return f"File not found: '{filename}'\n"
        try:
            return data.decode("utf-8") + "\n"
        except Exception:
            return f"[Binary data: {len(data)} bytes]\n"

if __name__ == "__main__":
    shell = SovereignCyberShell()
    print(shell.cmd_help())
    print(shell.execute_line("oracle 12"))
    print(shell.execute_line("axiom"))
    print(shell.execute_line("palloc"))
