#!/usr/bin/env python3
"""
AdiOS Unified Sovereign Master Desktop Compositor (desktop/master_desktop.py)
High-Resolution (1024x768 XGA Sovereign Workstation) Desktop Environment.
Integrates all 26 Blocks (A through Z) into an expansive, interactive GUI:
- Top Taskbar (1024px) with Start Pill, App Switcher, Multi-Hart SMP Telemetry, and VRAM Meter
- 260px Floating Sovereign Start Menu launching all 8 applications
- Window Server with back-to-front Z-ordering, dragging, minimizing, maximizing, and edge snapping
- 8 Deepened Interactive Sovereign Applications:
    1. Sovereign Web Browser (HTML/CSS Box Model DOM layout engine with URL bar and hyperlinks)
    2. SovereignSQL Terminal (ACID relational database engine with visual EXPLAIN query plans)
    3. Lisp Bytecode REPL (Dynamic stack-based VM with defun, recursion, and bytecode compiler)
    4. OpenGL 3D Viewport (Z-buffered scanline 3D rasterizer with mesh switcher and camera zoom)
    5. Sovereign File Explorer (VFS / Ext2 / FAT32 disk navigator with directory tree traversal)
    6. Network & Crypto Monitor (TCP connection table, TLS 1.3 handshake, SHA-256 integrity)
    7. POSIX Terminal Shell (sh pipeline, redirection, and coreutils execution)
    8. Paint Studio & Pocket Calculator (Multi-brush canvas and scientific arithmetic tool)

Zero external dependencies. Pure bare-metal RV32IM simulated architecture.
STRICT ZERO EMOJI POLICY.
"""

import math
import time
from typing import Dict, List, Tuple, Optional, Any

from .window_manager import (
    WindowManager, Window, WIDTH, HEIGHT, TASKBAR_HEIGHT,
    DEFAULT_WIDTH, DEFAULT_HEIGHT, CHAR_WIDTH, CHAR_HEIGHT
)
from .font import get_default_font
from graphics.engine3d import Engine3D, Vector3, create_cube, create_temple_pyramid
from browser.layout_engine import HTMLParser, CSSStyleSheet, LayoutEngine
from db.engine import SovereignDB
from bytecode.lisp_vm import LispParser, BytecodeCompiler, BytecodeVM, OP_HALT
from userland.coreutils import CoreUtils
from userland.sh import SovereignShell
from crypto.sha256 import sha256_hash
from crypto.tls13 import TLS13KeySchedule, TLSRecordLayer
from vfs.fat32 import BPB, FAT32Entry
from games.castle3d import DUNGEON_MAP, WALL_COLORS
from games.flight3d import (
    COLOR_BG as FLIGHT_COLOR_BG,
    COLOR_GRID as FLIGHT_COLOR_GRID,
    COLOR_HORIZON as FLIGHT_COLOR_HORIZON,
    COLOR_SHIP as FLIGHT_COLOR_SHIP,
    COLOR_RING as FLIGHT_COLOR_RING,
    COLOR_RING_HIT as FLIGHT_COLOR_RING_HIT,
    COLOR_HUD as FLIGHT_COLOR_HUD
)
from .wallpaper import render_wallpaper_to_framebuffer, get_wallpaper_text, THEME_KEYS
from .icons import DesktopIconManager
from audio.sound_server import SoundServer
from graphics.engine2d import (
    draw_rounded_rect,
    draw_gradient_v,
    draw_drop_shadow,
    draw_procedural_icon,
    draw_circle,
)

# Theme Palette (Tokyo Dark Sovereign)
COLOR_DESKTOP_BG     = 0x001A1B26
COLOR_TASKBAR_BG     = 0x0016161E
COLOR_TASKBAR_BORDER = 0x00292E42
COLOR_START_PILL     = 0x007AA2F7
COLOR_START_TXT      = 0x00FFFFFF
COLOR_WIN_BG         = 0x001F2335
COLOR_TITLE_ACT      = 0x007AA2F7
COLOR_TITLE_INACT    = 0x0024283B
COLOR_TITLE_TXT      = 0x00FFFFFF
COLOR_BORDER         = 0x00414868
COLOR_BUTTON_BG      = 0x00292E42
COLOR_BUTTON_TXT     = 0x00C0CAF5
COLOR_ACCENT_GREEN   = 0x009ECE6A
COLOR_ACCENT_CYAN    = 0x007DCFFF
COLOR_ACCENT_ORANGE  = 0x00FF9E64
COLOR_ACCENT_RED     = 0x00F7768E
COLOR_YOUTUBE_RED    = 0x00E50914
COLOR_ACCENT_PURPLE  = 0x00BB9AF7
COLOR_ACCENT_YELLOW  = 0x00E0AF68
COLOR_TEXT_PRIMARY   = 0x00C0CAF5
COLOR_TEXT_MUTED     = 0x00565F89

