#!/usr/bin/env python3
"""
AdiOS Virtual Graphics Adapter (VGA), Mouse & Keyboard Controller
Paravirtualized High-Resolution 32-bit ARGB Linear Framebuffer + Input Subsystem.
Zero External Dependencies (Standard Python 3 Tkinter).

Architecture:
- Configurable Native Resolutions:
    * 1024x768 (Default Sovereign Workstation XGA - 3,145,728 bytes VRAM)
    * 1280x720 (720p HD Sovereign Display - 3,686,400 bytes VRAM)
    * 640x480  (Legacy VGA Compatibility - 1,228,800 bytes VRAM)
- High-DPI Display Scaling Engine:
    * Supports scale factors (1.0x, 1.5x, 2.0x) with hardware-accelerated integer zoom
    * Automatic mouse coordinate inverse scaling: (screen_x / scale, screen_y / scale)
- Optimized Video Blitter:
    * Direct Little-Endian ARGB memory extraction to PPM P6 binary stream
    * Vectorized byte slice mapping: Red (byte 2), Green (byte 1), Blue (byte 0)
- Paravirtualized Input Registers (MMIO 0x20130000):
    * Mouse position (X, Y), Left/Right button bitmask, Click edge detection
    * Keyboard UART character FIFO ring buffer with Enter/Backspace translation
- Interactive Callback Architecture:
    * Direct hook dispatch for Master Desktop Compositor without polling lag
STRICT ZERO EMOJI POLICY.
"""

import tkinter as tk
import struct
import time
import sys
from typing import Optional, Callable

# Standard Display Profiles
RES_XGA = (1024, 768)
RES_HD  = (1280, 720)
RES_VGA = (640, 480)

DEFAULT_WIDTH  = 1280
DEFAULT_HEIGHT = 720

