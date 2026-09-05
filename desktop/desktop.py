#!/usr/bin/env python3
"""
AdiOS Sovereign Desktop Environment
Integrates:
- Top Taskbar with Start Pill, System Status, and Window switcher
- DolDoc Interactive Terminal Window with Clickable App Hyperlinks
- 3D Rotating Mesh Viewport Window (TempleOS 3D Wireframe / Flat-Shaded)
- AdiFS Virtual Disk File Manager Window
- Bare-Metal Paint Studio Window
"""

import time
import math
from .window_manager import WindowManager, Window, WIDTH, HEIGHT, CHAR_WIDTH, CHAR_HEIGHT
from doldoc import DolDocument, DocLink, DocButton
from graphics import Engine3D, Vector3, create_temple_pyramid, create_cube
from fs.adifs import AdiFS

COLOR_TASKBAR_BG = 0x0016161E
COLOR_TASKBAR_BORDER = 0x00292E42
COLOR_START_PILL = 0x007AA2F7
COLOR_START_TXT  = 0x00FFFFFF

class SovereignDesktop:
    def __init__(self, vm=None, font_dict=None):
        self.vm = vm
        self.font_dict = font_dict or {}
        self.wm = WindowManager()
        self.engine3d = Engine3D(vm, width=WIDTH, height=HEIGHT)
        self.adifs = AdiFS("disk.img")
        self.pyramid_mesh = create_temple_pyramid(base=70, height=65)
        self.rot_angle = 0.0
        self.start_menu_open = False
        self.status_message = "AdiOS Sovereign Desktop Ready."

        self._setup_windows()

    def _setup_windows(self):
        # 1. DolDoc Terminal & Launcher Window
        self.win_term = Window("term", "DolDoc Terminal & Launcher", 20, 35, 340, 220)
        self.doc = DolDocument(max_cols=40, max_rows=22)
        intro = (
            "$RED$AdiOS v1.0 Sovereign Terminal$DEFAULT$\n"
            "DolDoc Hypertext Subsystem Active.\n\n"
            "Click an application to launch:\n"
            "  * $LK,\"StarFlight 3D Flight Sim\",A=\"flight3d\"$\n"
            "  * $LK,\"Play Hymn of AdiOS\",A=\"play_hymn\"$\n"
            "  * $LK,\"Run 3D Cube Script\",A=\"cube3d\"$\n"
            "  * $LK,\"Refresh Virtual Disk\",A=\"refresh_disk\"$\n\n"
            "System: $CYAN$Ring-0 God Mode Active$DEFAULT$\n"
        )
        self.doc.load_stream(intro)
        self.win_term.on_draw_content = self._draw_term_content
        self.win_term.on_click_content = self._click_term_content
        self.wm.add_window(self.win_term)

        # 2. 3D Viewport Window (Rotating Temple Pyramid)
        self.win_3d = Window("3d", "3D Model Viewport (Temple)", 380, 35, 240, 220)
        self.win_3d.on_draw_content = self._draw_3d_content
        self.wm.add_window(self.win_3d)

        # 3. AdiFS Virtual Disk Explorer Window
        self.win_fs = Window("fs", "AdiFS Virtual Disk Explorer", 20, 270, 340, 190)
        self.win_fs.on_draw_content = self._draw_fs_content
        self.wm.add_window(self.win_fs)

        # 4. Paint Studio Window
        self.win_paint = Window("paint", "Paint Studio", 380, 270, 240, 190)
        self.win_paint.on_draw_content = self._draw_paint_content
        self.wm.add_window(self.win_paint)

    # --------------------------------------------------------------------------
    # Content Drawing Callbacks
    # --------------------------------------------------------------------------

    def _draw_term_content(self, win, fb, font_dict):
        cx, cy, cw, ch = win.client_rect
        self.doc.render_to_framebuffer(fb, font_dict, cx + 4, cy + 4, screen_w=WIDTH)

    def _click_term_content(self, win, rel_x, rel_y):
        hit = self.doc.hit_test(rel_x - 4, rel_y - 4)
        if isinstance(hit, DocLink):
            if hit.target == "flight3d":
                self.status_message = "Launching StarFlight 3D Game..."
            elif hit.target == "play_hymn":
                self.status_message = "Playing Hymn of AdiOS..."
                if self.vm:
                    from audio import AudioTracker, HYMN_OF_ADIOS
                    tracker = AudioTracker(self.vm)
                    tracker.play_track(HYMN_OF_ADIOS, sleep_between=False)
            elif hit.target == "cube3d":
                self.status_message = "Executing cube3d.ap via AdiPython..."
            elif hit.target == "refresh_disk":
                self.status_message = "Refreshed AdiFS virtual disk."

    def _draw_3d_content(self, win, fb, font_dict):
        cx, cy, cw, ch = win.client_rect
        center_x = cx + cw // 2
        center_y = cy + ch // 2
        clip = (cx + 1, cy + 1, cx + cw - 1, cy + ch - 1)

        # Rotate Temple Pyramid
        pos = Vector3(0, 0, 160)
        rot = Vector3(20, self.rot_angle, 0)

        # Render 3D mesh directly into the window area with strict client clipping
        self.engine3d.render_mesh(
            self.pyramid_mesh,
            pos=pos,
            rot=rot,
            wireframe=False,
            center_x=center_x,
            center_y=center_y,
            clip_rect=clip,
            fb=fb
        )

    def _draw_fs_content(self, win, fb, font_dict):
        cx, cy, cw, ch = win.client_rect
        # Draw header
        header = "NAME               SECTOR  SIZE"
        self.wm._draw_string(fb, font_dict, cx + 6, cy + 6, header, 0x007AA2F7)
        sep = "-" * 32
        self.wm._draw_string(fb, font_dict, cx + 6, cy + 18, sep, 0x00414868)

        # List files from AdiFS
        try:
            files = self.adifs.list_files()
            for idx, f in enumerate(files[:8]):
                line = f"{f.name:<18} {f.start_sector:<7} {f.size_bytes}B"
                self.wm._draw_string(fb, font_dict, cx + 6, cy + 30 + idx * 14, line, 0x00C0CAF5)
        except Exception:
            self.wm._draw_string(fb, font_dict, cx + 6, cy + 30, "(disk.img not formatted)", 0x00F7768E)

    def _draw_paint_content(self, win, fb, font_dict):
        cx, cy, cw, ch = win.client_rect
        # Palette swatches
        colors = [0x00F7768E, 0x009ECE6A, 0x007AA2F7, 0x00E0AF68, 0x00BB9AF7, 0x00FFFFFF]
        for i, c in enumerate(colors):
            c_bytes = bytes([c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF, 0])
            for py in range(cy + 6, cy + 22):
                off = (py * WIDTH + (cx + 8 + i * 24)) * 4
                fb[off : off + 20 * 4] = c_bytes * 20

        # White canvas rectangle
        canvas_bg = bytes([0x1A, 0x1B, 0x26, 0])
        for cy_i in range(cy + 28, cy + ch - 8):
            off = (cy_i * WIDTH + (cx + 8)) * 4
            fb[off : off + (cw - 16) * 4] = canvas_bg * (cw - 16)

    # --------------------------------------------------------------------------
    # Main Compositor & Frame Stepping
    # --------------------------------------------------------------------------

    def step_frame(self, mouse_x, mouse_y):
        self.rot_angle = (self.rot_angle + 2.5) % 360.0

    def render(self, fb):
        # 1. Clear Desktop with deep dark background
        bg_bytes = bytes([0x1A, 0x1B, 0x26, 0])
        fb[0 : WIDTH * HEIGHT * 4] = bg_bytes * (WIDTH * HEIGHT)

        # 2. Render Window Manager Layer
        self.wm.render_all(fb, self.font_dict)

        # 3. Render Top Taskbar (24px high)
        tb_bytes = bytes([COLOR_TASKBAR_BG & 0xFF, (COLOR_TASKBAR_BG >> 8) & 0xFF, (COLOR_TASKBAR_BG >> 16) & 0xFF, 0])
        for ty in range(0, 24):
            fb[(ty * WIDTH) * 4 : (ty * WIDTH + WIDTH) * 4] = tb_bytes * WIDTH

        # Start Pill (AdiOS button)
        pill_bytes = bytes([COLOR_START_PILL & 0xFF, (COLOR_START_PILL >> 8) & 0xFF, (COLOR_START_PILL >> 16) & 0xFF, 0])
        for py in range(3, 21):
            fb[(py * WIDTH + 6) * 4 : (py * WIDTH + 66) * 4] = pill_bytes * 60
        self.wm._draw_string(fb, self.font_dict, 14, 8, "AdiOS", COLOR_START_TXT)

        # Status text in center
        self.wm._draw_string(fb, self.font_dict, 80, 8, self.status_message[:45], 0x00A9B1D6)

        # Right clock / CPU indicator
        self.wm._draw_string(fb, self.font_dict, WIDTH - 120, 8, "64MB | RV32IM", 0x009ECE6A)
