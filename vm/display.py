#!/usr/bin/env python3
"""
AdiOS Virtual Graphics Adapter (VGA) & Mouse Controller
Paravirtualized 640x480 32-bit ARGB Framebuffer + Mouse/Keyboard Controller
Uses Python's built-in Tkinter library (Zero External Dependencies).
"""

import tkinter as tk
import struct
import time
import sys

FB_WIDTH  = 640
FB_HEIGHT = 480
FB_SIZE   = FB_WIDTH * FB_HEIGHT * 4 # 1,228,800 bytes

class DisplayWindow:
    def __init__(self, fb_memory, uart_callback=None):
        self.fb = fb_memory # Shared bytearray from VM
        self.uart_cb = uart_callback

        self.mouse_x = 320
        self.mouse_y = 240
        self.mouse_buttons = 0 # bit 0: Left, bit 1: Right
        self.mouse_event = 0

        self.root = tk.Tk()
        self.root.title("AdiOS v0.2.0 - Desktop Windowing System")
        self.root.geometry(f"{FB_WIDTH}x{FB_HEIGHT}")
        self.root.resizable(False, False)

        # High-performance Canvas
        self.canvas = tk.Canvas(self.root, width=FB_WIDTH, height=FB_HEIGHT, bg="#11111B", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.img = tk.PhotoImage(width=FB_WIDTH, height=FB_HEIGHT)
        self.img_item = self.canvas.create_image(0, 0, image=self.img, anchor=tk.NW)

        # Event bindings
        self.root.bind("<Motion>", self._on_mouse_move)
        self.root.bind("<ButtonPress-1>", self._on_lbutton_down)
        self.root.bind("<ButtonRelease-1>", self._on_lbutton_up)
        self.root.bind("<ButtonPress-3>", self._on_rbutton_down)
        self.root.bind("<ButtonRelease-3>", self._on_rbutton_up)
        self.root.bind("<Key>", self._on_key)

        self.closed = False
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.closed = True
        self.root.destroy()

    def _on_mouse_move(self, event):
        self.mouse_x = max(0, min(FB_WIDTH - 1, event.x))
        self.mouse_y = max(0, min(FB_HEIGHT - 1, event.y))
        self.mouse_event = 1

    def _on_lbutton_down(self, event):
        self.mouse_buttons |= 0x01
        self.mouse_event = 1

    def _on_lbutton_up(self, event):
        self.mouse_buttons &= ~0x01
        self.mouse_event = 1

    def _on_rbutton_down(self, event):
        self.mouse_buttons |= 0x02
        self.mouse_event = 1

    def _on_rbutton_up(self, event):
        self.mouse_buttons &= ~0x02
        self.mouse_event = 1

    def _on_key(self, event):
        if not self.uart_cb:
            return
        if event.char:
            c = ord(event.char)
            if c == 13: c = 10 # Convert Enter
            self.uart_cb(c)
        elif event.keysym == "BackSpace":
            self.uart_cb(8)
        elif event.keysym == "Return":
            self.uart_cb(10)

    def render_frame(self):
        """Blits the raw 32-bit ARGB framebuffer to the Tkinter PhotoImage using PPM format."""
        if self.closed:
            return
        try:
            # Convert 32-bit 0x00RRGGBB / 0x00BBGGRR memory into PPM P6 binary stream
            # PPM P6 format: P6\n640 480\n255\n<RGB binary data>
            # Extract R, G, B channels from 4-byte pixels
            ppm_header = f"P6 {FB_WIDTH} {FB_HEIGHT} 255\n".encode('ascii')
            
            # Slice memory view for maximum speed
            # Framebuffer memory layout per pixel: [B, G, R, A] (little endian uint32: 0x00RRGGBB)
            raw = self.fb[:FB_SIZE]
            # Fast vectorized RGB extraction using slice or byte swap
            # In little-endian: byte 2 is R, byte 1 is G, byte 0 is B
            # We can use a bytearray view
            rgb = bytearray(FB_WIDTH * FB_HEIGHT * 3)
            rgb[0::3] = raw[2::4] # Red
            rgb[1::3] = raw[1::4] # Green
            rgb[2::3] = raw[0::4] # Blue

            self.img.put(ppm_header + rgb)
        except Exception:
            pass

    def update(self):
        if self.closed:
            return False
        try:
            self.root.update_idletasks()
            self.root.update()
            return True
        except Exception:
            self.closed = True
            return False
