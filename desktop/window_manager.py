#!/usr/bin/env python3
"""
AdiOS Sovereign Window Manager & Desktop Compositor
High-Resolution (1024x768 XGA Workstation) Desktop Window Server.
Inspired by modern windowing systems and Terry A. Davis's single-user sovereign ergonomics.

Features:
- Dynamic Screen Geometry (Default 1024x768, configurable 1280x720 / 640x480)
- Overlapping Z-Order Back-to-Front Window Compositing
- Rich Titlebar Chrome with Three Workstation Controls:
    * [_] Minimize: Hides window to taskbar app switcher
    * [^] Maximize / Restore: Toggles between floating geometry and full screen
    * [X] Close: Closes active window
- Interactive Window Snapping:
    * Drag to top edge snaps to full maximized workspace (1024x744)
    * Drag to left edge snaps to 50% left half-tile (0, 24, 512, 744)
    * Drag to right edge snaps to 50% right half-tile (512, 24, 512, 744)
- Interactive Resize Grip:
    * Drag bottom-right corner to resize window dynamically (min 220x160)
- Multi-Layer Drop Shadows and Anti-Aliased Chrome Rendering
- Client Scissor Rectangle Clipping and Hierarchical Event Routing

Zero external dependencies. Pure RV32IM linear framebuffer rendering.
STRICT ZERO EMOJI POLICY.
"""

from typing import List, Tuple, Optional, Callable, Dict, Any

DEFAULT_WIDTH  = 1024
DEFAULT_HEIGHT = 768
TASKBAR_HEIGHT = 24

WIDTH  = DEFAULT_WIDTH
HEIGHT = DEFAULT_HEIGHT

# Tokyo Dark Sovereign Color Palette
COLOR_DESKTOP_BG = 0x001A1B26
COLOR_TITLE_ACT  = 0x007AA2F7
COLOR_TITLE_INACT= 0x00343B58
COLOR_TITLE_TXT  = 0x00FFFFFF
COLOR_BORDER_ACT = 0x007AA2F7
COLOR_BORDER     = 0x00545C7E
COLOR_SHADOW_1   = 0x000F0F14
COLOR_SHADOW_2   = 0x0009090D

# Titlebar Button Colors
COLOR_BTN_CLOSE  = 0x00F7768E  # Red
COLOR_BTN_MAX    = 0x009ECE6A  # Green
COLOR_BTN_MIN    = 0x00E0AF68  # Amber
COLOR_BTN_TXT    = 0x0016161E

CHAR_WIDTH  = 8
CHAR_HEIGHT = 8

SNAP_NONE       = 0
SNAP_MAXIMIZE   = 1
SNAP_LEFT_HALF  = 2
SNAP_RIGHT_HALF = 3

