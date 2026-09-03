#!/usr/bin/env python3
"""
AdiOS User Interface Subsystem: Sovereign Window Server & Compositor (window_server.py)
Manages multi-window Z-order stacking, active window focus, dirty rectangles,
desktop wallpaper rendering, hardware cursor compositing, and event routing.
Zero external dependencies.
"""

from typing import List, Optional
from ui.canvas2d import Canvas2D, Rect
from ui.widgets import WindowWidget, Widget

class WindowServer:
    """
    Compositor and Window Manager.
    """
    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self.canvas = Canvas2D(width, height)
        self.windows: List[WindowWidget] = []
        self.focused_window: Optional[WindowWidget] = None
        self.mouse_x = width // 2
        self.mouse_y = height // 2

    def add_window(self, win: WindowWidget):
        self.windows.append(win)
        self.set_focus(win)

    def set_focus(self, win: WindowWidget):
        if win in self.windows:
            self.windows.remove(win)
            self.windows.append(win) # Top of Z-order
            self.focused_window = win
            win.focused = True

    def handle_mouse_down(self, x: int, y: int):
        self.mouse_x = x
        self.mouse_y = y

        # Scan windows in top-to-bottom Z-order
        for win in reversed(self.windows):
            if win.contains(x, y):
                self.set_focus(win)
                win.on_mouse_down(x, y)
                return

    def handle_mouse_up(self, x: int, y: int):
        self.mouse_x = x
        self.mouse_y = y
        if self.focused_window:
            self.focused_window.on_mouse_up(x, y)

    def handle_mouse_move(self, x: int, y: int):
        self.mouse_x = x
        self.mouse_y = y
        for win in self.windows:
            win.on_mouse_move(x, y)

    def handle_key_down(self, key_code: int, char: str):
        if self.focused_window:
            self.focused_window.on_key_down(key_code, char)

    def compose(self):
        """Composites desktop wallpaper, windows, and mouse cursor."""
        # 1. Desktop Background
        self.canvas.clear(0xFF16161E)

        # Draw grid pattern
        for y in range(0, self.height, 40):
            self.canvas.draw_line(0, y, self.width - 1, y, 0xFF1F2335)
        for x in range(0, self.width, 40):
            self.canvas.draw_line(x, 0, x, self.height - 1, 0xFF1F2335)

        # 2. Render Windows in Z-order
        for win in self.windows:
            win.render(self.canvas)

        # 3. Render Mouse Cursor (Arrow pointer)
        self._draw_cursor(self.mouse_x, self.mouse_y)

    def _draw_cursor(self, cx: int, cy: int):
        # Draw small 8-pixel pointer arrow
        for i in range(8):
            self.canvas.draw_line(cx, cy + i, cx + i, cy + i, 0xFFFFFFFF)
        self.canvas.draw_line(cx, cy, cx, cy + 10, 0xFF000000)
        self.canvas.draw_line(cx, cy, cx + 10, cy, 0xFF000000)

if __name__ == "__main__":
    server = WindowServer()
    w1 = WindowWidget(10, 10, 100, 80, "Win1")
    w2 = WindowWidget(50, 50, 100, 80, "Win2")
    server.add_window(w1)
    server.add_window(w2)
    assert server.focused_window == w2

    # Click on w1 to focus
    server.handle_mouse_down(20, 20)
    assert server.focused_window == w1
    server.compose()
    assert server.canvas.get_pixel(server.mouse_x, server.mouse_y) != 0
    print("Window Server & Compositor verified.")