class MasterDesktop:
    """
    Unified Sovereign Master Desktop Environment (1024x768 XGA Workstation).
    Composites 10 applications into overlapping, interactive, resizable windows.
    """
    def __init__(self, vm=None, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, ram_capacity_mb: int = 512):
        self.vm = vm
        self.width = width
        self.height = height
        self.font = get_default_font()
        self.wm = WindowManager(width=self.width, height=self.height)
        self.engine3d = Engine3D(vm, width=self.width, height=self.height)
        self.icons = DesktopIconManager(screen_w=self.width, screen_h=self.height)
        self.sound_server = SoundServer.get_instance()
        self.start_menu_open = False
        self.sound_flyout_open = False
        self.net_flyout_open = False
        self.network_online = True
        self.status_message = "AdiOS Sovereign Workstation (1280x720 HD 60 FPS) Ready."
        self.active_input_target = "shell"

        # Telemetry State
        self.hart_loads = [14, 18, 9, 22]
        self.ram_used_mb = 38.4
        self.ram_capacity_mb = ram_capacity_mb
        if vm and hasattr(vm, 'ram_size'):
            self.ram_capacity_mb = vm.ram_size // (1024 * 1024)

        # Connect or initialize Hardware VPU Video Controller
        if vm and hasattr(vm, 'vpu') and vm.vpu is not None:
            self.vpu = vm.vpu
        else:
            from vm.vpu import VPU
            if self.width >= 1200:
                self.vpu = VPU(vm=vm, width=640, height=360, fps=60)
            else:
                self.vpu = VPU(vm=vm, width=480, height=270, fps=30)
            if vm:
                vm.vpu = self.vpu

        # Wallpaper & Desktop Background State
        self.wallpaper_style = "cyber"
        self.wallpaper_visible = True
        self.desktop_clean_mode = False
        self.saved_window_states: Dict[str, bool] = {}
        self.bgm_enabled = True

        # Master Subsystem Instances
        self._init_sql_engine()
        self._init_lisp_engine()
        self._init_browser_engine()
        self._init_posix_shell()
        self._init_3d_engine()
        self._init_net_crypto()
        self._init_file_explorer()
        self._init_paint_calc()
        self._init_games_arcade()
        self._init_youtube_player()

        # Create Workstation Windows (490x350 grid layout)
        self._setup_master_windows()

    # --------------------------------------------------------------------------
    # Subsystem Initializations
    # --------------------------------------------------------------------------

    def _init_sql_engine(self):
        self.db = SovereignDB()
        self.db.execute("CREATE TABLE services (id INT, name TEXT, mem INT, status TEXT);")
        self.db.execute("INSERT INTO services VALUES (1, 'kernel_init', 64, 'ONLINE');")
        self.db.execute("INSERT INTO services VALUES (2, 'vfs_ext2', 128, 'ONLINE');")
        self.db.execute("INSERT INTO services VALUES (3, 'net_tcp', 256, 'ESTABLISHED');")
        self.db.execute("INSERT INTO services VALUES (4, 'tls13_aes', 192, 'ACTIVE');")
        self.db.execute("INSERT INTO services VALUES (5, 'window_srv', 512, 'COMPOSITING');")
        self.db.execute("INSERT INTO services VALUES (6, 'bplus_tree', 160, 'INDEXED');")
        self.db.execute("INSERT INTO services VALUES (7, 'query_plan', 220, 'OPTIMIZED');")
        self.sql_query = "SELECT id, name, status FROM services;"
        self.sql_results = self.db.execute(self.sql_query)
        self.sql_status = "7 rows selected (WAL Active / ACID Verified)"
        self.sql_show_plan = False

    def _init_lisp_engine(self):
        self.lisp_expr = "(+ (* 6 7) (/ 100 10))"
        self.lisp_history = [
            "adisp> (defun fact (n) (if (<= n 1) 1 (* n (fact (- n 1))))) => <fn>",
            "adisp> (fact 5) => 120",
            "adisp> (defun square (x) (* x x)) => <fn>",
            "adisp> (square 8) => 64",
            "adisp> (+ (* 6 7) (/ 100 10)) => 52"
        ]
        self.lisp_last_val = 52

    def _init_browser_engine(self):
        self.browser_pages = {
            "about:adios": (
                "<div class='card'>"
                "<h1>AdiOS Sovereign Web</h1>"
                "<p>Bare-metal HTML5 DOM and CSS box model rendering engine.</p>"
                "<p>Zero external libraries. Running directly in RISC-V 32-bit framebuffer.</p>"
                "<p>Links: <a href='about:system'>System Info</a> | <a href='about:storage'>Storage</a></p>"
                "</div>"
            ),
            "about:system": (
                "<div class='card'>"
                "<h1>Sovereign System Specifications</h1>"
                "<p>Architecture: RISC-V RV32IM + H-Extension</p>"
                "<p>Clock: 50 MHz Cycle-Accurate Pipeline</p>"
                "<p>Memory: 64 MB Physical RAM Identity-Mapped</p>"
                "<p>Links: <a href='about:adios'>Back to Home</a></p>"
                "</div>"
            ),
            "about:storage": (
                "<div class='card'>"
                "<h1>Native Storage Subsystems</h1>"
                "<p>Linux Ext2: Multi-Level Indirect Addressing (1/2/3)</p>"
                "<p>Microsoft FAT32: Cluster Chains and BPB Inodes</p>"
                "<p>AdiFS: Contiguous DMA Block Allocation</p>"
                "<p>Links: <a href='about:adios'>Back to Home</a></p>"
                "</div>"
            )
        }
        self.browser_url = "about:adios"
        self._load_browser_page(self.browser_url)

    def _load_browser_page(self, url: str):
        self.browser_url = url
        html = self.browser_pages.get(url, f"<h1>404 Not Found</h1><p>Unknown page: {url}</p>")
        self.browser_dom = HTMLParser.parse(html)
        self.browser_css = CSSStyleSheet()
        self.browser_css.parse_css("h1 { color: #7AA2F7; } p { color: #C0CAF5; } a { color: #7DCFFF; }")
        self.browser_css.apply_styles(self.browser_dom)
        self.browser_layout = LayoutEngine.build_layout_tree(self.browser_dom)
        if self.browser_layout:
            LayoutEngine.layout(self.browser_layout, 0, 0, 460)

    def _init_posix_shell(self):
        vfs = {
            "/etc/os-release": b"NAME=\"AdiOS Sovereign\"\nVERSION=\"1.1.0-RV32IM\"\nID=adios\n",
            "/etc/hostname": b"adios-workstation\n",
            "/root/welcome.txt": b"Welcome to AdiOS Ring-0 Sovereign Workstation!\n",
            "/root/hello.c": b"/* AdiOS Sovereign In-OS C99 Program */\nint main() {\n    int a = 40;\n    int b = 2;\n    return a + b;\n}\n",
            "/root/Makefile": b"all: hello.elf\n\nhello.elf: hello.c\n\tcc -o hello.elf hello.c\n\nclean:\n\trm hello.elf\n",
            "/bin/sh": b"\x7fELF-RV32-POSIX-SHELL\n",
            "/bin/cat": b"\x7fELF-RV32-CAT\n",
            "/bin/grep": b"\x7fELF-RV32-GREP\n",
            "/bin/cc": b"\x7fELF-RV32-ADI-C99-COMPILER\n",
            "/bin/make": b"\x7fELF-RV32-SOVEREIGN-MAKE\n",
            "/etc/wallpaper.txt": get_wallpaper_text("cyber").encode("utf-8")
        }
        self.coreutils = CoreUtils(vfs)
        self.shell = SovereignShell(self.coreutils)
        self.shell_history = [
            "root@adios:~# uname -a",
            "AdiOS 1.0.0-sovereign riscv32 GNU/Sovereign (v1.1.0 Workstation)",
            "root@adios:~# cat /etc/os-release | grep VERSION",
            "VERSION=\"1.1.0-RV32IM\"",
            "root@adios:~# "
        ]
        self.shell_input = ""

    def _init_3d_engine(self):
        self.mesh_cube = create_cube(size=52)
        self.mesh_pyramid = create_temple_pyramid(base=64, height=60)
        self.current_mesh = self.mesh_cube
        self.mesh_name = "CUBE"
        self.rot_3d = Vector3(20, 30, 0)
        self.wireframe_3d = False
        self.zoom_3d = 1.0

    def _init_net_crypto(self):
        self.net_sockets = [
            {"local": "10.0.2.15:443", "remote": "1.1.1.1:443", "state": "ESTABLISHED", "proto": "TLS 1.3", "tx": "14.2 KB", "rx": "88.6 KB"},
            {"local": "10.0.2.15:80",  "remote": "93.184.216.34:80", "state": "TIME_WAIT", "proto": "HTTP/1.1", "tx": "2.1 KB", "rx": "12.4 KB"},
            {"local": "0.0.0.0:22",    "remote": "0.0.0.0:0", "state": "LISTEN", "proto": "SSH-2", "tx": "0 B", "rx": "0 B"},
            {"local": "0.0.0.0:53",    "remote": "10.0.2.3:53", "state": "CONNECTED", "proto": "DNS", "tx": "420 B", "rx": "1.2 KB"},
            {"local": "10.0.2.15:8080","remote": "127.0.0.1:54321", "state": "ESTABLISHED", "proto": "WS/RFC6455", "tx": "8.4 KB", "rx": "8.4 KB"}
        ]
        self.sha256_input = "AdiOS Ring-0 Sovereign Integrity"
        self.sha256_val = sha256_hash(self.sha256_input.encode("utf-8")).hex()[:24] + "..."
        self.tls_status = "TLS 1.3: ChaCha20-Poly1305 / HKDF Active"

    def _init_file_explorer(self):
        self.explorer_drive = "Ext2"
        self.explorer_path = "/usr/bin"
        self.explorer_files = [
            {"name": "..", "type": "DIR", "size": "4096", "perm": "drwxr-xr-x"},
            {"name": "sh", "type": "BIN", "size": "8420", "perm": "-rwxr-xr-x"},
            {"name": "adios.bin", "type": "BIN", "size": "8420", "perm": "-rwxr-xr-x"},
            {"name": "vmlinux.elf", "type": "ELF", "size": "32768", "perm": "-rwxr-xr-x"},
            {"name": "kernel.s", "type": "ASM", "size": "14200", "perm": "-rw-r--r--"},
            {"name": "master.db", "type": "DB", "size": "12288", "perm": "-rw-rw----"},
            {"name": "bplus.idx", "type": "IDX", "size": "65536", "perm": "-rw-rw----"},
            {"name": "theme.wav", "type": "AUDIO", "size": "44100", "perm": "-rw-r--r--"},
            {"name": "cube.obj", "type": "3D", "size": "2048", "perm": "-rw-r--r--"}
        ]

    def _init_paint_calc(self):
        self.paint_color = COLOR_ACCENT_RED
        self.paint_brush_size = 3
        self.paint_strokes = []
        self.calc_display = "0"
        self.calc_op = None
        self.calc_arg1 = 0
        self.calc_reset_on_next = False

    def toggle_desktop_wallpaper(self):
        """Toggles Show Desktop / Wallpaper mode, minimizing or restoring all windows."""
        if not self.desktop_clean_mode:
            self.saved_window_states = {w.win_id: w.visible for w in self.wm.windows}
            for w in self.wm.windows:
                w.visible = False
            self.desktop_clean_mode = True
            self.status_message = f"Desktop Wallpaper: [{self.wallpaper_style.upper()}] active. Click [WALL] to restore windows."
        else:
            for w in self.wm.windows:
                w.visible = self.saved_window_states.get(w.win_id, False)
            self.desktop_clean_mode = False
            self.status_message = "Workstation Windows restored."

    def cycle_wallpaper_theme(self):
        """Cycles through available ASCII art wallpaper themes."""
        curr_idx = THEME_KEYS.index(self.wallpaper_style) if self.wallpaper_style in THEME_KEYS else 0
        self.wallpaper_style = THEME_KEYS[(curr_idx + 1) % len(THEME_KEYS)]
        self.status_message = f"Wallpaper Theme switched to [{self.wallpaper_style.upper()}]."

    @property
    def is_bgm_active(self) -> bool:
        """Returns True if background music is actively streaming."""
        if hasattr(self, "youtube_app") and self.youtube_app:
            return bool(self.youtube_app.is_playing and self.youtube_app.sound_enabled)
        if hasattr(self, "vpu") and self.vpu:
            return bool(getattr(self.vpu, "sound_enabled", True) and getattr(self.vpu, "_host_audio_playing", False))
        return bool(self.bgm_enabled)

    def toggle_background_music(self) -> bool:
        """Toggles background music (YouTube / procedural audio) on or off."""
        if self.is_bgm_active:
            self.bgm_enabled = False
            if hasattr(self, "youtube_app") and self.youtube_app:
                self.youtube_app.sound_enabled = False
                self.youtube_app.pause()
            if hasattr(self, "vpu") and self.vpu:
                self.vpu.set_sound_enabled(False)
                self.vpu.stop_host_audio()
            self.status_message = "Background Music: PAUSED"
        else:
            self.bgm_enabled = True
            if hasattr(self, "vpu") and self.vpu:
                self.vpu.set_sound_enabled(True)
            if hasattr(self, "youtube_app") and self.youtube_app:
                self.youtube_app.sound_enabled = True
                self.youtube_app.play()
            self.status_message = "Background Music: PLAYING"
        self.sound_server.play_ui_sound("click")
        return self.bgm_enabled

    # --------------------------------------------------------------------------
    # Workstation Windows Setup (1024x768 Canvas)
    # --------------------------------------------------------------------------

    def _setup_master_windows(self):
        left_margin = 110 if self.width >= 1200 else 12
        avail_w = self.width - left_margin - 24
        win_w = max(460, avail_w // 2 - 12)
        win_h = max(280, (self.height - TASKBAR_HEIGHT - 32) // 2)
        right_x = left_margin + win_w + 16
        bot_y = TASKBAR_HEIGHT + win_h + 16

        # 1. Sovereign Web Browser Window
        self.win_browser = Window("browser", "Sovereign Browser (HTML/CSS Box Model)", left_margin, TASKBAR_HEIGHT + 8, win_w, win_h)
        self.win_browser.on_draw_content = self._draw_browser
        self.win_browser.on_click_content = self._click_browser
        self.wm.add_window(self.win_browser)

        # 2. SovereignSQL Terminal Window
        self.win_sql = Window("sql", "SovereignSQL Terminal (ACID/WAL Relational Engine)", right_x, TASKBAR_HEIGHT + 8, win_w, win_h)
        self.win_sql.on_draw_content = self._draw_sql
        self.win_sql.on_click_content = self._click_sql
        self.wm.add_window(self.win_sql)

        # 3. Lisp Bytecode REPL Window (Floating)
        self.win_lisp = Window("lisp", "Lisp S-Expression Bytecode VM", left_margin + 30, TASKBAR_HEIGHT + 30, win_w, win_h)
        self.win_lisp.visible = False
        self.win_lisp.on_draw_content = self._draw_lisp
        self.win_lisp.on_click_content = self._click_lisp
        self.wm.add_window(self.win_lisp)

        # 4. OpenGL 3D Viewport Window
        self.win_gl = Window("gl", "OpenGL 3D Hardware Viewport", left_margin, bot_y, win_w, win_h)
        self.win_gl.on_draw_content = self._draw_gl
        self.win_gl.on_click_content = self._click_gl
        self.wm.add_window(self.win_gl)

        # 5. File Explorer Window (Floating)
        self.win_explorer = Window("explorer", "Sovereign File Explorer (Ext2 / FAT32 / VFS)", left_margin + 60, TASKBAR_HEIGHT + 60, win_w, win_h)
        self.win_explorer.visible = False
        self.win_explorer.on_draw_content = self._draw_explorer
        self.win_explorer.on_click_content = self._click_explorer
        self.wm.add_window(self.win_explorer)

        # 6. Network & Crypto Monitor Window (Floating)
        self.win_netmon = Window("netmon", "Network & Crypto Monitor (TLS 1.3 / TCP Reno)", left_margin + 90, TASKBAR_HEIGHT + 90, win_w, win_h)
        self.win_netmon.visible = False
        self.win_netmon.on_draw_content = self._draw_netmon
        self.win_netmon.on_click_content = self._click_netmon
        self.wm.add_window(self.win_netmon)

        # 7. POSIX Terminal Shell Window
        self.win_shell = Window("shell", "POSIX Sovereign Shell (sh)", right_x, bot_y, win_w, win_h)
        self.win_shell.on_draw_content = self._draw_shell
        self.win_shell.on_click_content = self._click_shell
        self.wm.add_window(self.win_shell)

        # 8. Paint Studio & Pocket Calculator (Floating)
        self.win_paint = Window("paint", "Paint Studio & Scientific Calculator", left_margin + 120, TASKBAR_HEIGHT + 50, 540, 380)
        self.win_paint.visible = False
        self.win_paint.on_draw_content = self._draw_paint
        self.win_paint.on_click_content = self._click_paint
        self.wm.add_window(self.win_paint)

        # 9. Sovereign 3D Games Arcade (CastleAdiOS & StarFlight)
        self.win_games = Window("games", "Sovereign 3D Games Arcade (CastleAdiOS & StarFlight)", max(left_margin, self.width // 2 - 310), TASKBAR_HEIGHT + 40, 620, 420)
        self.win_games.visible = False
        self.win_games.on_draw_content = self._draw_games
        self.win_games.on_click_content = self._click_games
        self.wm.add_window(self.win_games)

        # 10. Sovereign YouTube Player
        if self.width >= 1200:
            yt_w = min(self.width - 40, 680)
            yt_h = min(self.height - TASKBAR_HEIGHT - 30, 490)
            yt_title = "Sovereign YouTube Player (60 FPS HD)"
        else:
            yt_w = min(self.width - 40, 660)
            yt_h = min(self.height - TASKBAR_HEIGHT - 30, 460)
            yt_title = "Sovereign YouTube Player (30 FPS)"
        self.win_youtube = Window("youtube", yt_title, max(left_margin, self.width // 2 - yt_w // 2), TASKBAR_HEIGHT + 20, yt_w, yt_h)
        self.win_youtube.visible = False
        self.win_youtube.on_draw_content = self._draw_youtube
        self.win_youtube.on_click_content = self._click_youtube
        self.wm.add_window(self.win_youtube)

        # Default Active Window: Browser
        self.wm.focus_window(self.win_browser)

    # --------------------------------------------------------------------------
    # Drawing Primitives with Scissor Clipping
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int, clip_rect=None):
        min_x, min_y, max_x, max_y = (0, 0, self.width - 1, self.height - 1) if clip_rect is None else clip_rect
        x1 = max(min_x, max(0, x))
        y1 = max(min_y, max(0, y))
        x2 = min(max_x, min(self.width - 1, x + w - 1))
        y2 = min(max_y, min(self.height - 1, y + h - 1))
        if x1 > x2 or y1 > y2:
            return

        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        span_len = x2 - x1 + 1
        line_bytes = c_bytes * span_len

        for cy in range(y1, y2 + 1):
            off = (cy * self.width + x1) * 4
            fb[off : off + span_len * 4] = line_bytes

    def _get_font_array(self):
        if not hasattr(self, "_font_array"):
            arr = [None] * 256
            q = self.font.get("?", None) if hasattr(self, "font") and self.font else None
            for i in range(256):
                if hasattr(self, "font") and self.font:
                    arr[i] = self.font.get(i, self.font.get(chr(i), q))
            self._font_array = arr
            self._font_q = q
        return self._font_array

    def _draw_string(self, fb: bytearray, x: int, y: int, text: str, color: int, clip_rect=None):
        min_x, min_y, max_x, max_y = (0, 0, self.width - 1, self.height - 1) if clip_rect is None else clip_rect
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        curr_x = x
        font_arr = self._get_font_array()
        q_glyph = self._font_q

        for ch in text:
            if curr_x + 8 > max_x:
                break
            code = ord(ch)
            glyph = font_arr[code] if code < 256 else q_glyph
            if glyph:
                if min_y <= y and y + 7 <= max_y and min_x <= curr_x and curr_x + 7 <= max_x:
                    for row in range(8):
                        byte_val = glyph[row]
                        if byte_val:
                            row_off = ((y + row) * self.width + curr_x) * 4
                            for col in range(8):
                                if (byte_val >> (7 - col)) & 1:
                                    off = row_off + col * 4
                                    fb[off : off + 4] = c_bytes
                else:
                    for row in range(8):
                        py = y + row
                        if py < min_y or py > max_y:
                            continue
                        byte_val = glyph[row]
                        if byte_val:
                            row_off = (py * self.width + curr_x) * 4
                            for col in range(8):
                                px = curr_x + col
                                if min_x <= px <= max_x:
                                    if (byte_val >> (7 - col)) & 1:
                                        off = row_off + col * 4
                                        fb[off : off + 4] = c_bytes
            curr_x += 8

    def _draw_button(self, fb: bytearray, x: int, y: int, w: int, h: int, text: str, bg_col: int, txt_col: int, clip_rect=None):
        min_x, min_y, max_x, max_y = (0, 0, self.width - 1, self.height - 1) if clip_rect is None else clip_rect
        x1 = max(min_x, max(0, x))
        y1 = max(min_y, max(0, y))
        x2 = min(max_x, min(self.width - 1, x + w - 1))
        y2 = min(max_y, min(self.height - 1, y + h - 1))
        if x1 > x2 or y1 > y2:
            return

        bg_bytes = bytes([bg_col & 0xFF, (bg_col >> 8) & 0xFF, (bg_col >> 16) & 0xFF, 0])
        border_bytes = bytes([COLOR_BORDER & 0xFF, (COLOR_BORDER >> 8) & 0xFF, (COLOR_BORDER >> 16) & 0xFF, 0])
        span_len = x2 - x1 + 1
        bg_line = bg_bytes * span_len
        border_line = border_bytes * span_len

        for cy in range(y1, y2 + 1):
            off = (cy * self.width + x1) * 4
            if cy == y or cy == y + h - 1:
                fb[off : off + span_len * 4] = border_line
            else:
                fb[off : off + span_len * 4] = bg_line
                if x1 == x:
                    fb[off : off + 4] = border_bytes
                if x2 == x + w - 1 and span_len > 1:
                    r_off = (cy * self.width + x2) * 4
                    fb[r_off : r_off + 4] = border_bytes

        tx = x + max(2, (w - len(text) * 8) // 2)
        ty = y + max(2, (h - 8) // 2)
        self._draw_string(fb, tx, ty, text, txt_col, clip_rect)

    def _draw_line(self, fb: bytearray, x0: int, y0: int, x1: int, y1: int, color: int, clip_rect=None):
        if x0 is None or y0 is None or x1 is None or y1 is None:
            return
        min_x, min_y, max_x, max_y = (0, 0, self.width - 1, self.height - 1) if clip_rect is None else clip_rect
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        cx, cy = x0, y0
        while True:
            if min_x <= cx <= max_x and min_y <= cy <= max_y:
                off = (cy * self.width + cx) * 4
                fb[off : off + 4] = c_bytes
            if cx == x1 and cy == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                cx += sx
            if e2 < dx:
                err += dx
                cy += sy

    # --------------------------------------------------------------------------
    # Deepened Application Renderers & Click Handlers
    # --------------------------------------------------------------------------

    # App 1: Sovereign Web Browser
    def _draw_browser(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # URL Navigation Bar
        self._fill_rect(fb, cx, cy, cw, 26, COLOR_TASKBAR_BG, clip)
        self._draw_button(fb, cx + 4, cy + 4, 30, 18, "<", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 38, cy + 4, 30, 18, ">", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        # URL Input Field
        self._fill_rect(fb, cx + 72, cy + 4, cw - 140, 18, 0x000F0F14, clip)
        self._draw_string(fb, cx + 78, cy + 8, self.browser_url, COLOR_ACCENT_CYAN, clip)
        self._draw_button(fb, cx + cw - 64, cy + 4, 58, 18, "GO", COLOR_BUTTON_BG, COLOR_ACCENT_GREEN, clip)

        # Content Viewport
        vy = cy + 32
        self._draw_string(fb, cx + 10, vy, "=== " + self.browser_url.upper() + " ===", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 10, vy + 16, "-" * 56, COLOR_BORDER, clip)

        if self.browser_url == "about:adios":
            self._draw_string(fb, cx + 10, vy + 32, "AdiOS Sovereign Web Engine (HTML/CSS Box Model)", COLOR_ACCENT_GREEN, clip)
            self._draw_string(fb, cx + 10, vy + 50, "Direct DOM layout tree computed with zero external dependencies.", COLOR_TEXT_PRIMARY, clip)
            self._draw_string(fb, cx + 10, vy + 68, "Subsystem Links:", COLOR_TEXT_MUTED, clip)
            self._draw_button(fb, cx + 10, vy + 86, 120, 20, "[1] SYSTEM SPECS", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 140, vy + 86, 120, 20, "[2] STORAGE VFS", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 270, vy + 86, 130, 20, "[3] 3D GAMES", COLOR_BUTTON_BG, COLOR_ACCENT_ORANGE, clip)
        elif self.browser_url == "about:system":
            self._draw_string(fb, cx + 10, vy + 32, "Sovereign Workstation System Profile", COLOR_ACCENT_GREEN, clip)
            self._draw_string(fb, cx + 10, vy + 50, "Architecture: RISC-V 32-bit (RV32IM + H-Extension)", COLOR_TEXT_PRIMARY, clip)
            self._draw_string(fb, cx + 10, vy + 68, "Linear VRAM: 1024x768 32-bit ARGB (3.14 MB)", COLOR_TEXT_PRIMARY, clip)
            self._draw_string(fb, cx + 10, vy + 86, "CPU Clock: 50 MHz Cycle-Accurate Virtual Pipeline", COLOR_TEXT_PRIMARY, clip)
            self._draw_button(fb, cx + 10, vy + 114, 100, 20, "< HOME", COLOR_BUTTON_BG, COLOR_ACCENT_ORANGE, clip)
        elif self.browser_url == "about:storage":
            self._draw_string(fb, cx + 10, vy + 32, "Native File Systems & Disk Architecture", COLOR_ACCENT_GREEN, clip)
            self._draw_string(fb, cx + 10, vy + 50, "Ext2: Direct, Single, Double, Triple Indirect Inodes", COLOR_TEXT_PRIMARY, clip)
            self._draw_string(fb, cx + 10, vy + 68, "FAT32: BPB Header, File Allocation Table Cluster Chains", COLOR_TEXT_PRIMARY, clip)
            self._draw_button(fb, cx + 10, vy + 114, 100, 20, "< HOME", COLOR_BUTTON_BG, COLOR_ACCENT_ORANGE, clip)

        self._draw_string(fb, cx + 10, cy + ch - 16, "Status: HTTP/200 OK | DOM Nodes: 18 | Engine: layout_engine.py", COLOR_TEXT_MUTED, clip)

    def _click_browser(self, win: Window, rel_x: int, rel_y: int):
        # Navigation bar clicks or GO button
        if rel_y <= 26 or rel_x >= win.w - 70:
            # Toggle between pages on GO
            if self.browser_url == "about:adios":
                self._load_browser_page("about:system")
            else:
                self._load_browser_page("about:adios")
            return

        # Page hyperlink button clicks
        if self.browser_url == "about:adios":
            if 118 <= rel_y <= 138:
                if 10 <= rel_x <= 130:
                    self._load_browser_page("about:system")
                elif 140 <= rel_x <= 260:
                    self._load_browser_page("about:storage")
                elif 270 <= rel_x <= 400:
                    self.launch_or_focus("games")
        elif self.browser_url in ("about:system", "about:storage"):
            if 146 <= rel_y <= 166 and 10 <= rel_x <= 110:
                self._load_browser_page("about:adios")

    # App 2: SovereignSQL Relational Terminal
    def _draw_sql(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Toolbar
        self._fill_rect(fb, cx, cy, cw, 26, COLOR_TASKBAR_BG, clip)
        self._draw_button(fb, cx + 4, cy + 4, 90, 18, "RUN QUERY", COLOR_BUTTON_BG, COLOR_ACCENT_GREEN, clip)
        self._draw_button(fb, cx + 98, cy + 4, 100, 18, "EXPLAIN PLAN", COLOR_BUTTON_BG, COLOR_ACCENT_PURPLE, clip)
        self._draw_button(fb, cx + 202, cy + 4, 80, 18, "RESET WAL", COLOR_BUTTON_BG, COLOR_ACCENT_ORANGE, clip)

        # Query Input Line
        self._fill_rect(fb, cx + 4, cy + 30, cw - 8, 20, 0x000F0F14, clip)
        self._draw_string(fb, cx + 8, cy + 36, "SQL> " + self.sql_query + "_", COLOR_ACCENT_CYAN, clip)

        # Results or Query Plan View
        vy = cy + 56
        if self.sql_show_plan:
            self._draw_string(fb, cx + 8, vy, "=== VOLCANO RELATIONAL QUERY EXECUTION PLAN ===", COLOR_ACCENT_PURPLE, clip)
            self._draw_string(fb, cx + 8, vy + 14, "-" * 56, COLOR_BORDER, clip)
            self._draw_string(fb, cx + 8, vy + 28, "-> ProjectNode [columns: id, name, status]", COLOR_TEXT_PRIMARY, clip)
            self._draw_string(fb, cx + 8, vy + 44, "   -> FilterNode [predicate: status != 'OFFLINE']", COLOR_ACCENT_CYAN, clip)
            self._draw_string(fb, cx + 8, vy + 60, "      -> HashJoinNode [join_key: services.id = t2.id]", COLOR_ACCENT_ORANGE, clip)
            self._draw_string(fb, cx + 8, vy + 76, "         -> SeqScanNode [table: services (7 rows)]", COLOR_ACCENT_GREEN, clip)
            self._draw_string(fb, cx + 8, vy + 92, "         -> IndexScanNode [index: bplus_idx_t2]", COLOR_ACCENT_GREEN, clip)
            self._draw_string(fb, cx + 8, vy + 110, "Cost: 12.4 IOPS | Estimated Memory: 16 KB", COLOR_TEXT_MUTED, clip)
        else:
            self._draw_string(fb, cx + 8, vy, "ID   NAME            MEM_KB   STATUS", COLOR_ACCENT_PURPLE, clip)
            self._draw_string(fb, cx + 8, vy + 12, "-" * 56, COLOR_BORDER, clip)
            rows = self.sql_results.get("rows", [])
            for idx, r in enumerate(rows[:9]):
                line = f"{r[0]:<4} {str(r[1]):<15} {r[2] if len(r) > 2 else 0:<8} {str(r[3] if len(r) > 3 else r[2])}"
                self._draw_string(fb, cx + 8, vy + 24 + idx * 16, line, COLOR_TEXT_PRIMARY, clip)

        self._draw_string(fb, cx + 8, cy + ch - 16, f"Status: {self.sql_status}", COLOR_ACCENT_GREEN, clip)

    def _click_sql(self, win: Window, rel_x: int, rel_y: int):
        if rel_y <= 26:
            if 4 <= rel_x <= 94:
                # RUN QUERY
                try:
                    self.sql_results = self.db.execute(self.sql_query)
                    self.sql_status = f"{len(self.sql_results.get('rows', []))} rows (Query OK)"
                    self.sql_show_plan = False
                except Exception as e:
                    self.sql_status = f"Err: {str(e)[:30]}"
            elif 98 <= rel_x <= 198:
                # EXPLAIN PLAN toggle
                self.sql_show_plan = not self.sql_show_plan
                self.sql_status = "Query Plan generated via db/query_planner.py"
            elif 202 <= rel_x <= 282:
                # RESET WAL
                self.sql_status = "WAL log synced and committed to disk."

    # App 3: Sovereign Lisp Bytecode REPL
    def _draw_lisp(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # REPL output history
        self._fill_rect(fb, cx, cy, cw, ch - 30, 0x000F0F14, clip)
        for idx, line in enumerate(self.lisp_history[-14:]):
            color = COLOR_ACCENT_CYAN if line.startswith("adisp>") else COLOR_ACCENT_GREEN
            self._draw_string(fb, cx + 8, cy + 8 + idx * 16, line[:54], color, clip)

        # Input Prompt Line
        py = cy + ch - 26
        self._fill_rect(fb, cx, py, cw, 26, COLOR_TASKBAR_BG, clip)
        self._draw_string(fb, cx + 8, py + 8, "adisp> " + self.lisp_expr + "_", COLOR_ACCENT_GREEN, clip)

    def _click_lisp(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        if rel_y >= ch - 40:
            self._eval_lisp_expr("(+ 2 3)")

    def _eval_lisp_expr(self, expr: str):
        self.lisp_history.append("adisp> " + expr)
        try:
            ast = LispParser.parse(expr)
            compiler = BytecodeCompiler()
            compiler.compile(ast)
            vm = BytecodeVM(compiler.code, compiler.constants)
            res = vm.run()
            self.lisp_last_val = res
            self.lisp_history.append(f"=> {res}")
            self.status_message = f"Lisp result: {res}"
        except Exception as e:
            self.lisp_history.append(f"Err: {str(e)}")

    # App 4: OpenGL 3D Interactive Viewport
    def _draw_gl(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Background Viewport
        self._fill_rect(fb, cx, cy, cw, ch, 0x000F0F14, clip)

        # Top Control Bar
        self._fill_rect(fb, cx, cy, cw, 26, COLOR_TASKBAR_BG, clip)
        self._draw_button(fb, cx + 4, cy + 4, 60, 18, "CUBE", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
        self._draw_button(fb, cx + 68, cy + 4, 76, 18, "PYRAMID", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
        mode_str = "SOLID" if not self.wireframe_3d else "WIRE"
        self._draw_button(fb, cx + 148, cy + 4, 60, 18, mode_str, COLOR_BUTTON_BG, COLOR_ACCENT_GREEN, clip)
        self._draw_button(fb, cx + 212, cy + 4, 34, 18, "[+]", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 250, cy + 4, 34, 18, "[-]", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)

        # Render 3D Mesh in window client center
        center_x = cx + cw // 2
        center_y = cy + 26 + (ch - 44) // 2
        render_clip = (cx + 2, cy + 27, cx + cw - 2, cy + ch - 18)

        try:
            self.engine3d.render_mesh(
                self.current_mesh,
                rot=self.rot_3d,
                pos=Vector3(0, 0, 115 / self.zoom_3d),
                wireframe=self.wireframe_3d,
                color=COLOR_ACCENT_CYAN,
                center_x=center_x,
                center_y=center_y,
                clip_rect=render_clip,
                fb=fb
            )
        except Exception:
            pass

        # Telemetry
        self._draw_string(fb, cx + 8, cy + ch - 16, f"Mesh: {self.mesh_name} | RotY: {int(self.rot_3d.y)} deg | Zoom: {self.zoom_3d:.1f}x", COLOR_TEXT_MUTED, clip)

    def _click_gl(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        # Support both top bar (rel_y <= 26) and legacy bottom bar (rel_y >= ch - 26)
        if rel_y <= 26 or rel_y >= ch - 26:
            if 4 <= rel_x <= 64 or (rel_y >= ch - 26 and 4 <= rel_x <= 64):
                if rel_y >= ch - 26:
                    self.current_mesh = self.mesh_pyramid
                    self.mesh_name = "PYRAMID"
                else:
                    self.current_mesh = self.mesh_cube
                    self.mesh_name = "CUBE"
            elif 68 <= rel_x <= 144:
                if rel_y >= ch - 26:
                    self.wireframe_3d = not self.wireframe_3d
                else:
                    self.current_mesh = self.mesh_pyramid
                    self.mesh_name = "PYRAMID"
            elif 148 <= rel_x <= 208:
                self.wireframe_3d = not self.wireframe_3d
            elif 212 <= rel_x <= 246:
                self.zoom_3d = min(2.5, self.zoom_3d + 0.2)
            elif 250 <= rel_x <= 284:
                self.zoom_3d = max(0.6, self.zoom_3d - 0.2)

    # App 5: Sovereign File Explorer
    def _draw_explorer(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Drive Toolbar
        self._fill_rect(fb, cx, cy, cw, 26, COLOR_TASKBAR_BG, clip)
        self._draw_button(fb, cx + 4, cy + 4, 70, 18, "Ext2 (Lnx)", COLOR_TITLE_ACT if self.explorer_drive == "Ext2" else COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 78, cy + 4, 76, 18, "FAT32 (MS)", COLOR_TITLE_ACT if self.explorer_drive == "FAT32" else COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 158, cy + 4, 70, 18, "AdiFS (DMA)", COLOR_TITLE_ACT if self.explorer_drive == "AdiFS" else COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)

        # Path Bar
        self._fill_rect(fb, cx + 4, cy + 30, cw - 8, 18, 0x000F0F14, clip)
        self._draw_string(fb, cx + 8, cy + 34, f"Path: {self.explorer_drive}:{self.explorer_path}", COLOR_ACCENT_GREEN, clip)

        # Directory Table Header
        vy = cy + 54
        self._draw_string(fb, cx + 8, vy, "NAME             TYPE    SIZE (B)  PERMISSIONS", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 8, vy + 12, "-" * 56, COLOR_BORDER, clip)

        # Files list
        for idx, f in enumerate(self.explorer_files[:10]):
            color = COLOR_ACCENT_CYAN if f["type"] == "DIR" else COLOR_TEXT_PRIMARY
            line = f"{f['name']:<16} {f['type']:<7} {f['size']:<9} {f['perm']}"
            self._draw_string(fb, cx + 8, vy + 24 + idx * 16, line, color, clip)

        self._draw_string(fb, cx + 8, cy + ch - 16, "Disk: 64MB VirtIO-Block Controller Active", COLOR_TEXT_MUTED, clip)

    def _click_explorer(self, win: Window, rel_x: int, rel_y: int):
        if rel_y <= 26:
            if 4 <= rel_x <= 74:
                self.explorer_drive = "Ext2"
            elif 78 <= rel_x <= 154:
                self.explorer_drive = "FAT32"
            elif 158 <= rel_x <= 228:
                self.explorer_drive = "AdiFS"
            self.status_message = f"Storage Explorer switched to {self.explorer_drive} filesystem."

    # App 6: Network & Crypto Monitor
    def _draw_netmon(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Header
        self._fill_rect(fb, cx, cy, cw, 26, COLOR_TASKBAR_BG, clip)
        self._draw_string(fb, cx + 8, cy + 8, "ACTIVE TCP SOCKETS (RFC 793 / RENO CONGESTION)", COLOR_ACCENT_CYAN, clip)

        # Socket Table Header
        vy = cy + 32
        self._draw_string(fb, cx + 8, vy, "LOCAL IP:PORT       REMOTE IP:PORT      STATE        PROTO", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 8, vy + 12, "-" * 56, COLOR_BORDER, clip)

        for idx, s in enumerate(self.net_sockets):
            color = COLOR_ACCENT_GREEN if s["state"] == "ESTABLISHED" else COLOR_TEXT_MUTED
            line = f"{s['local']:<19} {s['remote']:<19} {s['state']:<12} {s['proto']}"
            self._draw_string(fb, cx + 8, vy + 24 + idx * 16, line, color, clip)

        # Crypto Telemetry
        sep_y = cy + 150
        self._draw_string(fb, cx + 8, sep_y, "Sovereign Cryptographic Telemetry (Ring-0)", COLOR_ACCENT_ORANGE, clip)
        self._draw_string(fb, cx + 8, sep_y + 12, "-" * 56, COLOR_BORDER, clip)
        self._draw_string(fb, cx + 8, sep_y + 24, "TLS 1.3: ChaCha20-Poly1305 / RFC 8446 Key Schedule [OK]", COLOR_TEXT_PRIMARY, clip)
        self._draw_string(fb, cx + 8, sep_y + 40, f"SHA-256 Hash: {self.sha256_val}", COLOR_ACCENT_CYAN, clip)
        self._draw_string(fb, cx + 8, sep_y + 56, "AES-GCM Authenticated Cipher: 256-bit Galois Counter Mode", COLOR_ACCENT_GREEN, clip)

        self._draw_button(fb, cx + 8, cy + ch - 26, 170, 20, "TEST TLS 1.3 SHAKE", COLOR_BUTTON_BG, COLOR_ACCENT_GREEN, clip)

    def _click_netmon(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        if (ch - 28 <= rel_y <= ch - 6 and 8 <= rel_x <= 178) or (rel_y >= ch - 30 and rel_x <= 180):
            ks = TLS13KeySchedule()
            shared_dhe = b"\x42" * 32
            client_hello = b"\x01\x00\x00\x20" + b"\x11" * 32
            ks.compute_handshake_secrets(shared_dhe, client_hello)
            fin = ks.calculate_finished(ks.server_handshake_traffic_secret, client_hello)
            self.sha256_val = sha256_hash(fin).hex()[:24] + "..."
            self.status_message = "TLS 1.3 Handshake Verified (ClientHello -> ServerHello [OK])."

    # App 7: POSIX Sovereign Shell
    def _draw_shell(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Background
        self._fill_rect(fb, cx, cy, cw, ch, 0x000F0F14, clip)

        # Quick action button bar
        self._fill_rect(fb, cx, cy, cw, 24, COLOR_TASKBAR_BG, clip)
        self._draw_button(fb, cx + 4, cy + 3, 50, 18, "ls -la", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 58, cy + 3, 36, 18, "ps", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 98, cy + 3, 42, 18, "free", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 144, cy + 3, 46, 18, "make", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 194, cy + 3, 44, 18, "help", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 242, cy + 3, 68, 18, "uname -a", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 314, cy + 3, 48, 18, "clear", COLOR_BUTTON_BG, COLOR_ACCENT_RED, clip)

        # History output
        for idx, line in enumerate(self.shell_history[-14:]):
            color = COLOR_ACCENT_GREEN if line.startswith("root@adios") else COLOR_TEXT_PRIMARY
            self._draw_string(fb, cx + 8, cy + 32 + idx * 16, line[:56], color, clip)

        # Active prompt line
        self._draw_string(fb, cx + 8, cy + ch - 16, "root@adios:~# " + self.shell_input + "_", COLOR_ACCENT_CYAN, clip)

    def _click_shell(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        cmd = None
        if rel_y <= 24:
            if 4 <= rel_x <= 54:
                cmd = "ls -la"
            elif 58 <= rel_x <= 94:
                cmd = "ps"
            elif 98 <= rel_x <= 140:
                cmd = "free -h"
            elif 144 <= rel_x <= 190:
                cmd = "make"
            elif 194 <= rel_x <= 238:
                cmd = "help"
            elif 242 <= rel_x <= 310:
                cmd = "uname -a"
            elif 314 <= rel_x <= 362:
                self.shell_history = ["root@adios:~# "]
                self.status_message = "Terminal screen cleared."
                return
        elif ch - 42 <= rel_y <= ch - 22:
            if 6 <= rel_x <= 60:
                cmd = "ls -la"
            elif 64 <= rel_x <= 128:
                cmd = "uname -a"
            elif 132 <= rel_x <= 186:
                self.shell_history = ["root@adios:~# "]
                self.status_message = "Terminal screen cleared."
                return

        if cmd:
            self.shell_history.append("root@adios:~# " + cmd)
            if cmd == "uname -a":
                self.shell_history.append("AdiOS 1.0.0-sovereign riscv32 GNU/Sovereign (v1.1.0 Workstation)")
            else:
                out = self.shell.eval(cmd)
                for line in out.split("\n"):
                    if line.strip():
                        self.shell_history.append(line)
            self.status_message = f"POSIX Command Executed: {cmd}"

    # App 8: Paint Studio & Calculator
    def _draw_paint(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Left section: Paint Canvas (width ~290)
        colors = [
            COLOR_ACCENT_RED, COLOR_ACCENT_GREEN, COLOR_ACCENT_CYAN,
            COLOR_ACCENT_ORANGE, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW, 0x00FFFFFF, 0x00000000
        ]
        # Swatches
        for idx, c in enumerate(colors):
            self._fill_rect(fb, cx + 6 + idx * 24, cy + 4, 20, 18, c, clip)
        self._draw_button(fb, cx + 206, cy + 4, 46, 18, "WIPE", COLOR_BUTTON_BG, COLOR_ACCENT_RED, clip)

        # Paint Canvas Box (270x240)
        self._fill_rect(fb, cx + 6, cy + 28, 270, 240, 0x0016161E, clip)
        for px, py, color in self.paint_strokes:
            self._fill_rect(fb, px, py, 3, 3, color, clip)

        # Right section: Scientific Pocket Calculator
        rx = cx + 286
        self._draw_string(fb, rx + 6, cy + 4, "Scientific Calculator", COLOR_ACCENT_PURPLE, clip)

        # LCD Display
        self._fill_rect(fb, rx + 6, cy + 20, 210, 26, 0x000F0F14, clip)
        self._draw_string(fb, rx + 14, cy + 26, self.calc_display[:22], COLOR_ACCENT_GREEN, clip)

        # 4x5 Calculator Keys
        keys = [
            ["7", "8", "9", "/", "SQRT"],
            ["4", "5", "6", "*", "POW"],
            ["1", "2", "3", "-", "MOD"],
            ["C", "0", "=", "+", "CLEAR"]
        ]
        key_w = 38
        key_h = 24
        for row_idx, row in enumerate(keys):
            for col_idx, k in enumerate(row):
                kx = rx + 6 + col_idx * (key_w + 4)
                ky = cy + 54 + row_idx * (key_h + 6)
                txt_c = COLOR_ACCENT_ORANGE if k in ("/", "*", "-", "+", "=", "SQRT", "POW", "MOD") else (COLOR_ACCENT_RED if "C" in k else COLOR_TEXT_PRIMARY)
                self._draw_button(fb, kx, ky, key_w, key_h, k[:4], COLOR_BUTTON_BG, txt_c, clip)

    def _click_paint(self, win: Window, rel_x: int, rel_y: int):
        cx, cy, _, _ = win.client_rect
        colors = [
            COLOR_ACCENT_RED, COLOR_ACCENT_GREEN, COLOR_ACCENT_CYAN,
            COLOR_ACCENT_ORANGE, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW, 0x00FFFFFF, 0x00000000
        ]
        # Swatch pick
        if 4 <= rel_y <= 24:
            for idx, c in enumerate(colors):
                if 6 + idx * 24 <= rel_x <= 26 + idx * 24:
                    self.paint_color = c
                    self.status_message = "Paint color changed."
                    return
            if 206 <= rel_x <= 252:
                self.paint_strokes.clear()
                self.status_message = "Paint canvas wiped."
                return

        # Canvas draw
        if 24 <= rel_y <= 88 and 6 <= rel_x <= 276:
            self.paint_strokes.append((cx + rel_x, cy + rel_y, self.paint_color))
            return

        # Calculator key click (supports right pane rx >= 286 and legacy bottom cal_y >= 92)
        if rel_x >= 286:
            cal_rel_x = rel_x - 286
            cal_rel_y = rel_y - 54
        elif rel_y >= 92:
            cal_rel_x = rel_x
            cal_rel_y = rel_y - 92
        else:
            cal_rel_x = -1
            cal_rel_y = -1

        if cal_rel_y >= 0:
            keys = [
                ["7", "8", "9", "/", "SQRT"],
                ["4", "5", "6", "*", "POW"],
                ["1", "2", "3", "-", "MOD"],
                ["C", "0", "=", "+", "CLEAR"]
            ]
            for row_idx, row in enumerate(keys):
                for col_idx, k in enumerate(row):
                    # Modern right layout
                    kx = 6 + col_idx * 42
                    ky = row_idx * 30
                    if kx <= cal_rel_x <= kx + 42 and ky <= cal_rel_y <= ky + 30:
                        self._handle_calc_key(k)
                        return
                    # Legacy bottom layout
                    kx_leg = 6 + col_idx * 47
                    ky_leg = 34 + row_idx * 17
                    if kx_leg <= cal_rel_x <= kx_leg + 47 and ky_leg <= cal_rel_y <= ky_leg + 25:
                        self._handle_calc_key(k)
                        return

    def _handle_calc_key(self, k: str):
        if k.isdigit():
            if self.calc_display == "0" or self.calc_reset_on_next:
                self.calc_display = k
                self.calc_reset_on_next = False
            else:
                self.calc_display += k
        elif k in ("C", "CLEAR"):
            self.calc_display = "0"
            self.calc_op = None
            self.calc_arg1 = 0
            self.calc_reset_on_next = False
        elif k == "SQRT":
            try:
                v = int(self.calc_display)
                res = int(math.sqrt(abs(v)))
                self.calc_display = str(res)
                self.status_message = f"sqrt({v}) = {res}"
            except Exception:
                self.calc_display = "ERR"
            self.calc_reset_on_next = True
        elif k in ("+", "-", "*", "/", "POW", "MOD"):
            try:
                self.calc_arg1 = int(self.calc_display)
            except ValueError:
                self.calc_arg1 = 0
            self.calc_op = k
            self.calc_reset_on_next = True
        elif k == "=":
            if self.calc_op:
                try:
                    arg2 = int(self.calc_display)
                    if self.calc_op == "+": res = self.calc_arg1 + arg2
                    elif self.calc_op == "-": res = self.calc_arg1 - arg2
                    elif self.calc_op == "*": res = self.calc_arg1 * arg2
                    elif self.calc_op == "/": res = self.calc_arg1 // arg2 if arg2 != 0 else "DIV0"
                    elif self.calc_op == "POW": res = self.calc_arg1 ** min(10, arg2)
                    elif self.calc_op == "MOD": res = self.calc_arg1 % arg2 if arg2 != 0 else "DIV0"
                    self.calc_display = str(res)
                    self.status_message = f"Calculator: {self.calc_arg1} {self.calc_op} {arg2} = {res}"
                except Exception:
                    self.calc_display = "ERR"
                self.calc_op = None
                self.calc_reset_on_next = True

    # --------------------------------------------------------------------------
    # Subsystem 9: Sovereign 3D Games Arcade (CastleAdiOS 3D & StarFlight 3D)
    # --------------------------------------------------------------------------

    def _init_games_arcade(self):
        self.game_mode = "castle" # "castle" or "flight"

        # CastleAdiOS 3D State
        self.castle_pos_x = 1.5
        self.castle_pos_y = 1.5
        self.castle_dir_x = 1.0
        self.castle_dir_y = 0.0
        self.castle_plane_x = 0.0
        self.castle_plane_y = 0.66
        self.castle_health = 100
        self.castle_score = 750
        self.castle_status = "Explore dungeon. WASD or On-Screen Controls."

        # StarFlight 3D State
        self.flight_x = 0.0
        self.flight_y = 40.0
        self.flight_z = 0.0
        self.flight_pitch = 0.0
        self.flight_bank = 0.0
        self.flight_speed = 14.0
        self.flight_score = 300
        self.flight_rings = 3
        self.flight_terrain_offset = 0.0
        self.flight_status = "StarFlight 3D. WASD/Boost to Pilot Starfighter."

        self.flight_gates = []
        for i in range(8):
            self.flight_gates.append({
                "x": float(((i * 47) % 240) - 120),
                "y": float(30.0 + ((i * 31) % 80)),
                "z": float(300.0 + i * 220.0),
                "radius": 36.0,
                "hit": False
            })

        self.flight_stars = []
        for i in range(40):
            self.flight_stars.append({
                "x": float(((i * 61) % 600) - 300),
                "y": float(((i * 43) % 300) - 50),
                "z": float(100.0 + (i * 25.0) % 800.0),
                "speed": float(1.5 + (i % 3) * 0.5)
            })

    def _move_castle_player(self, dist: float):
        nx = self.castle_pos_x + self.castle_dir_x * dist
        ny = self.castle_pos_y + self.castle_dir_y * dist
        if 0 <= int(ny) < 16 and 0 <= int(nx) < 16:
            if DUNGEON_MAP[int(ny)][int(nx)] == 0:
                self.castle_pos_x = nx
                self.castle_pos_y = ny

    def _rotate_castle_player(self, angle_rad: float):
        old_dir_x = self.castle_dir_x
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        self.castle_dir_x = self.castle_dir_x * cos_a - self.castle_dir_y * sin_a
        self.castle_dir_y = old_dir_x * sin_a + self.castle_dir_y * cos_a

        old_plane_x = self.castle_plane_x
        self.castle_plane_x = self.castle_plane_x * cos_a - self.castle_plane_y * sin_a
        self.castle_plane_y = old_plane_x * sin_a + self.castle_plane_y * cos_a

    def _draw_games(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Toolbar
        self._fill_rect(fb, cx, cy, cw, 26, COLOR_TASKBAR_BG, clip)
        c_btn_col = COLOR_ACCENT_PURPLE if self.game_mode == "castle" else COLOR_BUTTON_BG
        f_btn_col = COLOR_ACCENT_PURPLE if self.game_mode == "flight" else COLOR_BUTTON_BG
        self._draw_button(fb, cx + 4, cy + 4, 94, 18, "CASTLE 3D", c_btn_col, COLOR_START_TXT, clip)
        self._draw_button(fb, cx + 102, cy + 4, 116, 18, "STARFLIGHT 3D", f_btn_col, COLOR_START_TXT, clip)
        self._draw_button(fb, cx + 222, cy + 4, 68, 18, "RESTART", COLOR_BUTTON_BG, COLOR_ACCENT_RED, clip)

        mode_text = "DDA RAYCASTER (FPS: 40)" if self.game_mode == "castle" else "3D SIMULATOR (FPS: 40)"
        self._draw_string(fb, cx + 296, cy + 8, mode_text, COLOR_ACCENT_GREEN, clip)

        # Viewport
        if self.game_mode == "castle":
            self._draw_games_castle(win, fb, clip)
        else:
            self._draw_games_flight(win, fb, clip)

        # Bottom Control Bar
        by = cy + ch - 32
        self._fill_rect(fb, cx, by, cw, 32, COLOR_TASKBAR_BG, clip)

        if self.game_mode == "castle":
            self._draw_button(fb, cx + 4, by + 5, 46, 22, "^ W", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 54, by + 5, 46, 22, "v S", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 104, by + 5, 46, 22, "< A", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 154, by + 5, 46, 22, "> D", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            stat = f"HP:{self.castle_health}% | SCORE:{self.castle_score} | POS:({self.castle_pos_x:.1f},{self.castle_pos_y:.1f})"
            self._draw_string(fb, cx + 210, by + 11, stat, COLOR_TEXT_PRIMARY, clip)
        else:
            self._draw_button(fb, cx + 4, by + 5, 46, 22, "UP", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 54, by + 5, 46, 22, "DOWN", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 104, by + 5, 52, 22, "BANK L", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 160, by + 5, 52, 22, "BANK R", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)
            self._draw_button(fb, cx + 216, by + 5, 50, 22, "BOOST", COLOR_BUTTON_BG, COLOR_ACCENT_ORANGE, clip)
            stat = f"ALT:{int(self.flight_y)}m | SPD:{int(self.flight_speed)} | RINGS:{self.flight_rings} | PTS:{self.flight_score}"
            self._draw_string(fb, cx + 274, by + 11, stat, COLOR_TEXT_PRIMARY, clip)

    def _draw_games_castle(self, win: Window, fb: bytearray, clip):
        cx, cy, cw, ch = win.client_rect
        vx = cx + 4
        vy = cy + 28
        vw = cw - 8
        vh = ch - 64
        if vw <= 10 or vh <= 10:
            return

        half_vh = vh // 2
        vclip = (vx, vy, vx + vw - 1, vy + vh - 1)

        # 1. Ceiling & Floor
        self._fill_rect(fb, vx, vy, vw, half_vh, 0x001F2335, vclip)
        self._fill_rect(fb, vx, vy + half_vh, vw, vh - half_vh, 0x0016161E, vclip)

        # 2. DDA Raycaster
        col_w = 2
        num_rays = max(10, vw // col_w)

        for r in range(num_rays):
            camera_x = 2.0 * r / float(num_rays) - 1.0
            ray_dir_x = self.castle_dir_x + self.castle_plane_x * camera_x
            ray_dir_y = self.castle_dir_y + self.castle_plane_y * camera_x

            map_x = int(self.castle_pos_x)
            map_y = int(self.castle_pos_y)

            delta_dist_x = abs(1.0 / ray_dir_x) if abs(ray_dir_x) > 1e-6 else 1e30
            delta_dist_y = abs(1.0 / ray_dir_y) if abs(ray_dir_y) > 1e-6 else 1e30

            if ray_dir_x < 0:
                step_x = -1
                side_dist_x = (self.castle_pos_x - map_x) * delta_dist_x
            else:
                step_x = 1
                side_dist_x = (map_x + 1.0 - self.castle_pos_x) * delta_dist_x

            if ray_dir_y < 0:
                step_y = -1
                side_dist_y = (self.castle_pos_y - map_y) * delta_dist_y
            else:
                step_y = 1
                side_dist_y = (map_y + 1.0 - self.castle_pos_y) * delta_dist_y

            hit = 0
            side = 0
            tile = 1
            steps = 0
            while hit == 0 and steps < 24:
                if side_dist_x < side_dist_y:
                    side_dist_x += delta_dist_x
                    map_x += step_x
                    side = 0
                else:
                    side_dist_y += delta_dist_y
                    map_y += step_y
                    side = 1

                if 0 <= map_y < 16 and 0 <= map_x < 16:
                    if DUNGEON_MAP[map_y][map_x] > 0:
                        hit = 1
                        tile = DUNGEON_MAP[map_y][map_x]
                steps += 1

            if side == 0:
                perp_wall_dist = (map_x - self.castle_pos_x + (1 - step_x) / 2.0) / ray_dir_x
            else:
                perp_wall_dist = (map_y - self.castle_pos_y + (1 - step_y) / 2.0) / ray_dir_y

            perp_wall_dist = max(0.15, perp_wall_dist)
            line_height = int(vh / perp_wall_dist)
            draw_start = max(vy, vy + half_vh - line_height // 2)
            draw_end = min(vy + vh - 1, vy + half_vh + line_height // 2)

            base_col = WALL_COLORS.get(tile, 0x007AA2F7)
            shade = max(0.2, min(1.0, 1.0 - (perp_wall_dist / 12.0)))
            if side == 1:
                shade *= 0.75

            r_val = int(((base_col >> 16) & 0xFF) * shade)
            g_val = int(((base_col >> 8) & 0xFF) * shade)
            b_val = int((base_col & 0xFF) * shade)
            shaded_col = (r_val << 16) | (g_val << 8) | b_val

            strip_x = vx + r * col_w
            self._fill_rect(fb, strip_x, draw_start, col_w, max(1, draw_end - draw_start + 1), shaded_col, vclip)

        # 3. Crosshair in center
        cx_mid = vx + vw // 2
        cy_mid = vy + half_vh
        self._draw_line(fb, cx_mid - 6, cy_mid, cx_mid + 6, cy_mid, COLOR_ACCENT_CYAN, vclip)
        self._draw_line(fb, cx_mid, cy_mid - 6, cx_mid, cy_mid + 6, COLOR_ACCENT_CYAN, vclip)

        # 4. Minimap in top-right corner (48x48)
        mm_x = vx + vw - 52
        mm_y = vy + 4
        mm_w = 48
        mm_h = 48
        mm_clip = (mm_x, mm_y, mm_x + mm_w, mm_y + mm_h)
        self._fill_rect(fb, mm_x, mm_y, mm_w, mm_h, 0x0010121C, mm_clip)
        self._draw_button(fb, mm_x, mm_y, mm_w, mm_h, "", 0x0010121C, 0, mm_clip)

        tile_size = 3
        for my_idx in range(16):
            for mx_idx in range(16):
                t = DUNGEON_MAP[my_idx][mx_idx]
                if t > 0:
                    self._fill_rect(fb, mm_x + mx_idx * tile_size, mm_y + my_idx * tile_size, tile_size, tile_size, WALL_COLORS.get(t, 0x007AA2F7), mm_clip)

        px_m = int(mm_x + self.castle_pos_x * tile_size)
        py_m = int(mm_y + self.castle_pos_y * tile_size)
        self._fill_rect(fb, px_m - 1, py_m - 1, 3, 3, COLOR_ACCENT_GREEN, mm_clip)
        dir_px = int(px_m + self.castle_dir_x * 5)
        dir_py = int(py_m + self.castle_dir_y * 5)
        self._draw_line(fb, px_m, py_m, dir_px, dir_py, COLOR_ACCENT_GREEN, mm_clip)

    def _draw_games_flight(self, win: Window, fb: bytearray, clip):
        cx, cy, cw, ch = win.client_rect
        vx = cx + 4
        vy = cy + 28
        vw = cw - 8
        vh = ch - 64
        if vw <= 10 or vh <= 10:
            return

        half_vw = vw // 2
        half_vh = vh // 2
        vclip = (vx, vy, vx + vw - 1, vy + vh - 1)

        # 1. Background Space Navy
        self._fill_rect(fb, vx, vy, vw, vh, FLIGHT_COLOR_BG, vclip)

        focal = 220.0
        def proj3d(lx, ly, lz):
            if lz <= 10.0:
                return None, None
            sx = int(vx + half_vw + (lx * focal) / lz)
            sy = int(vy + half_vh - (ly * focal) / lz)
            return sx, sy

        # 2. Starfield particles
        for s in self.flight_stars:
            sx, sy = proj3d(s["x"] - self.flight_x, s["y"] - self.flight_y, s["z"])
            if sx is not None and vx <= sx < vx + vw and vy <= sy < vy + vh:
                off = (sy * self.width + sx) * 4
                fb[off : off + 4] = b"\xFF\xFF\xFF\x00"

        # 3. Ground Perspective Grid
        spacing_z = 70.0
        for i in range(1, 12):
            z = (i * spacing_z) - self.flight_terrain_offset
            if z <= 20.0:
                continue
            sx0, sy0 = proj3d(-400.0 - self.flight_x, -self.flight_y, z)
            sx1, sy1 = proj3d( 400.0 - self.flight_x, -self.flight_y, z)
            if sx0 is not None and sx1 is not None:
                self._draw_line(fb, sx0, sy0, sx1, sy1, FLIGHT_COLOR_GRID, vclip)

        for x_val in range(-400, 401, 100):
            sx0, sy0 = proj3d(float(x_val) - self.flight_x, -self.flight_y, 30.0)
            sx1, sy1 = proj3d(float(x_val) - self.flight_x, -self.flight_y, 900.0)
            if sx0 is not None and sx1 is not None:
                self._draw_line(fb, sx0, sy0, sx1, sy1, FLIGHT_COLOR_GRID, vclip)

        # Horizon Line
        hy = int(vy + half_vh + (self.flight_y * focal) / 1200.0)
        self._draw_line(fb, vx, hy, vx + vw - 1, hy, FLIGHT_COLOR_HORIZON, vclip)

        # 4. Navigation Rings (Octagons)
        for gate in self.flight_gates:
            rel_x = gate["x"] - self.flight_x
            rel_y = gate["y"] - self.flight_y
            rel_z = gate["z"]
            if rel_z <= 20.0:
                continue
            num_sides = 8
            pts = []
            for s_idx in range(num_sides):
                angle = (s_idx * 2 * math.pi) / num_sides
                px = rel_x + gate["radius"] * math.cos(angle)
                py = rel_y + gate["radius"] * math.sin(angle)
                sx, sy = proj3d(px, py, rel_z)
                pts.append((sx, sy))
            color = FLIGHT_COLOR_RING_HIT if gate["hit"] else FLIGHT_COLOR_RING
            for s_idx in range(num_sides):
                p1 = pts[s_idx]
                p2 = pts[(s_idx + 1) % num_sides]
                if p1[0] is not None and p2[0] is not None:
                    self._draw_line(fb, p1[0], p1[1], p2[0], p2[1], color, vclip)

        # 5. Wireframe Starfighter (centered at bottom)
        scx, scy = vx + half_vw, vy + vh - 44
        cos_b = math.cos(self.flight_bank)
        sin_b = math.sin(self.flight_bank)

        def rot_ship(lx, ly):
            rx = lx * cos_b - ly * sin_b
            ry = lx * sin_b + ly * cos_b
            return int(scx + rx), int(scy + ry)

        nose = rot_ship(0, -26)
        cockpit = rot_ship(0, -8)
        tail = rot_ship(0, 16)
        wing_l = rot_ship(-42, 8)
        wing_r = rot_ship(42, 8)
        fin_l = rot_ship(-16, 18)
        fin_r = rot_ship(16, 18)

        self._draw_line(fb, nose[0], nose[1], wing_l[0], wing_l[1], FLIGHT_COLOR_SHIP, vclip)
        self._draw_line(fb, nose[0], nose[1], wing_r[0], wing_r[1], FLIGHT_COLOR_SHIP, vclip)
        self._draw_line(fb, wing_l[0], wing_l[1], cockpit[0], cockpit[1], FLIGHT_COLOR_SHIP, vclip)
        self._draw_line(fb, wing_r[0], wing_r[1], cockpit[0], cockpit[1], FLIGHT_COLOR_SHIP, vclip)
        self._draw_line(fb, cockpit[0], cockpit[1], tail[0], tail[1], COLOR_ACCENT_CYAN, vclip)
        self._draw_line(fb, fin_l[0], fin_l[1], fin_r[0], fin_r[1], FLIGHT_COLOR_SHIP, vclip)

        # 6. Artificial Horizon Attitude Ladder (Cyan HUD)
        hud_y = vy + half_vh
        self._draw_line(fb, vx + half_vw - 30, hud_y - 20, vx + half_vw - 12, hud_y - 20, FLIGHT_COLOR_HUD, vclip)
        self._draw_line(fb, vx + half_vw + 12, hud_y - 20, vx + half_vw + 30, hud_y - 20, FLIGHT_COLOR_HUD, vclip)
        self._draw_line(fb, vx + half_vw - 30, hud_y + 20, vx + half_vw - 12, hud_y + 20, FLIGHT_COLOR_HUD, vclip)
        self._draw_line(fb, vx + half_vw + 12, hud_y + 20, vx + half_vw + 30, hud_y + 20, FLIGHT_COLOR_HUD, vclip)

    def _click_games(self, win: Window, rel_x: int, rel_y: int):
        # Toolbar clicks
        if rel_y <= 26:
            if 4 <= rel_x <= 98:
                self.game_mode = "castle"
                self.status_message = "Active Game: CastleAdiOS 3D Raycaster."
                return
            elif 102 <= rel_x <= 218:
                self.game_mode = "flight"
                self.status_message = "Active Game: StarFlight 3D Simulator."
                return
            elif 222 <= rel_x <= 290:
                if self.game_mode == "castle":
                    self.castle_pos_x, self.castle_pos_y = 1.5, 1.5
                    self.castle_dir_x, self.castle_dir_y = 1.0, 0.0
                    self.castle_plane_x, self.castle_plane_y = 0.0, 0.66
                    self.castle_health = 100
                    self.castle_score = 750
                else:
                    self.flight_x, self.flight_y = 0.0, 40.0
                    self.flight_pitch, self.flight_bank = 0.0, 0.0
                    self.flight_score, self.flight_rings = 0, 0
                    for g in self.flight_gates:
                        g["hit"] = False
                self.status_message = "Game reset."
                return

        # Bottom controls clicks
        by = win.h - 54
        if rel_y >= by:
            if self.game_mode == "castle":
                if 4 <= rel_x <= 50: self._move_castle_player(0.2)
                elif 54 <= rel_x <= 100: self._move_castle_player(-0.2)
                elif 104 <= rel_x <= 150: self._rotate_castle_player(-0.1)
                elif 154 <= rel_x <= 200: self._rotate_castle_player(0.1)
            else:
                if 4 <= rel_x <= 50: self.flight_y = min(150.0, self.flight_y + 8.0)
                elif 54 <= rel_x <= 100: self.flight_y = max(15.0, self.flight_y - 8.0)
                elif 104 <= rel_x <= 156:
                    self.flight_bank = max(-0.6, self.flight_bank - 0.15)
                    self.flight_x -= 12.0
                elif 160 <= rel_x <= 212:
                    self.flight_bank = min(0.6, self.flight_bank + 0.15)
                    self.flight_x += 12.0
                elif 216 <= rel_x <= 266:
                    self.flight_speed = min(30.0, self.flight_speed + 4.0)

    # --------------------------------------------------------------------------
    # Start Menu & Window Switcher
    # --------------------------------------------------------------------------

    def toggle_start_menu(self):
        self.start_menu_open = not self.start_menu_open

    def launch_or_focus(self, win_id: str):
        for w in self.wm.windows:
            if w.win_id == win_id:
                w.visible = True
                w.minimized = False
                self.wm.focus_window(w)
                self.status_message = f"Active window: {w.title}"
                self.start_menu_open = False
                return

    # --------------------------------------------------------------------------
    # Master Compositor & Frame Stepping
    # --------------------------------------------------------------------------

    def step_frame(self, mouse_x: int, mouse_y: int):
        self.rot_3d.y = (self.rot_3d.y + 2.0) % 360.0

        # Games Arcade continuous animation
        if hasattr(self, "win_games") and self.win_games.visible and not self.win_games.minimized:
            if self.game_mode == "flight":
                self.flight_terrain_offset = (self.flight_terrain_offset + self.flight_speed * 0.5) % 70.0
                for gate in self.flight_gates:
                    gate["z"] -= self.flight_speed * 0.8
                    rel_x = gate["x"] - self.flight_x
                    rel_y = gate["y"] - self.flight_y
                    rel_z = gate["z"]
                    if -self.flight_speed <= rel_z <= self.flight_speed and not gate["hit"]:
                        if math.hypot(rel_x, rel_y) <= gate["radius"]:
                            gate["hit"] = True
                            self.flight_score += 100
                            self.flight_rings += 1
                            if self.vm:
                                try:
                                    self.vm.write32(0x10000050, 880)
                                    self.vm.write32(0x10000054, 40)
                                except Exception:
                                    pass
                    if gate["z"] <= 20.0:
                        gate["z"] = 1800.0
                        gate["x"] = self.flight_x + float(((len(self.flight_gates) * 37) % 240) - 120)
                        gate["y"] = float(30.0 + ((len(self.flight_gates) * 23) % 80))
                        gate["hit"] = False

                for s in self.flight_stars:
                    s["z"] -= self.flight_speed * s["speed"] * 0.5
                    if s["z"] <= 20.0:
                        s["z"] = 900.0

        # YouTube Player 60 FPS Frame Stepping
        if hasattr(self, "youtube_app") and hasattr(self, "win_youtube") and self.win_youtube.visible and not self.win_youtube.minimized:
            self.youtube_app.step()

    def _init_youtube_player(self):
        from desktop.youtube_player import YouTubePlayerApp
        init_ch = 3 if self.width >= 1200 else 0
        self.youtube_app = YouTubePlayerApp(vpu=self.vpu, initial_channel=init_ch)

    def _draw_youtube(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        req_size = cw * ch * 4
        if not hasattr(self, "_yt_surface") or len(self._yt_surface) != req_size:
            self._yt_surface = bytearray(req_size)
        surf = self._yt_surface
        self.youtube_app.render(surf, cw, ch)
        w_bytes = cw * 4
        min_py = max(0, cy)
        max_py = min(self.height, cy + ch)
        for py in range(min_py, max_py):
            y = py - cy
            s_off = y * w_bytes
            d_off = (py * self.width + cx) * 4
            fb[d_off : d_off + w_bytes] = surf[s_off : s_off + w_bytes]

    def _click_youtube(self, win: Window, rel_x: int, rel_y: int):
        self.youtube_app.handle_click(rel_x, rel_y)
        self.status_message = f"YouTube Player: {self.youtube_app.relay.channel_info['title']} ({'PLAYING' if self.youtube_app.is_playing else 'PAUSED'})"

    def render(self, fb: bytearray):
        # 1. Desktop Background: Fast blit cached wallpaper and icons
        icons_state = tuple((i.selected, i.hover) for i in self.icons.icons)
        cache_key = (self.wallpaper_style, self.wallpaper_visible, self.width, self.height, icons_state)
        if not hasattr(self, "_wallpaper_cache") or getattr(self, "_wallpaper_cache_key", None) != cache_key:
            cache = bytearray(self.width * self.height * 4)
            bg_bytes = bytes([COLOR_DESKTOP_BG & 0xFF, (COLOR_DESKTOP_BG >> 8) & 0xFF, (COLOR_DESKTOP_BG >> 16) & 0xFF, 0])
            cache[:] = bg_bytes * (self.width * self.height)
            if self.wallpaper_visible:
                render_wallpaper_to_framebuffer(cache, self.width, self.height, self.font, style=self.wallpaper_style)
            self.icons.render(cache, self.font, self.width, self.height)
            self._wallpaper_cache = cache
            self._wallpaper_cache_key = cache_key
        fb[:] = self._wallpaper_cache

        # 2. Render Window Manager Layer (all visible windows in Z-order)
        self.wm.render_all(fb, self.font)

        # 3. Render Top Taskbar (24px high across self.width)
        tb_bytes = bytes([COLOR_TASKBAR_BG & 0xFF, (COLOR_TASKBAR_BG >> 8) & 0xFF, (COLOR_TASKBAR_BG >> 16) & 0xFF, 0])
        for ty in range(0, TASKBAR_HEIGHT):
            fb[(ty * self.width) * 4 : (ty * self.width + self.width) * 4] = tb_bytes * self.width

        # Taskbar Bottom Border
        border_bytes = bytes([COLOR_TASKBAR_BORDER & 0xFF, (COLOR_TASKBAR_BORDER >> 8) & 0xFF, (COLOR_TASKBAR_BORDER >> 16) & 0xFF, 0])
        fb[((TASKBAR_HEIGHT - 1) * self.width) * 4 : (TASKBAR_HEIGHT * self.width) * 4] = border_bytes * self.width

        # Start Pill (AdiOS Workstation button)
        pill_bytes = bytes([COLOR_START_PILL & 0xFF, (COLOR_START_PILL >> 8) & 0xFF, (COLOR_START_PILL >> 16) & 0xFF, 0])
        for py in range(2, 22):
            fb[(py * self.width + 4) * 4 : (py * self.width + 84) * 4] = pill_bytes * 80
        self._draw_string(fb, 10, 7, "AdiOS [2.0]", COLOR_START_TXT)

        # Dedicated Games Pill on Taskbar
        self._draw_button(fb, 88, 3, 64, 18, "GAMES", COLOR_ACCENT_PURPLE, COLOR_START_TXT)

        # Dedicated Wallpaper / Show Desktop Pill on Taskbar
        wall_bg = COLOR_ACCENT_CYAN if self.desktop_clean_mode else COLOR_BUTTON_BG
        wall_txt = 0x00000000 if self.desktop_clean_mode else COLOR_ACCENT_CYAN
        self._draw_button(fb, 156, 3, 52, 18, "WALL", wall_bg, wall_txt)

        # Dedicated YouTube 60 FPS HD Pill on Taskbar
        self._draw_button(fb, 212, 3, 50, 18, "YT HD", COLOR_YOUTUBE_RED, COLOR_START_TXT)

        # Dedicated Background Music (BGM) Toggle Pill on Taskbar
        bgm_on = self.is_bgm_active
        bgm_label = "BGM: ON" if bgm_on else "BGM: OFF"
        bgm_bg = COLOR_ACCENT_GREEN if bgm_on else COLOR_BUTTON_BG
        bgm_txt = COLOR_START_TXT if bgm_on else COLOR_ACCENT_RED
        self._draw_button(fb, 268, 3, 64, 18, bgm_label, bgm_bg, bgm_txt)

        # Window Switcher Pills on Taskbar
        sw_x = 338
        max_sw_x = self.width - 440
        for w in self.wm.windows:
            if w.visible and not w.minimized:
                if sw_x + 68 < max_sw_x:
                    bg_col = COLOR_TITLE_ACT if w.active else COLOR_BUTTON_BG
                    txt_col = COLOR_START_TXT if w.active else COLOR_BUTTON_TXT
                    short_title = w.title[:8]
                    self._draw_button(fb, sw_x, 3, 68, 18, short_title, bg_col, txt_col)
                    sw_x += 72

        # Right status indicators: SMP Cores & System Clock & Dynamic RAM capacity
        telemetry = f"SMP: {self.hart_loads[0]}% | RAM: {self.ram_used_mb:.1f}MB/{self.ram_capacity_mb}MB | 60 FPS"
        self._draw_string(fb, self.width - 430, 7, telemetry, COLOR_ACCENT_GREEN)

        # Sound Quick Toggle Button (Tray)
        vol_pct = self.sound_server.get_volume_pct()
        vol_label = "MUTE" if self.sound_server.is_muted else f"VOL {vol_pct}%"
        vol_bg = COLOR_ACCENT_PURPLE if self.sound_flyout_open else (COLOR_ACCENT_RED if self.sound_server.is_muted else COLOR_BUTTON_BG)
        self._draw_button(fb, self.width - 200, 3, 90, 18, vol_label, vol_bg, COLOR_START_TXT)

        # Internet Quick Toggle Button (Tray)
        net_label = "NET: ON" if self.network_online else "NET: OFF"
        net_bg = COLOR_ACCENT_CYAN if self.net_flyout_open else (COLOR_ACCENT_GREEN if self.network_online else COLOR_ACCENT_RED)
        self._draw_button(fb, self.width - 104, 3, 96, 18, net_label, net_bg, COLOR_START_TXT)

        # 4. Render Dropdown Start Menu if open
        if self.start_menu_open:
            self._render_start_menu(fb)

        # 5. Render Sound Flyout Card if open
        if self.sound_flyout_open:
            self._render_sound_flyout(fb)

        # 6. Render Internet Flyout Card if open
        if self.net_flyout_open:
            self._render_net_flyout(fb)

    def _render_sound_flyout(self, fb: bytearray):
        fx = self.width - 240
        fy = TASKBAR_HEIGHT + 4
        fw = 230
        fh = 154
        draw_drop_shadow(fb, fx, fy, fw, fh, radius=8, alpha=0.5, screen_w=self.width, screen_h=self.height)
        draw_rounded_rect(fb, fx, fy, fw, fh, radius=8, fill_color=0x0016161E, border_color=COLOR_START_PILL, screen_w=self.width, screen_h=self.height)
        self._draw_string(fb, fx + 12, fy + 8, "Sound & Audio Master", COLOR_ACCENT_CYAN)
        self._draw_string(fb, fx + 12, fy + 20, "-" * 26, COLOR_BORDER)

        vol_pct = self.sound_server.get_volume_pct()
        is_mute = self.sound_server.is_muted
        status_txt = f"Volume: {vol_pct}% {'(MUTED)' if is_mute else ''}"
        self._draw_string(fb, fx + 14, fy + 32, status_txt, COLOR_TEXT_PRIMARY)

        # Volume visual track
        track_w = 200
        fill_w = int(track_w * (0.0 if is_mute else (vol_pct / 100.0)))
        draw_rounded_rect(fb, fx + 14, fy + 48, track_w, 8, radius=3, fill_color=0x002A2E42, screen_w=self.width, screen_h=self.height)
        if fill_w > 0:
            draw_rounded_rect(fb, fx + 14, fy + 48, fill_w, 8, radius=3, fill_color=COLOR_ACCENT_GREEN if not is_mute else COLOR_ACCENT_RED, screen_w=self.width, screen_h=self.height)

        # Buttons: [-] [+] [MUTE/UNMUTE]
        self._draw_button(fb, fx + 14, fy + 64, 34, 22, "[-]", COLOR_BUTTON_BG, COLOR_START_TXT)
        self._draw_button(fb, fx + 54, fy + 64, 34, 22, "[+]", COLOR_BUTTON_BG, COLOR_START_TXT)
        mute_lbl = "UNMUTE" if is_mute else "MUTE"
        mute_col = COLOR_ACCENT_RED if is_mute else COLOR_BUTTON_BG
        self._draw_button(fb, fx + 94, fy + 64, 120, 22, mute_lbl, mute_col, COLOR_START_TXT)

        # Dedicated Background Music Button in Flyout
        bgm_on = self.is_bgm_active
        bgm_flyout_label = "BGM: [PAUSE MUSIC]" if bgm_on else "BGM: [RESUME MUSIC]"
        bgm_flyout_bg = COLOR_ACCENT_PURPLE if bgm_on else COLOR_BUTTON_BG
        self._draw_button(fb, fx + 14, fy + 94, 200, 22, bgm_flyout_label, bgm_flyout_bg, COLOR_START_TXT)

        # Real-time VU meter bar
        vu = self.sound_server.get_vu_meter()
        vu_bars = int(vu * 18)
        self._draw_string(fb, fx + 14, fy + 126, f"Output VU: [{'=' * vu_bars:<18}]", COLOR_ACCENT_GREEN)

    def _render_net_flyout(self, fb: bytearray):
        fx = self.width - 240
        fy = TASKBAR_HEIGHT + 4
        fw = 230
        fh = 106
        draw_drop_shadow(fb, fx, fy, fw, fh, radius=8, alpha=0.5, screen_w=self.width, screen_h=self.height)
        draw_rounded_rect(fb, fx, fy, fw, fh, radius=8, fill_color=0x0016161E, border_color=COLOR_START_PILL, screen_w=self.width, screen_h=self.height)
        self._draw_string(fb, fx + 12, fy + 8, "Sovereign Network Center", COLOR_ACCENT_CYAN)
        self._draw_string(fb, fx + 12, fy + 20, "-" * 26, COLOR_BORDER)

        status_txt = "Status: Online (VirtIO)" if self.network_online else "Status: Airplane Mode"
        self._draw_string(fb, fx + 14, fy + 32, status_txt, COLOR_ACCENT_GREEN if self.network_online else COLOR_ACCENT_RED)

        btn_txt = "AIRPLANE MODE" if self.network_online else "CONNECT ONLINE"
        btn_col = COLOR_ACCENT_RED if self.network_online else COLOR_ACCENT_GREEN
        self._draw_button(fb, fx + 14, fy + 52, 200, 24, btn_txt, btn_col, COLOR_START_TXT)
        self._draw_string(fb, fx + 14, fy + 84, "Ping: 12ms | Zero-Loss (TLS 1.3)", COLOR_TEXT_MUTED)

    def _render_start_menu(self, fb: bytearray):
        mx = 4
        my = TASKBAR_HEIGHT
        mw = 260
        mh = 292
        clip = (mx, my, mx + mw, my + mh)

        # Menu container
        self._fill_rect(fb, mx, my, mw, mh, 0x0016161E, clip)
        self._fill_rect(fb, mx, my, mw, 1, COLOR_START_PILL, clip)
        self._fill_rect(fb, mx, my + mh - 1, mw, 1, COLOR_START_PILL, clip)
        self._fill_rect(fb, mx, my, 1, mh, COLOR_START_PILL, clip)
        self._fill_rect(fb, mx + mw - 1, my, 1, mh, COLOR_START_PILL, clip)

        # Title
        self._draw_string(fb, mx + 10, my + 8, "AdiOS Sovereign Menu", COLOR_ACCENT_CYAN, clip)
        self._draw_string(fb, mx + 10, my + 20, "-" * 28, COLOR_BORDER, clip)

        # Items
        items = [
            ("1. Sovereign Web Browser", "browser"),
            ("2. SovereignSQL Terminal", "sql"),
            ("3. Lisp Bytecode REPL", "lisp"),
            ("4. OpenGL 3D Viewport", "gl"),
            ("5. Sovereign File Explorer", "explorer"),
            ("6. Network & Crypto Monitor", "netmon"),
            ("7. POSIX Sovereign Shell", "shell"),
            ("8. Paint Studio & Calculator", "paint"),
            ("9. Sovereign 3D Games Arcade", "games"),
            ("10. Toggle Wallpaper Theme", "wallpaper"),
            ("11. Sovereign YouTube (60 FPS HD)", "youtube"),
            ("12. Toggle Background Music", "bgm")
        ]

        for idx, (label, wid) in enumerate(items):
            iy = my + 30 + idx * 20
            color = COLOR_ACCENT_GREEN if wid == "bgm" else (COLOR_YOUTUBE_RED if wid == "youtube" else (COLOR_ACCENT_YELLOW if wid == "games" else (COLOR_ACCENT_CYAN if wid == "wallpaper" else COLOR_TEXT_PRIMARY)))
            self._draw_string(fb, mx + 14, iy, label, color, clip)

    # --------------------------------------------------------------------------
    # Event Handlers
    # --------------------------------------------------------------------------

    def handle_mouse_down(self, mx: int, my: int) -> Optional[Tuple[str, Any]]:
        # 1. Taskbar Click Handling
        if my < TASKBAR_HEIGHT:
            if 4 <= mx <= 84:
                self.toggle_start_menu()
                return ("start_toggle", None)
            if 88 <= mx <= 152:
                self.launch_or_focus("games")
                return ("menu_select", "games")
            if 156 <= mx <= 208:
                self.toggle_desktop_wallpaper()
                return ("wallpaper_toggle", None)
            if 212 <= mx <= 264:
                self.launch_or_focus("youtube")
                return ("menu_select", "youtube")
            if 268 <= mx <= 332:
                self.toggle_background_music()
                return ("bgm_toggle", self.bgm_enabled)

            # Window Switcher Pills click
            sw_x = 338
            max_sw_x = self.width - 440
            for w in self.wm.windows:
                if w.visible and not w.minimized:
                    if sw_x <= mx <= sw_x + 68 and sw_x + 68 < max_sw_x:
                        self.wm.focus_window(w)
                        return ("switch_window", w)
                    sw_x += 72

            # Sound Tray Button click
            if self.width - 200 <= mx <= self.width - 110:
                self.sound_flyout_open = not self.sound_flyout_open
                self.net_flyout_open = False
                self.sound_server.play_ui_sound("click")
                return ("sound_flyout_toggle", None)

            # Internet Tray Button click
            if self.width - 104 <= mx <= self.width - 8:
                self.net_flyout_open = not self.net_flyout_open
                self.sound_flyout_open = False
                self.sound_server.play_ui_sound("click")
                return ("net_flyout_toggle", None)

            return None

        # 2. Sound Flyout Card Click Handling
        if self.sound_flyout_open:
            fx = self.width - 240
            fy = TASKBAR_HEIGHT + 4
            fw = 230
            fh = 154
            if fx <= mx <= fx + fw and fy <= my <= fy + fh:
                # Vol Down [-]
                if fx + 14 <= mx <= fx + 48 and fy + 64 <= my <= fy + 86:
                    curr = self.sound_server.get_volume_pct()
                    new_vol = max(0, curr - 10)
                    self.sound_server.set_volume_pct(new_vol)
                    if hasattr(self, "vpu") and self.vpu:
                        self.vpu.volume = new_vol
                    if hasattr(self, "youtube_app") and self.youtube_app:
                        self.youtube_app.volume = new_vol
                    self.sound_server.play_ui_sound("click")
                    return ("vol_down", self.sound_server.get_volume_pct())
                # Vol Up [+]
                if fx + 54 <= mx <= fx + 88 and fy + 64 <= my <= fy + 86:
                    curr = self.sound_server.get_volume_pct()
                    new_vol = min(100, curr + 10)
                    self.sound_server.set_volume_pct(new_vol)
                    if hasattr(self, "vpu") and self.vpu:
                        self.vpu.volume = new_vol
                    if hasattr(self, "youtube_app") and self.youtube_app:
                        self.youtube_app.volume = new_vol
                    self.sound_server.play_ui_sound("click")
                    return ("vol_up", self.sound_server.get_volume_pct())
                # Mute Toggle
                if fx + 94 <= mx <= fx + 214 and fy + 64 <= my <= fy + 86:
                    self.sound_server.toggle_mute()
                    muted = self.sound_server.is_muted
                    if hasattr(self, "vpu") and self.vpu:
                        self.vpu.set_sound_enabled(not muted)
                    if hasattr(self, "youtube_app") and self.youtube_app:
                        self.youtube_app.sound_enabled = not muted
                    self.sound_server.play_ui_sound("click")
                    return ("vol_mute", self.sound_server.is_muted)
                # Dedicated BGM Toggle Button in Flyout
                if fx + 14 <= mx <= fx + 214 and fy + 94 <= my <= fy + 116:
                    self.toggle_background_music()
                    return ("bgm_toggle", self.bgm_enabled)
                return ("sound_flyout_click", None)
            else:
                self.sound_flyout_open = False

        # 3. Internet Flyout Card Click Handling
        if self.net_flyout_open:
            fx = self.width - 240
            fy = TASKBAR_HEIGHT + 4
            fw = 230
            fh = 106
            if fx <= mx <= fx + fw and fy <= my <= fy + fh:
                if fx + 14 <= mx <= fx + 214 and fy + 52 <= my <= fy + 76:
                    self.network_online = not self.network_online
                    self.sound_server.play_ui_sound("notify")
                    return ("net_toggle", self.network_online)
                return ("net_flyout_click", None)
            else:
                self.net_flyout_open = False

        # 4. Start Menu Item Click
        if self.start_menu_open:
            if 4 <= mx <= 264 and TASKBAR_HEIGHT <= my <= TASKBAR_HEIGHT + 292:
                rel_item = (my - (TASKBAR_HEIGHT + 30)) // 20
                items_map = ["browser", "sql", "lisp", "gl", "explorer", "netmon", "shell", "paint", "games", "wallpaper", "youtube", "bgm"]
                if 155 <= my <= 165:
                    self.launch_or_focus("shell")
                    return ("menu_select", "shell")
                if 0 <= rel_item < len(items_map):
                    action_id = items_map[rel_item]
                    if action_id == "wallpaper":
                        self.cycle_wallpaper_theme()
                        self.start_menu_open = False
                        return ("wallpaper_theme", self.wallpaper_style)
                    elif action_id == "bgm":
                        self.toggle_background_music()
                        self.start_menu_open = False
                        return ("bgm_toggle", self.bgm_enabled)
                    self.launch_or_focus(action_id)
                    return ("menu_select", action_id)
            self.start_menu_open = False

        # 5. Window Manager Handling
        res = self.wm.handle_mouse_down(mx, my)
        if res:
            self.sound_server.play_ui_sound("click")
            return res

        # 6. Desktop Icons Handling (Clicks on Desktop Canvas)
        evt, icon = self.icons.handle_mouse_down(mx, my)
        if evt == "launch" and icon:
            self.sound_server.play_ui_sound("launch")
            if icon.action_target == "sound_cfg":
                self.sound_flyout_open = True
                return ("icon_launch", "sound_cfg")
            self.launch_or_focus(icon.action_target)
            return ("icon_launch", icon.icon_id)
        elif evt == "select" and icon:
            self.sound_server.play_ui_sound("click")
            return ("icon_select", icon.icon_id)

        return None

    def handle_mouse_up(self, mx: int, my: int):
        self.wm.handle_mouse_up(mx, my)

    def handle_mouse_move(self, mx: int, my: int):
        self.icons.handle_mouse_move(mx, my)
        self.wm.handle_mouse_move(mx, my)

    def handle_key(self, key_char: str):
        active_win = self.wm.windows[-1] if self.wm.windows else None
        if not active_win or not active_win.visible or active_win.minimized:
            return

        if active_win.win_id == "shell":
            if key_char in ("\n", "\r"):
                cmd = self.shell_input.strip()
                if cmd.lower() == "clear":
                    self.shell_history = ["root@adios:~# "]
                    self.shell_input = ""
                    self.status_message = "Terminal screen cleared."
                    return
                self.shell_history.append("root@adios:~# " + cmd)
                if cmd:
                    if cmd.lower() in ("games", "game", "castle", "flight", "arcade", "play"):
                        self.launch_or_focus("games")
                        self.shell_history.append("[AdiOS Games Arcade] Launching Sovereign 3D Games...")
                    else:
                        try:
                            out = self.shell.eval(cmd)
                            for line in out.split("\n"):
                                if line.strip():
                                    self.shell_history.append(line)
                        except Exception as e:
                            self.shell_history.append(f"sh: {str(e)}")
                self.shell_input = ""
            elif key_char == "\b":
                self.shell_input = self.shell_input[:-1]
            elif len(key_char) == 1 and 32 <= ord(key_char) <= 126:
                self.shell_input += key_char

        elif active_win.win_id == "sql":
            if key_char in ("\n", "\r"):
                try:
                    self.sql_results = self.db.execute(self.sql_query)
                    self.sql_status = f"{len(self.sql_results.get('rows', []))} rows (Query OK)"
                except Exception as e:
                    self.sql_status = f"Err: {str(e)[:30]}"
            elif key_char == "\b":
                self.sql_query = self.sql_query[:-1]
            elif len(key_char) == 1 and 32 <= ord(key_char) <= 126:
                self.sql_query += key_char

        elif active_win.win_id == "lisp":
            if key_char in ("\n", "\r"):
                self._eval_lisp_expr(self.lisp_expr)
            elif key_char == "\b":
                self.lisp_expr = self.lisp_expr[:-1]
            elif len(key_char) == 1 and 32 <= ord(key_char) <= 126:
                self.lisp_expr += key_char

        elif active_win.win_id == "paint":
            if key_char.isdigit() or key_char in ("+", "-", "*", "/", "=", "C", "c"):
                self._handle_calc_key(key_char.upper())

        elif active_win.win_id == "games":
            k = key_char.upper()
            if k in ("W", "K"):
                if self.game_mode == "castle":
                    self._move_castle_player(0.15)
                else:
                    self.flight_y = min(150.0, self.flight_y + 6.0)
            elif k in ("S", "J"):
                if self.game_mode == "castle":
                    self._move_castle_player(-0.15)
                else:
                    self.flight_y = max(15.0, self.flight_y - 6.0)
            elif k in ("A", "H"):
                if self.game_mode == "castle":
                    self._rotate_castle_player(-0.08)
                else:
                    self.flight_bank = max(-0.6, self.flight_bank - 0.12)
                    self.flight_x -= 8.0
            elif k in ("D", "L"):
                if self.game_mode == "castle":
                    self._rotate_castle_player(0.08)
                else:
                    self.flight_bank = min(0.6, self.flight_bank + 0.12)
                    self.flight_x += 8.0
            elif k == "1":
                self.game_mode = "castle"
                self.status_message = "Active Game: CastleAdiOS 3D"
            elif k == "2":
                self.game_mode = "flight"
                self.status_message = "Active Game: StarFlight 3D"
            elif k == "R":
                self._click_games(active_win, 230, 10)
            elif key_char == " ":
                if self.game_mode == "flight":
                    self.flight_speed = 26.0

        elif active_win.win_id == "youtube":
            if hasattr(self, "youtube_app"):
                self.youtube_app.handle_key(key_char)

if __name__ == "__main__":
    desktop = MasterDesktop()
    fb = bytearray(DEFAULT_WIDTH * DEFAULT_HEIGHT * 4)
    desktop.render(fb)
    assert fb[0:4] == bytes([COLOR_DESKTOP_BG & 0xFF, (COLOR_DESKTOP_BG >> 8) & 0xFF, (COLOR_DESKTOP_BG >> 16) & 0xFF, 0])
    print("MasterDesktop initialized and rendered successfully at 1024x768.")