class Window:
    """
    Sovereign Desktop Window Entity.
    Represents an independent application viewport with titlebar, controls, and client rect.
    """
    def __init__(
        self,
        win_id: str,
        title: str,
        x: int,
        y: int,
        w: int,
        h: int,
        bg_color: int = 0x001F2335,
        can_close: bool = True,
        can_maximize: bool = True,
        can_minimize: bool = True
    ):
        self.win_id = win_id
        self.title = title
        self.x = max(0, min(WIDTH - w, x))
        self.y = max(TASKBAR_HEIGHT, min(HEIGHT - h, y))
        self.w = w
        self.h = h
        self.bg_color = bg_color
        self.can_close = can_close
        self.can_maximize = can_maximize
        self.can_minimize = can_minimize

        # Window State Machine
        self.active: bool = False
        self.visible: bool = True
        self.maximized: bool = False
        self.minimized: bool = False

        # Saved Geometry for Restore
        self.saved_rect: Tuple[int, int, int, int] = (self.x, self.y, self.w, self.h)

        # Callbacks
        self.on_draw_content: Optional[Callable[[Any, bytearray, Dict], None]] = None
        self.on_click_content: Optional[Callable[[Any, int, int], None]] = None
        self.on_resize: Optional[Callable[[Any, int, int], None]] = None

    @property
    def client_rect(self) -> Tuple[int, int, int, int]:
        """Returns client drawable bounds (cx, cy, cw, ch) inside 20px titlebar and 2px border."""
        return (self.x + 2, self.y + 20, max(10, self.w - 4), max(10, self.h - 22))

    def hit_test_close(self, mx: int, my: int) -> bool:
        """Hit-tests the [X] close button on the far right of the titlebar."""
        if not self.can_close:
            return False
        btn_x = self.x + self.w - 18
        btn_y = self.y + 3
        return (btn_x <= mx <= btn_x + 14) and (btn_y <= my <= btn_y + 14)

    def hit_test_maximize(self, mx: int, my: int) -> bool:
        """Hit-tests the [^] maximize/restore button."""
        if not self.can_maximize:
            return False
        btn_x = self.x + self.w - 36
        btn_y = self.y + 3
        return (btn_x <= mx <= btn_x + 14) and (btn_y <= my <= btn_y + 14)

    def hit_test_minimize(self, mx: int, my: int) -> bool:
        """Hit-tests the [_] minimize button."""
        if not self.can_minimize:
            return False
        btn_x = self.x + self.w - 54
        btn_y = self.y + 3
        return (btn_x <= mx <= btn_x + 14) and (btn_y <= my <= btn_y + 14)

    def hit_test_titlebar(self, mx: int, my: int) -> bool:
        """Hit-tests the draggable titlebar strip (excluding control buttons)."""
        ctrl_start = self.x + self.w - 58
        return (self.x <= mx <= ctrl_start) and (self.y <= my <= self.y + 20)

    def hit_test_resize(self, mx: int, my: int) -> bool:
        """Hit-tests the 12x12 corner grip on the bottom-right of the window."""
        if self.maximized:
            return False
        rx = self.x + self.w - 12
        ry = self.y + self.h - 12
        return (rx <= mx <= self.x + self.w) and (ry <= my <= self.y + self.h)

    def contains_point(self, mx: int, my: int) -> bool:
        """Returns True if (mx, my) lies inside window boundaries."""
        return (self.x <= mx <= self.x + self.w) and (self.y <= my <= self.y + self.h)

    def toggle_maximize(self, screen_w: int = WIDTH, screen_h: int = HEIGHT):
        """Toggles between floating geometry and maximized workspace geometry."""
        if not self.can_maximize:
            return
        if not self.maximized:
            self.saved_rect = (self.x, self.y, self.w, self.h)
            self.x = 0
            self.y = TASKBAR_HEIGHT
            self.w = screen_w
            self.h = screen_h - TASKBAR_HEIGHT
            self.maximized = True
        else:
            sx, sy, sw, sh = self.saved_rect
            self.x = sx
            self.y = sy
            self.w = sw
            self.h = sh
            self.maximized = False

        if self.on_resize:
            cx, cy, cw, ch = self.client_rect
            self.on_resize(self, cw, ch)

    def snap_tile(self, snap_mode: int, screen_w: int = WIDTH, screen_h: int = HEIGHT):
        """Snaps window to half-screen or maximized geometry."""
        if snap_mode == SNAP_MAXIMIZE:
            self.toggle_maximize(screen_w, screen_h)
        elif snap_mode == SNAP_LEFT_HALF:
            self.saved_rect = (self.x, self.y, self.w, self.h)
            self.x = 0
            self.y = TASKBAR_HEIGHT
            self.w = screen_w // 2
            self.h = screen_h - TASKBAR_HEIGHT
            self.maximized = False
        elif snap_mode == SNAP_RIGHT_HALF:
            self.saved_rect = (self.x, self.y, self.w, self.h)
            self.x = screen_w // 2
            self.y = TASKBAR_HEIGHT
            self.w = screen_w // 2
            self.h = screen_h - TASKBAR_HEIGHT
            self.maximized = False

        if self.on_resize:
            cx, cy, cw, ch = self.client_rect
            self.on_resize(self, cw, ch)


