#!/usr/bin/env python3
"""
Test Suite: Block P Sovereign Window Server & Vector GUI Toolkit
Verifies:
1. ui/canvas2d: 2D vector primitives, rounded rects, clipping rects, alpha blending
2. ui/widgets: Widget hierarchy, coordinate mapping, Buttons, TextBoxes, Sliders
3. ui/window_server: Z-order window stacking, focus management, drag movement, composition
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ui.canvas2d import Canvas2D, Rect, blend_pixel
from ui.widgets import Widget, Label, Button, TextBox, Slider, WindowWidget
from ui.window_server import WindowServer

def test_ui_block_p_suite():
    print("[Test UI Block P] Initializing Window Server & Vector GUI Verification...")

    # 1. Test 2D Canvas & Vector Primitives
    print("  -> Testing Canvas2D Vector Primitives & Clipping...")
    canvas = Canvas2D(320, 240)
    canvas.clear(0xFF1A1B26)
    assert canvas.get_pixel(10, 10) == 0xFF1A1B26

    # Draw lines and rectangles
    canvas.draw_line(0, 0, 100, 0, 0xFFFFFFFF)
    assert canvas.get_pixel(50, 0) == 0xFFFFFFFF

    canvas.fill_rect(20, 20, 50, 50, 0xFF7AA2F7)
    assert canvas.get_pixel(30, 30) == 0xFF7AA2F7

    canvas.fill_rounded_rect(100, 100, 60, 40, 6, 0xFF9ECE6A)
    assert canvas.get_pixel(120, 120) == 0xFF9ECE6A

    # Test Clipping Stack
    canvas.push_clip(Rect(200, 200, 20, 20))
    canvas.fill_rect(0, 0, 320, 240, 0xFFF7768E)
    # Outside clip rectangle must NOT be changed!
    assert canvas.get_pixel(30, 30) == 0xFF7AA2F7
    # Inside clip rectangle MUST be changed!
    assert canvas.get_pixel(205, 205) == 0xFFF7768E
    canvas.pop_clip()

    # Test Alpha Blending
    blended = blend_pixel(0x80FF0000, 0xFF0000FF)
    assert (blended >> 24) & 0xFF == 0xFF # Fully opaque output
    assert (blended >> 16) & 0xFF > 0     # Red blended in
    assert blended & 0xFF > 0              # Blue preserved
    print("  -> [PASS] Canvas2D primitives, clipping & blending verified.")

    # 2. Test Widget Hierarchy & Controls
    print("  -> Testing Widget Hierarchy, Buttons, TextBoxes & Sliders...")
    root = Widget(0, 0, 320, 240)
    panel = Widget(50, 50, 200, 150)
    root.add_child(panel)

    clicked = False
    def on_btn_click():
        nonlocal clicked
        clicked = True

    btn = Button(10, 10, 80, 30, "Confirm", on_click=on_btn_click)
    panel.add_child(btn)

    # Test coordinate mapping: screen_x should be 50 + 10 = 60
    assert btn.screen_x == 60
    assert btn.screen_y == 60

    # Simulate Button Click at (65, 65)
    root.on_mouse_down(65, 65)
    assert btn.is_pressed is True
    root.on_mouse_up(65, 65)
    assert btn.is_pressed is False
    assert clicked is True

    # Test TextBox Typing
    txt = TextBox(10, 50, 120, 25, "Initial")
    panel.add_child(txt)
    root.on_mouse_down(65, 105) # Click on TextBox
    assert txt.focused is True
    root.on_key_down(ord('A'), 'A')
    root.on_key_down(ord('B'), 'B')
    assert txt.text == "InitialAB"
    root.on_key_down(8, '') # Backspace
    assert txt.text == "InitialA"

    # Test Slider
    slider = Slider(10, 90, 100, 20, min_val=0.0, max_val=100.0, initial=25.0)
    panel.add_child(slider)
    root.on_mouse_down(110, 150) # Click at midpoint
    assert slider.value > 25.0
    root.on_mouse_up(110, 150)
    assert slider.is_dragging is False
    print("  -> [PASS] Widgets (Button, TextBox, Slider) verified.")

    # 3. Test WindowServer & Compositor
    print("  -> Testing Sovereign Window Server, Focus & Compositor...")
    server = WindowServer(width=640, height=480)
    win1 = WindowWidget(30, 30, 200, 150, "Process Monitor")
    win2 = WindowWidget(100, 100, 200, 150, "Network Console")

    server.add_window(win1)
    server.add_window(win2)
    assert server.focused_window == win2

    # Click on win1 titlebar (40, 40) to focus
    server.handle_mouse_down(40, 40)
    assert server.focused_window == win1

    # Drag window
    server.handle_mouse_move(60, 60)
    assert win1.x == 50 # Moved by +20
    assert win1.y == 50
    server.handle_mouse_up(60, 60)
    assert win1.is_dragging is False

    # Full composition pass
    server.compose()
    assert len(server.canvas.pixels) == 640 * 480 * 4
    # Ensure window pixels were drawn
    assert server.canvas.get_pixel(win1.x + 10, win1.y + 10) != 0
    print("  -> [PASS] Window Server, dragging & compositor verified.")

    print("\n[Test UI Block P] ALL BLOCK P WINDOW SERVER & GUI TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_ui_block_p_suite()
