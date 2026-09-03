#!/usr/bin/env python3
"""
Automated Graphics & GUI Test for AdiOS
Verifies framebuffer memory, desktop initialization, and mouse interactions.
"""

import sys
import os

sys.path.insert(0, os.path.abspath("vm"))
from vm import VM, FB_BASE, FB_WIDTH, FB_HEIGHT

def test_gui_render():
    print("[Test GUI] Initializing AdiOS Virtual Machine...")
    v = VM()
    v.load_binary("adios.bin")

    sys.path.insert(0, os.path.abspath("toolchain"))
    from assembler import Assembler
    asmb = Assembler()
    asmb.assemble_file("kernel/gui_kernel.s", "adios.bin")
    print(f"[Test GUI] gui_main_loop is at: 0x{asmb.labels['gui_main_loop']:08X}")
    print(f"[Test GUI] draw_calc_button is at: 0x{asmb.labels['draw_calc_button']:08X}")

    # Step through boot and desktop initialization (approx 4M cycles for 740K pixels)
    print("[Test GUI] Running boot and GUI compositor sequence...")
    for step in range(5000000):
        if not v.step():
            print(f"Halted prematurely at step {step}")
            return False
        if v.pc == asmb.labels['gui_main_loop']:
            print(f"[Test GUI] Reached gui_main_loop at step {step}!")
            break
    print(f"[Test GUI] Finished steps, current PC: 0x{v.pc:08X}")
    for lbl, addr in sorted(asmb.labels.items(), key=lambda x: x[1]):
        if addr <= v.pc <= addr + 200:
            print(f"  Near label '{lbl}': 0x{addr:08X} (offset +{v.pc - addr})")

    # Check 1: Verify Taskbar color (#16161E -> little endian 0x1E, 0x16, 0x16, 0x00)
    # Taskbar is at (x=200, y=10)
    tb_offset = (10 * FB_WIDTH + 200) * 4
    b, g, r, a = v.fb[tb_offset:tb_offset+4]
    print(f"[Test GUI] Taskbar pixel at (200, 10): R={r}, G={g}, B={b}")
    assert (r, g, b) == (0x16, 0x16, 0x1E), "Taskbar pixel color mismatch"

    # Check 2: Verify Start Pill at (x=10, y=10) (#7AA2F7 -> R=0x7A, G=0xA2, B=0xF7)
    pill_offset = (10 * FB_WIDTH + 10) * 4
    b, g, r, a = v.fb[pill_offset:pill_offset+4]
    print(f"[Test GUI] Start Pill pixel at (10, 10): R={r}, G={g}, B={b}")
    assert (r, g, b) == (0x7A, 0xA2, 0xF7), "Start pill color mismatch"

    # Check 3: Verify Paint Canvas Body at (x=450, y=100) (White: R=255, G=255, B=255)
    paint_offset = (100 * FB_WIDTH + 450) * 4
    b, g, r, a = v.fb[paint_offset:paint_offset+4]
    print(f"[Test GUI] Paint Canvas pixel at (450, 100): R={r}, G={g}, B={b}")
    assert (r, g, b) == (0xFF, 0xFF, 0xFF), "Paint canvas color mismatch"

    # Check 4: Simulate Mouse Click on Paint Canvas
    print("[Test GUI] Simulating mouse click on Paint Canvas at (450, 100)...")
    # Set mouse coordinates and click in display state
    class FakeDisplay:
        mouse_x = 450
        mouse_y = 100
        mouse_buttons = 1
        mouse_event = 1
        def render_frame(self): pass
    v.display = FakeDisplay()

    # Step through interaction loop
    for _ in range(5000):
        v.step()

    # Check if brush pixel was drawn (x=453 is within 4x4 brush, outside 2px cursor stem)
    painted_offset = (100 * FB_WIDTH + 453) * 4
    b, g, r, a = v.fb[painted_offset:painted_offset+4]
    print(f"[Test GUI] Painted pixel at (453, 100) after click: R={r}, G={g}, B={b}")
    assert (r, g, b) == (0xF7, 0x76, 0x8E), "Painted pixel did not register on canvas!"

    print("\n[Test GUI] ALL GUI CHECKS PASSED SUCCESSFULLY! Framebuffer & Mouse MMIO verified.")
    return True

if __name__ == "__main__":
    success = test_gui_render()
    sys.exit(0 if success else 1)