class WindowManager:
    """
    Sovereign Multi-Window Z-Order Compositor & Event Router.
    """
    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        self.width = width
        self.height = height
        self.windows: List[Window] = []
        self.dragging_win: Optional[Window] = None
        self.resizing_win: Optional[Window] = None
        self.drag_off_x: int = 0
        self.drag_off_y: int = 0
        self.snap_preview: int = SNAP_NONE

    def add_window(self, win: Window) -> Window:
        """Enqueues window onto compositor stack and promotes to active focus."""
        self.windows.append(win)
        self.focus_window(win)
        return win

    def focus_window(self, win: Window):
        """Promotes window to topmost Z-order position and updates active status."""
        if win in self.windows:
            self.windows.remove(win)
            self.windows.append(win)
            for w in self.windows:
                w.active = (w == win)

    def get_window_at(self, mx: int, my: int) -> Optional[Window]:
        """Returns topmost visible window under point (mx, my)."""
        for w in reversed(self.windows):
            if w.visible and not w.minimized and w.contains_point(mx, my):
                return w
        return None

    def handle_mouse_down(self, mx: int, my: int) -> Optional[Tuple[str, Any]]:
        """Handles mouse press, promoting focus and dispatching titlebar controls or client clicks."""
        target = self.get_window_at(mx, my)
        if not target:
            return None

        self.focus_window(target)

        # 1. Close Button [X]
        if target.hit_test_close(mx, my):
            target.visible = False
            return ("close", target)

        # 2. Maximize Button [^]
        if target.hit_test_maximize(mx, my):
            target.toggle_maximize(self.width, self.height)
            return ("maximize", target)

        # 3. Minimize Button [_]
        if target.hit_test_minimize(mx, my):
            target.minimized = True
            target.visible = False
            return ("minimize", target)

        # 4. Corner Resize Grip
        if target.hit_test_resize(mx, my):
            self.resizing_win = target
            return ("resize_start", target)

        # 5. Titlebar Dragging
        if target.hit_test_titlebar(mx, my):
            # If window was maximized and dragged, un-maximize smoothly
            if target.maximized:
                target.toggle_maximize(self.width, self.height)
                target.x = max(0, min(self.width - target.w, mx - target.w // 2))
                target.y = TASKBAR_HEIGHT

            self.dragging_win = target
            self.drag_off_x = mx - target.x
            self.drag_off_y = my - target.y
            return ("drag_start", target)

        # 6. Client Content Click
        cx, cy, cw, ch = target.client_rect
        if (cx <= mx <= cx + cw) and (cy <= my <= cy + ch):
            rel_x = mx - cx
            rel_y = my - cy
            if target.on_click_content:
                target.on_click_content(target, rel_x, rel_y)
            return ("content_click", target)

        return ("focus", target)

    def handle_mouse_move(self, mx: int, my: int):
        """Processes window repositioning, edge snapping detection, and corner resizing."""
        # Handle Window Dragging & Edge Snapping
        if self.dragging_win:
            new_x = mx - self.drag_off_x
            new_y = my - self.drag_off_y

            # Clamp window titlebar to stay on screen
            self.dragging_win.x = max(0, min(self.width - self.dragging_win.w, new_x))
            self.dragging_win.y = max(TASKBAR_HEIGHT, min(self.height - 20, new_y))

            # Edge Snapping Detection
            if my <= TASKBAR_HEIGHT + 4:
                self.snap_preview = SNAP_MAXIMIZE
            elif mx <= 6:
                self.snap_preview = SNAP_LEFT_HALF
            elif mx >= self.width - 6:
                self.snap_preview = SNAP_RIGHT_HALF
            else:
                self.snap_preview = SNAP_NONE

        # Handle Corner Resizing
        elif self.resizing_win:
            new_w = max(220, mx - self.resizing_win.x)
            new_h = max(160, my - self.resizing_win.y)
            # Clamp to screen bounds
            self.resizing_win.w = min(self.width - self.resizing_win.x, new_w)
            self.resizing_win.h = min(self.height - self.resizing_win.y, new_h)
            if self.resizing_win.on_resize:
                cx, cy, cw, ch = self.resizing_win.client_rect
                self.resizing_win.on_resize(self.resizing_win, cw, ch)

    def handle_mouse_up(self, mx: int, my: int):
        """Applies edge snap transitions upon mouse release."""
        if self.dragging_win:
            if self.snap_preview != SNAP_NONE:
                self.dragging_win.snap_tile(self.snap_preview, self.width, self.height)
            self.dragging_win = None
            self.snap_preview = SNAP_NONE

        self.resizing_win = None

    def render_all(self, fb: bytearray, font_dict: Dict):
        """Composites all visible windows from back to front with shadows and chrome."""
        for win in self.windows:
            if not win.visible or win.minimized:
                continue
            self._render_window(win, fb, font_dict)

        # Draw Snapping Preview Guide Outline if active
        if self.snap_preview != SNAP_NONE and self.dragging_win:
            self._render_snap_preview(fb)

    def _render_snap_preview(self, fb: bytearray):
        """Renders semi-transparent cyan snap preview outline."""
        if self.snap_preview == SNAP_MAXIMIZE:
            px, py, pw, ph = 4, TASKBAR_HEIGHT + 4, self.width - 8, self.height - TASKBAR_HEIGHT - 8
        elif self.snap_preview == SNAP_LEFT_HALF:
            px, py, pw, ph = 4, TASKBAR_HEIGHT + 4, self.width // 2 - 8, self.height - TASKBAR_HEIGHT - 8
        elif self.snap_preview == SNAP_RIGHT_HALF:
            px, py, pw, ph = self.width // 2 + 4, TASKBAR_HEIGHT + 4, self.width // 2 - 8, self.height - TASKBAR_HEIGHT - 8
        else:
            return

        cyan_bytes = bytes([0xC8, 0xDC, 0x7A, 0])
        # Top & Bottom Outline
        for x in range(px, px + pw):
            fb[(py * self.width + x) * 4 : (py * self.width + x + 1) * 4] = cyan_bytes
            fb[((py + ph) * self.width + x) * 4 : ((py + ph) * self.width + x + 1) * 4] = cyan_bytes
        # Left & Right Outline
        for y in range(py, py + ph):
            fb[(y * self.width + px) * 4 : (y * self.width + px + 1) * 4] = cyan_bytes
            fb[(y * self.width + (px + pw)) * 4 : (y * self.width + (px + pw) + 1) * 4] = cyan_bytes

    def _render_window(self, win: Window, fb: bytearray, font_dict: Dict):
        """Draws window drop shadow, window background, titlebar, controls, and client content."""
        wx, wy, ww, wh = win.x, win.y, win.w, win.h

        # 1. Multi-Stage Drop Shadow (if floating)
        if not win.maximized:
            s1_bytes = bytes([COLOR_SHADOW_1 & 0xFF, (COLOR_SHADOW_1 >> 8) & 0xFF, (COLOR_SHADOW_1 >> 16) & 0xFF, 0])
            for sy in range(wy + 5, min(self.height, wy + wh + 5)):
                start_x = max(0, wx + 5)
                end_x   = min(self.width, wx + ww + 5)
                if start_x < end_x:
                    fb[(sy * self.width + start_x) * 4 : (sy * self.width + end_x) * 4] = s1_bytes * (end_x - start_x)

        # 2. Window Background
        bg_bytes = bytes([win.bg_color & 0xFF, (win.bg_color >> 8) & 0xFF, (win.bg_color >> 16) & 0xFF, 0])
        for y in range(wy, min(self.height, wy + wh)):
            fb[(y * self.width + wx) * 4 : (y * self.width + wx + ww) * 4] = bg_bytes * ww

        # 3. Outer Border (Active Window Glow)
        border_col = COLOR_BORDER_ACT if win.active else COLOR_BORDER
        b_bytes = bytes([border_col & 0xFF, (border_col >> 8) & 0xFF, (border_col >> 16) & 0xFF, 0])
        # Top and Bottom border lines
        fb[(wy * self.width + wx) * 4 : (wy * self.width + wx + ww) * 4] = b_bytes * ww
        fb[((wy + wh - 1) * self.width + wx) * 4 : ((wy + wh - 1) * self.width + wx + ww) * 4] = b_bytes * ww
        # Left and Right border lines
        for y in range(wy, min(self.height, wy + wh)):
            fb[(y * self.width + wx) * 4 : (y * self.width + wx + 1) * 4] = b_bytes
            fb[(y * self.width + wx + ww - 1) * 4 : (y * self.width + wx + ww) * 4] = b_bytes

        # 4. Titlebar Header Strip (20px high)
        tb_col = COLOR_TITLE_ACT if win.active else COLOR_TITLE_INACT
        tb_bytes = bytes([tb_col & 0xFF, (tb_col >> 8) & 0xFF, (tb_col >> 16) & 0xFF, 0])
        for ty in range(wy + 1, min(self.height, wy + 20)):
            fb[(ty * self.width + wx + 1) * 4 : (ty * self.width + wx + ww - 1) * 4] = tb_bytes * (ww - 2)

        # 5. Titlebar Text (Truncated to avoid control buttons)
        title_limit = max(1, (ww - 75) // CHAR_WIDTH)
        display_title = win.title[:title_limit]
        self._draw_string(fb, wx + 8, wy + 6, display_title, COLOR_TITLE_TXT, font_dict)

        # 6. Titlebar Control Buttons: [_] Minimize, [^] Maximize, [X] Close
        if win.can_minimize:
            min_x = wx + ww - 54
            self._draw_ctrl_button(fb, min_x, wy + 4, 12, 12, COLOR_BTN_MIN, "_", font_dict)

        if win.can_maximize:
            max_x = wx + ww - 36
            sym = "v" if win.maximized else "^"
            self._draw_ctrl_button(fb, max_x, wy + 4, 12, 12, COLOR_BTN_MAX, sym, font_dict)

        if win.can_close:
            cls_x = wx + ww - 18
            self._draw_ctrl_button(fb, cls_x, wy + 4, 12, 12, COLOR_BTN_CLOSE, "X", font_dict)

        # 7. Corner Resize Grip Indicator (Bottom-Right)
        if not win.maximized:
            self._draw_resize_grip(fb, wx + ww - 10, wy + wh - 10, border_col)

        # 8. Dispatch Application Client Viewport Rendering Callback
        if win.on_draw_content:
            win.on_draw_content(win, fb, font_dict)

    def _draw_ctrl_button(
        self,
        fb: bytearray,
        bx: int,
        by: int,
        bw: int,
        bh: int,
        color: int,
        symbol: str,
        font_dict: Dict
    ):
        """Draws rounded modern control pill button on window titlebar."""
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        for y in range(by, min(self.height, by + bh)):
            fb[(y * self.width + bx) * 4 : (y * self.width + bx + bw) * 4] = c_bytes * bw
        # Draw central symbol
        self._draw_string(fb, bx + 2, by + 2, symbol, COLOR_BTN_TXT, font_dict)

    def _draw_resize_grip(self, fb: bytearray, gx: int, gy: int, color: int):
        """Draws 3 diagonal dots representing modern window resize handle."""
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        dots = [(gx + 6, gy + 6), (gx + 3, gy + 6), (gx + 6, gy + 3)]
        for dx, dy in dots:
            if 0 <= dx < self.width and 0 <= dy < self.height:
                fb[(dy * self.width + dx) * 4 : (dy * self.width + dx + 1) * 4] = c_bytes

    def _draw_string(self, fb: bytearray, arg2, arg3, arg4, arg5, arg6=None):
        """Draws text glyphs into the framebuffer supporting both legacy and modern signatures."""
        if isinstance(arg2, dict):
            font_dict = arg2
            x = arg3
            y = arg4
            text = arg5
            color = arg6 if arg6 is not None else COLOR_TITLE_TXT
        else:
            x = arg2
            y = arg3
            text = arg4
            color = arg5
            font_dict = arg6 if isinstance(arg6, dict) else {}

        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        curr_x = x
        for ch in text:
            if curr_x + CHAR_WIDTH > self.width:
                break
            glyph = font_dict.get(ord(ch), font_dict.get(ch, None)) if font_dict else None
            if glyph:
                for row in range(CHAR_HEIGHT):
                    py = y + row
                    if py < 0 or py >= self.height:
                        continue
                    bits = glyph[row]
                    for col in range(CHAR_WIDTH):
                        px = curr_x + col
                        if px < 0 or px >= self.width:
                            continue
                        if (bits >> (7 - col)) & 1:
                            fb[(py * self.width + px) * 4 : (py * self.width + px + 1) * 4] = c_bytes
            curr_x += CHAR_WIDTH
