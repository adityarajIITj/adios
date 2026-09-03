#!/usr/bin/env python3
"""
AdiOS Sovereign Window Manager & Desktop Compositor
Inspired by modern windowing systems and TempleOS single-user sovereign ergonomics.
Features:
- Overlapping windows with back-to-front Z-order compositing
- Title bars, accent borders, drop shadows, and close buttons [X]
- Mouse drag-and-drop window movement
- Click-to-focus window management
- Client area clipping and event routing
"""

WIDTH  = 640
HEIGHT = 480

COLOR_DESKTOP_BG = 0x001A1B26
COLOR_TITLE_ACT  = 0x007AA2F7
COLOR_TITLE_INACT= 0x0024283B
COLOR_TITLE_TXT  = 0x00FFFFFF
COLOR_BORDER     = 0x00414868
COLOR_CLOSE_BTN  = 0x00F7768E
COLOR_SHADOW     = 0x000F0F14

CHAR_WIDTH  = 8
CHAR_HEIGHT = 8

class Window:
    def __init__(self, win_id, title, x, y, w, h, bg_color=0x001F2335, can_close=True):
        self.win_id = win_id
        self.title = title
        self.x = max(0, min(WIDTH - w, x))
        self.y = max(24, min(HEIGHT - h, y))
        self.w = w
        self.h = h
        self.bg_color = bg_color
        self.can_close = can_close
        self.active = False
        self.visible = True
        self.on_draw_content = None # callback: fn(window, fb, font_dict)
        self.on_click_content = None # callback: fn(window, rel_x, rel_y)

    @property
    def client_rect(self):
        # Client area inside border and below 20px titlebar
        return (self.x + 2, self.y + 20, self.w - 4, self.h - 22)

    def hit_test_close(self, mx, my):
        if not self.can_close: return False
        btn_x = self.x + self.w - 18
        btn_y = self.y + 3
        return (btn_x <= mx <= btn_x + 14) and (btn_y <= my <= btn_y + 14)

    def hit_test_titlebar(self, mx, my):
        return (self.x <= mx <= self.x + self.w) and (self.y <= my <= self.y + 20)

    def contains_point(self, mx, my):
        return (self.x <= mx <= self.x + self.w) and (self.y <= my <= self.y + self.h)

