#!/usr/bin/env python3
"""
Comprehensive Automated GUI & Interaction Test for AdiOS v0.3
Verifies:
1. Framebuffer layout & desktop composition
2. Paint Studio color palette selection, canvas drawing, and [CLEAR] button
3. Calculator full arithmetic execution (7 + 5 = 12) and [C] clear
4. Start Menu toggling
"""

import sys
import os
import struct

sys.path.insert(0, os.path.abspath("vm"))
from vm import VM, FB_BASE, FB_WIDTH, FB_HEIGHT

sys.path.insert(0, os.path.abspath("toolchain"))
from assembler import Assembler

class MockDisplay:
    def __init__(self):
        self.mouse_x = 320
        self.mouse_y = 240
        self.mouse_buttons = 0
        self.mouse_event = 0
    def render_frame(self):
        pass

def click(vm, x, y, steps_down=250000, steps_up=10000):
    """Simulates a mouse press and release at (x, y) with CPU steps."""
    vm.display.mouse_x = x
    vm.display.mouse_y = y
    vm.display.mouse_buttons = 1
    vm.display.mouse_event = 1
    for _ in range(steps_down):
        vm.step()
    vm.display.mouse_buttons = 0
    vm.display.mouse_event = 1
    for _ in range(steps_up):
        vm.step()

def test_gui_suite():
    print("[Test GUI] Assembling kernel/gui_kernel.s...")
    asmb = Assembler()
    asmb.assemble_file("kernel/gui_kernel.s", "adios.bin")

    print("[Test GUI] Initializing AdiOS Virtual Machine...")
    v = VM()
    v.load_binary("adios.bin")
    v.display = MockDisplay()

    # Step 1: Boot & Desktop Composition
    print("[Test GUI] Booting bare-metal kernel & initializing desktop...")
    for step in range(5000000):
        if not v.step():
            print(f"Halted at step {step}")
            return False
        if v.pc == asmb.labels['gui_main_loop']:
            print(f"[Test GUI] Desktop initialized! Reached main loop at step {step}.")
            break

    # Verification 1: Taskbar & Start Pill
    tb_off = (10 * FB_WIDTH + 200) * 4
    pill_off = (10 * FB_WIDTH + 10) * 4
    assert v.fb[tb_off:tb_off+3] == b"\x1e\x16\x16", "Taskbar color mismatch"
    assert v.fb[pill_off:pill_off+3] == b"\xf7\xa2\x7a", "Start pill color mismatch"
    print("[Test GUI] [PASS] Taskbar and Start Pill verified.")

    # Verification 2: Paint Studio Swatches, Canvas, and [CLEAR]
    print("[Test GUI] Testing Paint Studio...")
    # Canvas pixel (450, 120) should initially be white (0xFF, 0xFF, 0xFF)
    p_off = (120 * FB_WIDTH + 450) * 4
    assert v.fb[p_off:p_off+3] == b"\xff\xff\xff", "Initial canvas not white"

    # Click Swatch 1 (Red at x=398, y=65)
    print("  -> Clicking Red swatch at (398, 65)...")
    click(v, 398, 65)
    p_color = v.read32(asmb.labels['paint_current_color'])
    print(f"  -> paint_current_color = 0x{p_color:08X}")
    # Check that preview box (498, 65) is now Red (#F7768E -> little endian 0x8E, 0x76, 0xF7)
    prev_off = (65 * FB_WIDTH + 498) * 4
    print(f"  -> preview box pixel bytes: {list(v.fb[prev_off:prev_off+4])}")
    assert v.fb[prev_off:prev_off+3] == b"\x8e\x76\xf7", f"Preview box not red: {v.fb[prev_off:prev_off+3]}"
    print("  -> Red swatch selection verified!")

    # Paint a stroke at (450, 120)
    print("  -> Painting stroke at (450, 120)...")
    click(v, 450, 120)
    assert v.fb[p_off:p_off+3] == b"\x8e\x76\xf7", "Stroke not painted with active red color"
    print("  -> Canvas stroke registration verified!")

    # Click [CLEAR] button at (570, 68)
    print("  -> Clicking [CLEAR] button at (570, 68)...")
    click(v, 570, 68)
    assert v.fb[p_off:p_off+3] == b"\xff\xff\xff", "Canvas was not cleared back to white"
    print("[Test GUI] [PASS] Paint Studio fully functional (swatch pick, stroke draw, canvas wipe).")

    # Verification 3: Calculator Arithmetic (7 + 5 = 12)
    print("[Test GUI] Testing Bare-Metal Calculator (7 + 5 = 12)...")
    # Click 7: (Row 0, Col 0) -> x=400, y=330
    print("  -> Clicking '7' at (400, 330)...")
    click(v, 400, 330)
    val_a_addr = asmb.labels['calc_val_a']
    assert v.read32(val_a_addr) == 7, f"Expected calc_val_a=7, got {v.read32(val_a_addr)}"

    # Click +: (Row 0, Col 3) -> x=574, y=330
    print("  -> Clicking '+' at (574, 330)...")
    click(v, 574, 330)
    op_addr = asmb.labels['calc_op']
    assert v.read32(op_addr) == 1, f"Expected calc_op=1, got {v.read32(op_addr)}"

    # Click 5: (Row 1, Col 1) -> x=458, y=360
    print("  -> Clicking '5' at (458, 360)...")
    click(v, 458, 360)
    assert v.read32(val_a_addr) == 5, f"Expected calc_val_a=5, got {v.read32(val_a_addr)}"

    # Click =: (Row 3, Col 2) -> x=516, y=420
    print("  -> Clicking '=' at (516, 420)...")
    click(v, 516, 420)
    result = v.read32(val_a_addr)
    print(f"  -> Calculator result: 7 + 5 = {result}")
    assert result == 12, f"Expected 12, got {result}"

    # Click C: (Row 3, Col 0) -> x=400, y=420
    print("  -> Clicking 'C' at (400, 420)...")
    click(v, 400, 420)
    assert v.read32(val_a_addr) == 0, f"Expected 0, got {v.read32(val_a_addr)}"
    print("[Test GUI] [PASS] Calculator arithmetic (7 + 5 = 12) and Clear verified!")

    # Verification 4: Start Menu
    print("[Test GUI] Testing Start Menu dropdown toggle...")
    menu_state_addr = asmb.labels['start_menu_open']
    assert v.read32(menu_state_addr) == 0, "Menu should initially be closed"

    # Click Start Pill at (30, 10)
    print("  -> Clicking Start Pill at (30, 10)...")
    click(v, 30, 10)
    assert v.read32(menu_state_addr) == 1, "Menu should now be open"
    print("  -> Start Menu open verified!")

    # Click Start Pill again to close
    print("  -> Clicking Start Pill to close...")
    click(v, 30, 10)
    assert v.read32(menu_state_addr) == 0, "Menu should now be closed"
    print("[Test GUI] [PASS] Start Menu toggled cleanly!")

    print("\n===========================================================")
    print("[Test GUI] ALL v0.3 INTERACTIVE GUI FEATURES VERIFIED (100% PASS)!")
    print("===========================================================")
    return True

if __name__ == "__main__":
    success = test_gui_suite()
    sys.exit(0 if success else 1)
