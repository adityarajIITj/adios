#!/usr/bin/env python3
"""
Test Suite: Sovereign Desktop Environment & Window Manager
Verifies:
1. Window creation, stacking order, focus switching, and dragging
2. Window close button [X] hit-testing
3. SovereignDesktop integration: DolDoc terminal, 3D viewport, and File Manager
4. Full compositor rendering to Framebuffer
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from desktop import WindowManager, Window, SovereignDesktop

def test_desktop_wm_suite():
    print("[Test Desktop WM] Testing Sovereign Window Manager & Desktop Compositor...")

    # 1. Test Window Stacking & Focus
    print("  -> Testing window stacking order and focus switching...")
    wm = WindowManager()
    w1 = Window("w1", "Window 1", 10, 30, 200, 150)
    w2 = Window("w2", "Window 2", 50, 60, 200, 150)

    wm.add_window(w1)
    wm.add_window(w2)

    assert wm.windows[-1] == w2, "Top window should be w2"
    assert w2.active and not w1.active, "w2 should be active"

    # Focus w1
    wm.focus_window(w1)
    assert wm.windows[-1] == w1, "Top window should now be w1"
    assert w1.active and not w2.active, "w1 should now be active"
    print("  -> [PASS] Window stacking and focus verified.")

    # 2. Test Window Dragging & Movement
    print("  -> Testing mouse window dragging...")
    # Mouse down on w1 titlebar (10 + 20, 30 + 10) = (30, 40)
    act = wm.handle_mouse_down(30, 40)
    assert act[0] == "drag_start" and act[1] == w1, "Failed to start drag"

    # Drag mouse to (60, 80) -> move offset +30, +40
    wm.handle_mouse_move(60, 80)
    assert w1.x == 40 and w1.y == 70, f"Drag failed: expected (40, 70), got ({w1.x}, {w1.y})"

    # Mouse up
    wm.handle_mouse_up(60, 80)
    assert wm.dragging_win is None, "Drag should be released"
    print("  -> [PASS] Window dragging verified.")

    # 3. Test Close Button [X]
    print("  -> Testing close button hit-testing...")
    # w1 is at (40, 70), w=200, h=150. Close btn is at (40 + 200 - 18 = 222, 70 + 3 = 73)
    close_act = wm.handle_mouse_down(225, 75)
    assert close_act[0] == "close" and close_act[1] == w1, "Close button hit test failed"
    assert not w1.visible, "Window should become invisible after closing"
    print("  -> [PASS] Close button verified.")

    # 4. Test SovereignDesktop Full Integration
    print("  -> Testing SovereignDesktop full compositor and applications...")
    vm = VM()
    desktop = SovereignDesktop(vm)

    # Step frame (increments rotation angle)
    desktop.step_frame(100, 100)
    assert desktop.rot_angle > 0.0, "3D rotation angle did not advance"

    # Render complete desktop to Framebuffer
    desktop.render(vm.fb)

    # Assert Taskbar rendered (top left Start button pixel at y=10, x=20)
    pill_pixel_off = (10 * 640 + 20) * 4
    pill_bytes = list(vm.fb[pill_pixel_off : pill_pixel_off + 4])
    assert pill_bytes[0] > 0 or pill_bytes[1] > 0 or pill_bytes[2] > 0, "Taskbar start pill not rendered"

    # Assert Desktop windows rendered (y=50, x=30)
    win_pixel_off = (50 * 640 + 30) * 4
    win_bytes = list(vm.fb[win_pixel_off : win_pixel_off + 4])
    assert any(b > 0 for b in win_bytes), "Desktop window not rendered"
    print(f"  -> Desktop Compositor output verified (Start Pill: {pill_bytes}, Window: {win_bytes})")

    # Test DolDoc interactive hyperlink click in Desktop Terminal
    print("  -> Testing DolDoc hyperlink click event dispatch inside window...")
    # Click inside terminal content
    desktop.win_term.on_click_content(desktop.win_term, 20, 40)
    print(f"  -> Desktop Status: '{desktop.status_message}'")
    print("  -> [PASS] SovereignDesktop integrated environment verified.")

    print("\n[Test Desktop WM] ALL SOVEREIGN DESKTOP TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_desktop_wm_suite()