class WindowManager:
    def __init__(self):
        self.windows = [] # Back-to-front list
        self.dragging_win = None
        self.drag_off_x = 0
        self.drag_off_y = 0

    def add_window(self, win):
        self.windows.append(win)
        self.focus_window(win)
        return win

    def focus_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
            self.windows.append(win)
            for w in self.windows:
                w.active = (w == win)

    def get_window_at(self, mx, my):
        """Returns the topmost visible window under (mx, my)."""
        for w in reversed(self.windows):
            if w.visible and w.contains_point(mx, my):
                return w
        return None

    def handle_mouse_down(self, mx, my):
        target = self.get_window_at(mx, my)
        if not target:
            return None

        self.focus_window(target)

        # Check Close Button
        if target.hit_test_close(mx, my):
            target.visible = False
            return ("close", target)

        # Check Titlebar Drag
        if target.hit_test_titlebar(mx, my):
            self.dragging_win = target
            self.drag_off_x = mx - target.x
            self.drag_off_y = my - target.y
            return ("drag_start", target)

        # Content Click
        cx, cy, cw, ch = target.client_rect
        if (cx <= mx <= cx + cw) and (cy <= my <= cy + ch):
            rel_x = mx - cx
            rel_y = my - cy
            if target.on_click_content:
                target.on_click_content(target, rel_x, rel_y)
            return ("content_click", target)

        return ("focus", target)

    def handle_mouse_move(self, mx, my):
        if self.dragging_win:
            new_x = mx - self.drag_off_x
            new_y = my - self.drag_off_y
            # Clamp to screen bounds (below 24px taskbar)
            self.dragging_win.x = max(0, min(WIDTH - self.dragging_win.w, new_x))
            self.dragging_win.y = max(24, min(HEIGHT - self.dragging_win.h, new_y))

    def handle_mouse_up(self, mx, my):
        self.dragging_win = None

    def render_all(self, fb, font_dict):
        """Composites all visible windows from back to front with shadows and chrome."""
        for win in self.windows:
            if not win.visible: continue
            self._render_window(win, fb, font_dict)

    def _render_window(self, win, fb, font_dict):
        wx, wy, ww, wh = win.x, win.y, win.w, win.h

        # 1. Drop Shadow (offset +4, +4)
        shadow_bytes = bytes([COLOR_SHADOW & 0xFF, (COLOR_SHADOW >> 8) & 0xFF, (COLOR_SHADOW >> 16) & 0xFF, 0])
        for sy in range(wy + 4, min(HEIGHT, wy + wh + 4)):
            start_x = max(0, wx + 4)
            end_x   = min(WIDTH, wx + ww + 4)
            if start_x < end_x:
                off = (sy * WIDTH + start_x) * 4
                fb[off : off + (end_x - start_x) * 4] = shadow_bytes * (end_x - start_x)

        # 2. Window Background
        bg_bytes = bytes([win.bg_color & 0xFF, (win.bg_color >> 8) & 0xFF, (win.bg_color >> 16) & 0xFF, 0])
        for py in range(wy, min(HEIGHT, wy + wh)):
            start_x = max(0, wx)
            end_x   = min(WIDTH, wx + ww)
            if start_x < end_x:
                off = (py * WIDTH + start_x) * 4
                fb[off : off + (end_x - start_x) * 4] = bg_bytes * (end_x - start_x)

        # 3. Titlebar (20px high)
        title_bg = COLOR_TITLE_ACT if win.active else COLOR_TITLE_INACT
        title_bytes = bytes([title_bg & 0xFF, (title_bg >> 8) & 0xFF, (title_bg >> 16) & 0xFF, 0])
        for ty in range(wy, min(HEIGHT, wy + 20)):
            off = (ty * WIDTH + wx) * 4
            fb[off : off + ww * 4] = title_bytes * ww

        # Title text
        self._draw_string(fb, font_dict, wx + 8, wy + 6, win.title[:28], COLOR_TITLE_TXT)

        # Close button [X]
        if win.can_close:
            close_x = wx + ww - 16
            close_y = wy + 4
            close_bg = bytes([COLOR_CLOSE_BTN & 0xFF, (COLOR_CLOSE_BTN >> 8) & 0xFF, (COLOR_CLOSE_BTN >> 16) & 0xFF, 0])
            for cy in range(close_y, close_y + 12):
                off = (cy * WIDTH + close_x) * 4
                fb[off : off + 12 * 4] = close_bg * 12
            self._draw_string(fb, font_dict, close_x + 3, close_y + 2, "X", 0x00FFFFFF)

        # 4. Window Border (1px outline)
        border_bytes = bytes([COLOR_BORDER & 0xFF, (COLOR_BORDER >> 8) & 0xFF, (COLOR_BORDER >> 16) & 0xFF, 0])
        # Top & bottom lines
        for bx in range(wx, wx + ww):
            if 0 <= bx < WIDTH:
                if 0 <= wy < HEIGHT: fb[(wy * WIDTH + bx) * 4 : (wy * WIDTH + bx) * 4 + 4] = border_bytes
                if 0 <= wy + wh - 1 < HEIGHT: fb[((wy + wh - 1) * WIDTH + bx) * 4 : ((wy + wh - 1) * WIDTH + bx) * 4 + 4] = border_bytes
        # Left & right lines
        for by in range(wy, wy + wh):
            if 0 <= by < HEIGHT:
                if 0 <= wx < WIDTH: fb[(by * WIDTH + wx) * 4 : (by * WIDTH + wx) * 4 + 4] = border_bytes
                if 0 <= wx + ww - 1 < WIDTH: fb[(by * WIDTH + (wx + ww - 1)) * 4 : (by * WIDTH + (wx + ww - 1)) * 4 + 4] = border_bytes

        # 5. Client Content Callback
        if win.on_draw_content:
            win.on_draw_content(win, fb, font_dict)

    def _draw_string(self, fb, font_dict, x, y, text, color):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        for idx, ch in enumerate(text):
            bitmap = font_dict.get(ch, font_dict.get(" ", b"\x00"*8))
            px = x + idx * CHAR_WIDTH
            if px + CHAR_WIDTH > WIDTH: break

            for row in range(CHAR_HEIGHT):
                py = y + row
                if py >= HEIGHT: break
                byte_val = bitmap[row]
                for col in range(CHAR_WIDTH):
                    if (byte_val >> (7 - col)) & 1:
                        off = (py * WIDTH + (px + col)) * 4
                        fb[off : off + 4] = c_bytes