class DisplayWindow:
    """
    Paravirtualized Framebuffer Display and Input Controller.
    Bridges the bare-metal linear VRAM buffer to the host desktop environment.
    """
    def __init__(
        self,
        fb_memory: bytearray,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        scale: float = 1.0,
        uart_callback: Optional[Callable[[int], None]] = None,
        title: str = "AdiOS Sovereign Workstation (1280x720 HD 60 FPS)"
    ):
        self.fb = fb_memory
        self.width = width
        self.height = height
        self.scale = max(0.5, float(scale))
        self.uart_cb = uart_callback
        self.fb_size = self.width * self.height * 4

        # MMIO Status Registers
        self.mouse_x = self.width // 2
        self.mouse_y = self.height // 2
        self.mouse_buttons = 0  # Bit 0: Left, Bit 1: Right, Bit 2: Middle
        self.mouse_event = 0

        # High-Resolution Callback Hooks
        self.on_mouse_down_cb: Optional[Callable[[int, int], None]] = None
        self.on_mouse_up_cb: Optional[Callable[[int, int], None]] = None
        self.on_mouse_move_cb: Optional[Callable[[int, int], None]] = None
        self.on_mouse_drag_cb: Optional[Callable[[int, int], None]] = None
        self.on_key_cb: Optional[Callable[[str], None]] = None

        # Performance & Telemetry Diagnostics
        self.frames_rendered = 0
        self.last_fps_time = time.time()
        self.current_fps = 0.0
        self.blit_time_ms = 0.0

        # Calculate Canvas & Window Dimensions
        self.canvas_w = int(self.width * self.scale)
        self.canvas_h = int(self.height * self.scale)

        # Tkinter Host Initialization
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{self.canvas_w}x{self.canvas_h}")
        self.root.resizable(False, False)

        # Configure High-Contrast Modern Workstation Frame
        self.canvas = tk.Canvas(
            self.root,
            width=self.canvas_w,
            height=self.canvas_h,
            bg="#16161E",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Base Image Buffer
        self.img = tk.PhotoImage(width=self.width, height=self.height)
        
        # Determine whether scaling requires Tkinter PhotoImage zoom
        self.use_zoom = (self.scale >= 2.0 and int(self.scale) == self.scale)
        if self.use_zoom:
            self.scaled_img = self.img.zoom(int(self.scale), int(self.scale))
            self.img_item = self.canvas.create_image(0, 0, image=self.scaled_img, anchor=tk.NW)
        else:
            self.img_item = self.canvas.create_image(0, 0, image=self.img, anchor=tk.NW)

        # Precompute PPM P6 Header
        self.ppm_header = f"P6 {self.width} {self.height} 255\n".encode('ascii')
        self.rgb_buffer = bytearray(self.width * self.height * 3)

        # Bind Core User Input Handlers
        self._bind_events()

        self.closed = False
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_events(self):
        """Binds all mouse and keyboard events to high-performance internal dispatchers."""
        self.root.bind("<Motion>", self._on_mouse_move)
        self.root.bind("<ButtonPress-1>", self._on_lbutton_down)
        self.root.bind("<ButtonRelease-1>", self._on_lbutton_up)
        self.root.bind("<B1-Motion>", self._on_lbutton_drag)
        self.root.bind("<ButtonPress-2>", self._on_mbutton_down)
        self.root.bind("<ButtonRelease-2>", self._on_mbutton_up)
        self.root.bind("<ButtonPress-3>", self._on_rbutton_down)
        self.root.bind("<ButtonRelease-3>", self._on_rbutton_up)
        self.root.bind("<Key>", self._on_key)

    def _map_coords(self, event_x: int, event_y: int) -> tuple[int, int]:
        """Maps host window coordinates back to bare-metal framebuffer coordinates."""
        if self.scale != 1.0:
            fx = int(event_x / self.scale)
            fy = int(event_y / self.scale)
        else:
            fx = event_x
            fy = event_y
        mx = max(0, min(self.width - 1, fx))
        my = max(0, min(self.height - 1, fy))
        return mx, my

    def _on_close(self):
        """Performs clean graphical teardown."""
        self.closed = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def _on_mouse_move(self, event):
        mx, my = self._map_coords(event.x, event.y)
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_event = 1

        # Dynamic Cursor Styling for Sovereign Ergonomics
        if my < 26:
            self.root.config(cursor="hand2")
        else:
            self.root.config(cursor="arrow")

        if self.on_mouse_move_cb:
            self.on_mouse_move_cb(mx, my)

    def _on_lbutton_down(self, event):
        mx, my = self._map_coords(event.x, event.y)
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_buttons |= 0x01
        self.mouse_event = 1

        if self.on_mouse_down_cb:
            self.on_mouse_down_cb(mx, my)

    def _on_lbutton_up(self, event):
        mx, my = self._map_coords(event.x, event.y)
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_buttons &= ~0x01
        self.mouse_event = 1

        if self.on_mouse_up_cb:
            self.on_mouse_up_cb(mx, my)

    def _on_lbutton_drag(self, event):
        mx, my = self._map_coords(event.x, event.y)
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_buttons |= 0x01
        self.mouse_event = 1

        if self.on_mouse_drag_cb:
            self.on_mouse_drag_cb(mx, my)
        elif self.on_mouse_move_cb:
            self.on_mouse_move_cb(mx, my)

    def _on_mbutton_down(self, event):
        self.mouse_buttons |= 0x04
        self.mouse_event = 1

    def _on_mbutton_up(self, event):
        self.mouse_buttons &= ~0x04
        self.mouse_event = 1

    def _on_rbutton_down(self, event):
        mx, my = self._map_coords(event.x, event.y)
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_buttons |= 0x02
        self.mouse_event = 1

    def _on_rbutton_up(self, event):
        mx, my = self._map_coords(event.x, event.y)
        self.mouse_x = mx
        self.mouse_y = my
        self.mouse_buttons &= ~0x02
        self.mouse_event = 1

    def _on_key(self, event):
        # Check for Ctrl+V clipboard paste
        is_ctrl_v = (event.char == "\x16") or (event.keysym.lower() == "v" and (event.state & 4))
        if is_ctrl_v:
            clip_text = None
            try:
                clip_text = self.root.clipboard_get()
            except Exception:
                pass
            if not clip_text:
                try:
                    from desktop.youtube_player import get_system_clipboard_text
                    clip_text = get_system_clipboard_text()
                except Exception:
                    pass
            if clip_text and self.on_key_cb:
                self.on_key_cb(clip_text)
                return

        # 1. Forward to master desktop direct callback
        if self.on_key_cb:
            if event.char and len(event.char) == 1 and 32 <= ord(event.char) <= 126:
                self.on_key_cb(event.char)
            elif event.keysym == "BackSpace":
                self.on_key_cb("\b")
            elif event.keysym == "Return":
                self.on_key_cb("\n")
            elif event.keysym == "Escape":
                self.on_key_cb("\x1b")
            elif event.keysym == "Tab":
                self.on_key_cb("\t")
            elif event.keysym in ("Up", "Down", "Left", "Right"):
                self.on_key_cb(f"KEY_{event.keysym.upper()}")

        # 2. Forward to paravirtualized UART console FIFO
        if self.uart_cb:
            if event.char:
                c = ord(event.char)
                if c == 13: c = 10
                self.uart_cb(c)
            elif event.keysym == "BackSpace":
                self.uart_cb(8)
            elif event.keysym == "Return":
                self.uart_cb(10)

    def render_frame(self):
        """
        Blits the 32-bit ARGB framebuffer to the PhotoImage using vectorized slice transfers.
        In little-endian RISC-V VRAM: byte 0 is Blue, byte 1 is Green, byte 2 is Red, byte 3 is Alpha.
        PPM P6 format requires raw [R, G, B] binary sequence.
        """
        if self.closed:
            return

        t_start = time.time()
        try:
            raw = memoryview(self.fb)[:self.fb_size]
            # Vectorized color channel extraction (no Python per-pixel loop)
            self.rgb_buffer[0::3] = raw[2::4]  # Red
            self.rgb_buffer[1::3] = raw[1::4]  # Green
            self.rgb_buffer[2::3] = raw[0::4]  # Blue

            # Blit binary stream to Tkinter PhotoImage
            self.img.put(self.ppm_header + self.rgb_buffer)

            # Update zoomed surface if integer scaling is active
            if self.use_zoom:
                self.scaled_img = self.img.zoom(int(self.scale), int(self.scale))
                self.canvas.itemconfig(self.img_item, image=self.scaled_img)

            self.frames_rendered += 1
            now = time.time()
            self.blit_time_ms = (now - t_start) * 1000.0

            # Calculate rolling average FPS every 1.0 second
            if now - self.last_fps_time >= 1.0:
                self.current_fps = self.frames_rendered / (now - self.last_fps_time)
                self.frames_rendered = 0
                self.last_fps_time = now

        except Exception:
            pass

    def update(self) -> bool:
        """Processes pending Tkinter GUI event loop tasks."""
        if self.closed:
            return False
        try:
            self.root.update_idletasks()
            self.root.update()
            return True
        except Exception:
            self.closed = True
            return False

    def set_title(self, title: str):
        """Updates window title bar text dynamically."""
        if not self.closed:
            try:
                self.root.title(title)
            except Exception:
                pass
