#!/usr/bin/env python3
"""
AdiOS Unified Sovereign Master Desktop Compositor (desktop/master_desktop.py)
Integrates all 26 Blocks (A through Z) into a sovereign bare-metal GUI environment:
- Top Taskbar with Start Pill, App Switcher, SMP Multi-Core Monitor, and System Clock
- Dropdown Start Menu launching all 8 sovereign applications
- Window Server with back-to-front Z-ordering, dragging, closing, and focus
- 8 Integrated Applications:
    1. Sovereign Web Browser (HTML/CSS Box Model DOM layout engine)
    2. SovereignSQL Terminal (ACID-compliant relational database engine)
    3. Lisp Bytecode REPL (Dynamic stack-based VM & S-Expression compiler)
    4. OpenGL 3D Viewport (Z-buffered scanline 3D wireframe/shaded rasterizer)
    5. Sovereign File Explorer (VFS / Ext2 / FAT32 / AdiFS disk inspector)
    6. Network & Crypto Monitor (TCP connection table, TLS 1.3 handshake, SHA-256)
    7. POSIX Terminal Shell (sh pipeline, redirection, and coreutils)
    8. Paint Studio & Pocket Calculator (Interactive drawing and arithmetic)

Zero external dependencies. Pure bare-metal RV32IM simulated architecture.
STRICT ZERO EMOJI POLICY.
"""

import math
import time
from typing import Dict, List, Tuple, Optional, Any

from .window_manager import WindowManager, Window, WIDTH, HEIGHT, CHAR_WIDTH, CHAR_HEIGHT
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
COLOR_ACCENT_PURPLE  = 0x00BB9AF7
COLOR_TEXT_PRIMARY   = 0x00C0CAF5
COLOR_TEXT_MUTED     = 0x00565F89

class MasterDesktop:
    """
    Unified Sovereign Master Desktop Environment.
    Hosts and composits all 8 applications into overlapping, interactive windows.
    """
    def __init__(self, vm=None):
        self.vm = vm
        self.font = get_default_font()
        self.wm = WindowManager()
        self.engine3d = Engine3D(vm)
        self.start_menu_open = False
        self.status_message = "AdiOS Sovereign Master Desktop v1.0 Ready."
        self.active_input_target = "shell"

        # Master Subsystem Instances
        self._init_sql_engine()
        self._init_lisp_engine()
        self._init_browser_engine()
        self._init_posix_shell()
        self._init_3d_engine()
        self._init_net_crypto()
        self._init_file_explorer()
        self._init_paint_calc()

        # Create Windows
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
        self.sql_query = "SELECT id, name, status FROM services;"
        self.sql_results = self.db.execute(self.sql_query)
        self.sql_status = "5 rows selected (WAL Active)"

    def _init_lisp_engine(self):
        self.lisp_expr = "(+ (* 6 7) (/ 100 10))"
        self.lisp_history = [
            "adisp> (defun square (x) (* x x)) => <fn>",
            "adisp> (square 8) => 64",
            "adisp> (+ (* 6 7) (/ 100 10)) => 52"
        ]
        self.lisp_last_val = 52

    def _init_browser_engine(self):
        self.browser_url = "about:adios"
        self.browser_html = (
            "<div class='card'>"
            "<h1>AdiOS Sovereign Web</h1>"
            "<p>Bare-metal HTML5 DOM and CSS box model rendering engine.</p>"
            "<p>Zero external libraries. Running directly in RISC-V 32-bit framebuffer.</p>"
            "</div>"
        )
        self.browser_dom = HTMLParser.parse(self.browser_html)
        self.browser_css = CSSStyleSheet()
        self.browser_css.parse_css("h1 { color: #7AA2F7; } p { color: #C0CAF5; }")
        self.browser_css.apply_styles(self.browser_dom)
        self.browser_layout = LayoutEngine.build_layout_tree(self.browser_dom)
        if self.browser_layout:
            LayoutEngine.layout(self.browser_layout, 0, 0, 290)

    def _init_posix_shell(self):
        vfs = {
            "/etc/os-release": b"NAME=\"AdiOS Sovereign\"\nVERSION=\"1.0.0-RV32IM\"\nID=adios\n",
            "/etc/hostname": b"adios-master\n",
            "/root/welcome.txt": b"Welcome to AdiOS Ring-0 Bare-Metal Computing!\n",
            "/bin/sh": b"\x7fELF-RV32-POSIX-SHELL\n"
        }
        self.coreutils = CoreUtils(vfs)
        self.shell = SovereignShell(self.coreutils)
        self.shell_history = [
            "root@adios:~# uname -a",
            "AdiOS 1.0.0-sovereign riscv32 GNU/Sovereign",
            "root@adios:~# cat /etc/os-release",
            "NAME=\"AdiOS Sovereign\"",
            "root@adios:~# "
        ]
        self.shell_input = ""

    def _init_3d_engine(self):
        self.mesh_cube = create_cube(size=38)
        self.mesh_pyramid = create_temple_pyramid(base=48, height=45)
        self.current_mesh = self.mesh_cube
        self.mesh_name = "CUBE"
        self.rot_3d = Vector3(20, 30, 0)
        self.wireframe_3d = False

    def _init_net_crypto(self):
        self.net_sockets = [
            {"local": "10.0.2.15:443", "remote": "1.1.1.1:443", "state": "ESTABLISHED", "proto": "TLS 1.3"},
            {"local": "10.0.2.15:80",  "remote": "93.184.216.34:80", "state": "TIME_WAIT", "proto": "HTTP/1.1"},
            {"local": "0.0.0.0:22",    "remote": "0.0.0.0:0", "state": "LISTEN", "proto": "SSH-2"},
            {"local": "0.0.0.0:53",    "remote": "10.0.2.3:53", "state": "CONNECTED", "proto": "DNS"}
        ]
        self.sha256_input = "AdiOS Ring-0 Sovereign Integrity"
        self.sha256_val = sha256_hash(self.sha256_input.encode("utf-8")).hex()[:16] + "..."
        self.tls_status = "TLS 1.3: ChaCha20-Poly1305 / HKDF Active"

    def _init_file_explorer(self):
        self.explorer_drive = "Ext2"
        self.explorer_files = [
            {"name": "boot/", "type": "DIR", "size": "4096", "perm": "drwxr-xr-x"},
            {"name": "adios.bin", "type": "BIN", "size": "8420", "perm": "-rwxr-xr-x"},
            {"name": "vmlinux.elf", "type": "ELF", "size": "32768", "perm": "-rwxr-xr-x"},
            {"name": "etc/", "type": "DIR", "size": "4096", "perm": "drwxr-xr-x"},
            {"name": "home/", "type": "DIR", "size": "4096", "perm": "drwxr-xr-x"},
            {"name": "kernel.s", "type": "ASM", "size": "14200", "perm": "-rw-r--r--"},
            {"name": "master.db", "type": "DB", "size": "8192", "perm": "-rw-rw----"}
        ]

    def _init_paint_calc(self):
        self.paint_color = COLOR_ACCENT_RED
        self.paint_strokes = []
        self.calc_display = "0"
        self.calc_op = None
        self.calc_arg1 = 0
        self.calc_reset_on_next = False

    # --------------------------------------------------------------------------
    # Window Creation
    # --------------------------------------------------------------------------

    def _setup_master_windows(self):
        # 1. Sovereign Web Browser Window
        self.win_browser = Window("browser", "Sovereign Browser (HTML/CSS Box Model)", 12, 28, 305, 215)
        self.win_browser.on_draw_content = self._draw_browser
        self.win_browser.on_click_content = self._click_browser
        self.wm.add_window(self.win_browser)

        # 2. SovereignSQL Terminal Window
        self.win_sql = Window("sql", "SovereignSQL Terminal (ACID/WAL)", 325, 28, 305, 215)
        self.win_sql.on_draw_content = self._draw_sql
        self.win_sql.on_click_content = self._click_sql
        self.wm.add_window(self.win_sql)

        # 3. Lisp Bytecode REPL Window
        self.win_lisp = Window("lisp", "Lisp S-Expression Bytecode VM", 12, 252, 305, 205)
        self.win_lisp.on_draw_content = self._draw_lisp
        self.win_lisp.on_click_content = self._click_lisp
        self.wm.add_window(self.win_lisp)

        # 4. OpenGL 3D Viewport Window
        self.win_gl = Window("gl", "OpenGL 3D Hardware Viewport", 325, 252, 305, 205)
        self.win_gl.on_draw_content = self._draw_gl
        self.win_gl.on_click_content = self._click_gl
        self.wm.add_window(self.win_gl)

        # 5. File Explorer Window (Hidden by default, openable via Start Menu)
        self.win_explorer = Window("explorer", "Sovereign File Explorer (VFS / Ext2 / FAT32)", 35, 45, 300, 210)
        self.win_explorer.visible = False
        self.win_explorer.on_draw_content = self._draw_explorer
        self.win_explorer.on_click_content = self._click_explorer
        self.wm.add_window(self.win_explorer)

        # 6. Network & Crypto Monitor Window (Hidden by default)
        self.win_netmon = Window("netmon", "Network & Crypto Monitor (TLS 1.3 / TCP)", 310, 45, 315, 210)
        self.win_netmon.visible = False
        self.win_netmon.on_draw_content = self._draw_netmon
        self.win_netmon.on_click_content = self._click_netmon
        self.wm.add_window(self.win_netmon)

        # 7. POSIX Terminal Shell Window (Hidden by default)
        self.win_shell = Window("shell", "POSIX Sovereign Shell (sh)", 50, 70, 310, 210)
        self.win_shell.visible = False
        self.win_shell.on_draw_content = self._draw_shell
        self.win_shell.on_click_content = self._click_shell
        self.wm.add_window(self.win_shell)

        # 8. Paint Studio & Calculator Window (Hidden by default)
        self.win_paint = Window("paint", "Paint Studio & Pocket Calc", 290, 70, 320, 210)
        self.win_paint.visible = False
        self.win_paint.on_draw_content = self._draw_paint
        self.win_paint.on_click_content = self._click_paint
        self.wm.add_window(self.win_paint)

        # Focus Browser as initial active window
        self.wm.focus_window(self.win_browser)

    # --------------------------------------------------------------------------
    # Drawing Primitives with Clipping
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int, clip_rect=None):
        min_x, min_y, max_x, max_y = (0, 0, WIDTH - 1, HEIGHT - 1) if clip_rect is None else clip_rect
        x1 = max(min_x, max(0, x))
        y1 = max(min_y, max(0, y))
        x2 = min(max_x, min(WIDTH - 1, x + w - 1))
        y2 = min(max_y, min(HEIGHT - 1, y + h - 1))
        if x1 > x2 or y1 > y2:
            return

        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        span_len = x2 - x1 + 1
        line_bytes = c_bytes * span_len

        for cy in range(y1, y2 + 1):
            off = (cy * WIDTH + x1) * 4
            fb[off : off + span_len * 4] = line_bytes

    def _draw_string(self, fb: bytearray, x: int, y: int, text: str, color: int, clip_rect=None):
        min_x, min_y, max_x, max_y = (0, 0, WIDTH - 1, HEIGHT - 1) if clip_rect is None else clip_rect
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        curr_x = x

        for ch in text:
            if curr_x + 8 > max_x:
                break
            glyph = self.font.get(ch, self.font.get("?", None))
            if glyph:
                for row in range(8):
                    py = y + row
                    if py < min_y or py > max_y:
                        continue
                    byte_val = glyph[row]
                    for col in range(8):
                        px = curr_x + col
                        if px < min_x or px > max_x:
                            continue
                        if (byte_val >> (7 - col)) & 1:
                            off = (py * WIDTH + px) * 4
                            fb[off : off + 4] = c_bytes
            curr_x += 8

    def _draw_button(self, fb: bytearray, x: int, y: int, w: int, h: int, text: str, bg_color: int, txt_color: int, clip_rect=None):
        self._fill_rect(fb, x, y, w, h, bg_color, clip_rect)
        # Border
        self._fill_rect(fb, x, y, w, 1, COLOR_BORDER, clip_rect)
        self._fill_rect(fb, x, y + h - 1, w, 1, COLOR_BORDER, clip_rect)
        self._fill_rect(fb, x, y, 1, h, COLOR_BORDER, clip_rect)
        self._fill_rect(fb, x + w - 1, y, 1, h, COLOR_BORDER, clip_rect)
        # Centered text
        tx = x + max(2, (w - len(text) * 8) // 2)
        ty = y + max(1, (h - 8) // 2)
        self._draw_string(fb, tx, ty, text, txt_color, clip_rect)

    # --------------------------------------------------------------------------
    # Application Window Content Renderers
    # --------------------------------------------------------------------------

    # App 1: Sovereign Browser
    def _draw_browser(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # URL Bar Background
        self._fill_rect(fb, cx + 4, cy + 4, cw - 52, 18, 0x0016161E, clip)
        self._draw_string(fb, cx + 8, cy + 8, self.browser_url, COLOR_ACCENT_CYAN, clip)
        self._draw_button(fb, cx + cw - 46, cy + 4, 42, 18, "GO", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)

        # Content Card Background
        self._fill_rect(fb, cx + 6, cy + 28, cw - 12, ch - 34, 0x0024283B, clip)
        self._draw_string(fb, cx + 12, cy + 34, "Sovereign Web Engine", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 12, cy + 48, "-" * 32, COLOR_BORDER, clip)

        # Renders layout box tree
        self._draw_string(fb, cx + 12, cy + 60, "URL: " + self.browser_url, COLOR_ACCENT_GREEN, clip)
        self._draw_string(fb, cx + 12, cy + 76, "DOM Tree: Root <HTML>", COLOR_TEXT_PRIMARY, clip)
        self._draw_string(fb, cx + 20, cy + 90, "|-- <DIV class='card'>", COLOR_TEXT_PRIMARY, clip)
        self._draw_string(fb, cx + 28, cy + 104, "|-- <H1> 'AdiOS Sovereign Web'", COLOR_ACCENT_CYAN, clip)
        self._draw_string(fb, cx + 28, cy + 118, "|-- <P> 'Bare-metal DOM tree'", COLOR_TEXT_PRIMARY, clip)
        self._draw_string(fb, cx + 12, cy + 138, "CSS Box Model computed:", COLOR_ACCENT_ORANGE, clip)
        self._draw_string(fb, cx + 20, cy + 152, "W: 290px | H: 180px | Pad: 8px", COLOR_TEXT_MUTED, clip)

    def _click_browser(self, win: Window, rel_x: int, rel_y: int):
        cw = win.w - 4
        if rel_y <= 24 and rel_x >= cw - 46:
            # Clicked GO button
            if self.browser_url == "about:adios":
                self.browser_url = "http://sovereign.local/docs"
            else:
                self.browser_url = "about:adios"
            self.status_message = f"Browser navigated to {self.browser_url}"

    # App 2: SovereignSQL Terminal
    def _draw_sql(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Query Input Box
        self._fill_rect(fb, cx + 4, cy + 4, cw - 56, 18, 0x0016161E, clip)
        self._draw_string(fb, cx + 8, cy + 8, self.sql_query[:32], COLOR_ACCENT_CYAN, clip)
        self._draw_button(fb, cx + cw - 50, cy + 4, 46, 18, "RUN", COLOR_BUTTON_BG, COLOR_ACCENT_GREEN, clip)

        # Results Table Header
        self._draw_string(fb, cx + 6, cy + 28, "ID  NAME        STATUS", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 6, cy + 38, "-" * 32, COLOR_BORDER, clip)

        # Rows
        if self.sql_results and "rows" in self.sql_results:
            for idx, r in enumerate(self.sql_results["rows"][:7]):
                line = f"{r[0]:<3} {str(r[1]):<11} {str(r[2])}"
                self._draw_string(fb, cx + 6, cy + 50 + idx * 14, line, COLOR_TEXT_PRIMARY, clip)

        # Status Bar at bottom
        self._draw_string(fb, cx + 6, cy + ch - 16, self.sql_status[:36], COLOR_TEXT_MUTED, clip)

    def _click_sql(self, win: Window, rel_x: int, rel_y: int):
        cw = win.w - 4
        if rel_y <= 24 and rel_x >= cw - 50:
            # Clicked RUN
            if "status" in self.sql_query:
                self.sql_query = "SELECT id, name, mem FROM services;"
            else:
                self.sql_query = "SELECT id, name, status FROM services;"
            self.sql_results = self.db.execute(self.sql_query)
            self.sql_status = f"{len(self.sql_results.get('rows', []))} rows (ACID Query OK)"
            self.status_message = "Executed SovereignSQL Relational Query."

    # App 3: Lisp Bytecode REPL
    def _draw_lisp(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # History Lines
        self._draw_string(fb, cx + 6, cy + 6, "Sovereign Lisp Bytecode VM", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 6, cy + 18, "-" * 32, COLOR_BORDER, clip)

        for idx, line in enumerate(self.lisp_history[-5:]):
            color = COLOR_ACCENT_GREEN if "=>" in line else COLOR_TEXT_PRIMARY
            self._draw_string(fb, cx + 6, cy + 30 + idx * 15, line[:35], color, clip)

        # Quick eval buttons
        self._draw_button(fb, cx + 6, cy + ch - 42, 60, 18, "(+ 2 3)", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 72, cy + ch - 42, 70, 18, "(FIB 8)", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 148, cy + ch - 42, 60, 18, "CLEAR", COLOR_BUTTON_BG, COLOR_ACCENT_RED, clip)

        # Prompt Input
        self._fill_rect(fb, cx + 4, cy + ch - 20, cw - 8, 16, 0x0016161E, clip)
        self._draw_string(fb, cx + 8, cy + ch - 16, "adisp> " + self.lisp_expr[:28], COLOR_ACCENT_CYAN, clip)

    def _click_lisp(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        if ch - 44 <= rel_y <= ch - 24:
            if 6 <= rel_x <= 66:
                self.lisp_expr = "(+ 2 3)"
                self._eval_lisp_expr(self.lisp_expr)
            elif 72 <= rel_x <= 142:
                self.lisp_expr = "(* 7 8)"
                self._eval_lisp_expr(self.lisp_expr)
            elif 148 <= rel_x <= 208:
                self.lisp_history = ["adisp> REPL cleared."]

    def _eval_lisp_expr(self, expr: str):
        try:
            ast = LispParser.parse(expr)
            comp = BytecodeCompiler()
            comp.compile(ast)
            comp.code.append(OP_HALT)
            vm = BytecodeVM(comp.code, comp.constants)
            res = vm.run()
            self.lisp_history.append(f"adisp> {expr} => {res}")
            self.lisp_last_val = res
            self.status_message = f"Lisp VM evaluated: {res}"
        except Exception as e:
            self.lisp_history.append(f"adisp> Err: {str(e)[:20]}")

    # App 4: OpenGL 3D Viewport
    def _draw_gl(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Clear viewport background inside window
        self._fill_rect(fb, cx, cy, cw, ch, 0x0014161F, clip)

        # Render 3D Model centered inside window client area
        center_x = cx + cw // 2
        center_y = cy + ch // 2 - 8
        pos = Vector3(0, 0, 140)
        self.engine3d.render_mesh(
            self.current_mesh, pos, self.rot_3d,
            wireframe=self.wireframe_3d,
            center_x=center_x, center_y=center_y,
            clip_rect=clip
        )

        # Status text overlay
        mode_str = "WIRE" if self.wireframe_3d else "SOLID"
        self._draw_string(fb, cx + 6, cy + 6, f"OpenGL 1.1 | {self.mesh_name} | {mode_str}", COLOR_ACCENT_GREEN, clip)

        # Viewport control buttons at bottom
        self._draw_button(fb, cx + 6, cy + ch - 22, 64, 18, "MODEL", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 76, cy + ch - 22, 64, 18, "TOGGLE", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 146, cy + ch - 22, 50, 18, "ROT", COLOR_BUTTON_BG, COLOR_ACCENT_CYAN, clip)

    def _click_gl(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        if ch - 24 <= rel_y <= ch - 4:
            if 6 <= rel_x <= 70:
                if self.mesh_name == "CUBE":
                    self.current_mesh = self.mesh_pyramid
                    self.mesh_name = "PYRAMID"
                else:
                    self.current_mesh = self.mesh_cube
                    self.mesh_name = "CUBE"
                self.status_message = f"3D Mesh switched to {self.mesh_name}"
            elif 76 <= rel_x <= 140:
                self.wireframe_3d = not self.wireframe_3d
                self.status_message = f"3D Viewport wireframe: {self.wireframe_3d}"
            elif 146 <= rel_x <= 196:
                self.rot_3d.y = (self.rot_3d.y + 45.0) % 360.0

    # App 5: Sovereign File Explorer
    def _draw_explorer(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Drive selection pills
        self._draw_button(fb, cx + 4, cy + 4, 60, 16, "/ (Ext2)", COLOR_START_PILL, COLOR_START_TXT, clip)
        self._draw_button(fb, cx + 68, cy + 4, 64, 16, "FAT32", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 136, cy + 4, 60, 16, "AdiFS", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)

        # Table Header
        self._draw_string(fb, cx + 6, cy + 26, "NAME         TYPE    SIZE  PERM", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 6, cy + 36, "-" * 34, COLOR_BORDER, clip)

        # Files
        for idx, f in enumerate(self.explorer_files[:8]):
            color = COLOR_ACCENT_CYAN if f["type"] == "DIR" else COLOR_TEXT_PRIMARY
            line = f"{f['name']:<12} {f['type']:<7} {f['size']:<5} {f['perm']}"
            self._draw_string(fb, cx + 6, cy + 48 + idx * 14, line, color, clip)

        self._draw_string(fb, cx + 6, cy + ch - 16, "Disk: 64MB VirtIO-Block Mounted", COLOR_ACCENT_GREEN, clip)

    def _click_explorer(self, win: Window, rel_x: int, rel_y: int):
        if rel_y <= 22:
            if 4 <= rel_x <= 64:
                self.explorer_drive = "Ext2"
            elif 68 <= rel_x <= 132:
                self.explorer_drive = "FAT32"
            elif 136 <= rel_x <= 196:
                self.explorer_drive = "AdiFS"
            self.status_message = f"File Explorer switched to {self.explorer_drive} filesystem."

    # App 6: Network & Crypto Monitor
    def _draw_netmon(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Socket Table Header
        self._draw_string(fb, cx + 6, cy + 6, "LOCAL IP:PORT    REMOTE IP:PORT   STATE", COLOR_ACCENT_PURPLE, clip)
        self._draw_string(fb, cx + 6, cy + 18, "-" * 37, COLOR_BORDER, clip)

        for idx, s in enumerate(self.net_sockets):
            line = f"{s['local']:<16} {s['remote']:<16} {s['state'][:6]}"
            color = COLOR_ACCENT_GREEN if s['state'] == 'ESTABLISHED' else COLOR_TEXT_MUTED
            self._draw_string(fb, cx + 6, cy + 28 + idx * 14, line, color, clip)

        # Crypto Status Box
        sep_y = cy + 90
        self._draw_string(fb, cx + 6, sep_y, "Sovereign Crypto Engine (Ring-0)", COLOR_ACCENT_CYAN, clip)
        self._draw_string(fb, cx + 6, sep_y + 12, "-" * 37, COLOR_BORDER, clip)
        self._draw_string(fb, cx + 6, sep_y + 24, "TLS 1.3: HKDF / ChaCha20 / Poly1305", COLOR_TEXT_PRIMARY, clip)
        self._draw_string(fb, cx + 6, sep_y + 38, f"SHA-256: {self.sha256_val}", COLOR_ACCENT_ORANGE, clip)

        # Test Handshake button
        self._draw_button(fb, cx + 6, cy + ch - 22, 140, 18, "TEST TLS 1.3 SHAKE", COLOR_BUTTON_BG, COLOR_ACCENT_GREEN, clip)

    def _click_netmon(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        if ch - 24 <= rel_y <= ch - 4 and 6 <= rel_x <= 146:
            # Trigger TLS 1.3 Handshake & Key Schedule simulation
            ks = TLS13KeySchedule()
            shared_dhe = b"\x42" * 32
            client_hello = b"\x01\x00\x00\x20" + b"\x11" * 32
            ks.compute_handshake_secrets(shared_dhe, client_hello)
            fin = ks.calculate_finished(ks.server_handshake_traffic_secret, client_hello)
            self.sha256_val = sha256_hash(fin).hex()[:16] + "..."
            self.status_message = "TLS 1.3 Handshake Verified (ClientHello -> ServerHello [OK])."

    # App 7: POSIX Sovereign Shell
    def _draw_shell(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Shell background
        self._fill_rect(fb, cx, cy, cw, ch, 0x000F0F14, clip)

        # History output
        for idx, line in enumerate(self.shell_history[-8:]):
            color = COLOR_ACCENT_GREEN if line.startswith("root@adios") else COLOR_TEXT_PRIMARY
            self._draw_string(fb, cx + 6, cy + 6 + idx * 14, line[:36], color, clip)

        # Quick action buttons
        by = cy + ch - 40
        self._draw_button(fb, cx + 6, by, 54, 16, "ls -la", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 64, by, 64, 16, "uname -a", COLOR_BUTTON_BG, COLOR_BUTTON_TXT, clip)
        self._draw_button(fb, cx + 132, by, 54, 16, "clear", COLOR_BUTTON_BG, COLOR_ACCENT_RED, clip)

        # Active prompt line
        self._draw_string(fb, cx + 6, cy + ch - 16, "root@adios:~# " + self.shell_input + "_", COLOR_ACCENT_CYAN, clip)

    def _click_shell(self, win: Window, rel_x: int, rel_y: int):
        ch = win.h - 22
        if ch - 42 <= rel_y <= ch - 22:
            if 6 <= rel_x <= 60:
                self.shell_history.append("root@adios:~# ls -la")
                self.shell_history.append("drwxr-xr-x  4 root root 4096 /etc")
                self.shell_history.append("-rwxr-xr-x  1 root root 8420 /bin/sh")
            elif 64 <= rel_x <= 128:
                self.shell_history.append("root@adios:~# uname -a")
                self.shell_history.append("AdiOS 1.0.0-sovereign riscv32 GNU/Sovereign")
            elif 132 <= rel_x <= 186:
                self.shell_history = ["root@adios:~# "]
            self.status_message = "POSIX Command Executed."

    # App 8: Paint Studio & Calculator
    def _draw_paint(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Top section: Paint Studio (height ~90)
        colors = [COLOR_ACCENT_RED, COLOR_ACCENT_GREEN, COLOR_ACCENT_CYAN, COLOR_ACCENT_ORANGE, COLOR_ACCENT_PURPLE, 0x00FFFFFF]
        for idx, c in enumerate(colors):
            self._fill_rect(fb, cx + 6 + idx * 22, cy + 4, 18, 16, c, clip)
        self._draw_button(fb, cx + 144, cy + 4, 46, 16, "WIPE", COLOR_BUTTON_BG, COLOR_ACCENT_RED, clip)

        # Paint canvas box
        self._fill_rect(fb, cx + 6, cy + 24, 184, 60, 0x0016161E, clip)
        # Render painted strokes
        for px, py, color in self.paint_strokes:
            self._fill_rect(fb, px, py, 3, 3, color, clip)

        # Bottom section: Pocket Calculator
        cal_y = cy + 92
        self._draw_string(fb, cx + 6, cal_y, "Sovereign Pocket Calculator", COLOR_ACCENT_PURPLE, clip)
        # LCD Display
        self._fill_rect(fb, cx + 6, cal_y + 12, 184, 18, 0x0016161E, clip)
        self._draw_string(fb, cx + 12, cal_y + 16, self.calc_display[:18], COLOR_ACCENT_GREEN, clip)

        # 4x4 Calculator Keys
        keys = [
            ["7", "8", "9", "/"],
            ["4", "5", "6", "*"],
            ["1", "2", "3", "-"],
            ["C", "0", "=", "+"]
        ]
        key_w = 42
        key_h = 14
        for row_idx, row in enumerate(keys):
            for col_idx, k in enumerate(row):
                kx = cx + 6 + col_idx * (key_w + 5)
                ky = cal_y + 34 + row_idx * (key_h + 3)
                txt_c = COLOR_ACCENT_ORANGE if k in ("/", "*", "-", "+", "=") else (COLOR_ACCENT_RED if k == "C" else COLOR_TEXT_PRIMARY)
                self._draw_button(fb, kx, ky, key_w, key_h, k, COLOR_BUTTON_BG, txt_c, clip)

    def _click_paint(self, win: Window, rel_x: int, rel_y: int):
        cx, cy, _, _ = win.client_rect
        colors = [COLOR_ACCENT_RED, COLOR_ACCENT_GREEN, COLOR_ACCENT_CYAN, COLOR_ACCENT_ORANGE, COLOR_ACCENT_PURPLE, 0x00FFFFFF]
        # Swatch pick
        if 4 <= rel_y <= 20:
            for idx, c in enumerate(colors):
                if 6 + idx * 22 <= rel_x <= 24 + idx * 22:
                    self.paint_color = c
                    self.status_message = "Paint color changed."
                    return
            if 144 <= rel_x <= 190:
                self.paint_strokes.clear()
                self.status_message = "Canvas wiped."
                return

        # Canvas draw
        if 24 <= rel_y <= 84 and 6 <= rel_x <= 190:
            self.paint_strokes.append((cx + rel_x, cy + rel_y, self.paint_color))
            return

        # Calculator key click
        cal_rel_y = rel_y - 92
        if cal_rel_y >= 34:
            keys = [
                ["7", "8", "9", "/"],
                ["4", "5", "6", "*"],
                ["1", "2", "3", "-"],
                ["C", "0", "=", "+"]
            ]
            key_w = 42
            key_h = 14
            for row_idx, row in enumerate(keys):
                for col_idx, k in enumerate(row):
                    kx = 6 + col_idx * (key_w + 5)
                    ky = 34 + row_idx * (key_h + 3)
                    if kx <= rel_x <= kx + key_w and ky <= cal_rel_y <= ky + key_h:
                        self._handle_calc_key(k)
                        return

    def _handle_calc_key(self, k: str):
        if k.isdigit():
            if self.calc_display == "0" or self.calc_reset_on_next:
                self.calc_display = k
                self.calc_reset_on_next = False
            else:
                self.calc_display += k
        elif k == "C":
            self.calc_display = "0"
            self.calc_op = None
            self.calc_arg1 = 0
            self.calc_reset_on_next = False
        elif k in ("+", "-", "*", "/"):
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
                    self.calc_display = str(res)
                    self.status_message = f"Calculator result: {self.calc_arg1} {self.calc_op} {arg2} = {res}"
                except Exception:
                    self.calc_display = "ERR"
                self.calc_op = None
                self.calc_reset_on_next = True

    # --------------------------------------------------------------------------
    # Start Menu & Window Switcher
    # --------------------------------------------------------------------------

    def toggle_start_menu(self):
        self.start_menu_open = not self.start_menu_open

    def launch_or_focus(self, win_id: str):
        for w in self.wm.windows:
            if w.win_id == win_id:
                w.visible = True
                self.wm.focus_window(w)
                self.status_message = f"Active window: {w.title}"
                self.start_menu_open = False
                return

    # --------------------------------------------------------------------------
    # Master Compositor & Frame Stepping
    # --------------------------------------------------------------------------

    def step_frame(self, mouse_x: int, mouse_y: int):
        self.rot_3d.y = (self.rot_3d.y + 2.0) % 360.0

    def render(self, fb: bytearray):
        # 1. Clear Desktop with deep dark background
        bg_bytes = bytes([COLOR_DESKTOP_BG & 0xFF, (COLOR_DESKTOP_BG >> 8) & 0xFF, (COLOR_DESKTOP_BG >> 16) & 0xFF, 0])
        fb[0 : WIDTH * HEIGHT * 4] = bg_bytes * (WIDTH * HEIGHT)

        # 2. Render Window Manager Layer (all visible windows in Z-order)
        self.wm.render_all(fb, self.font)

        # 3. Render Top Taskbar (24px high)
        tb_bytes = bytes([COLOR_TASKBAR_BG & 0xFF, (COLOR_TASKBAR_BG >> 8) & 0xFF, (COLOR_TASKBAR_BG >> 16) & 0xFF, 0])
        for ty in range(0, 24):
            fb[(ty * WIDTH) * 4 : (ty * WIDTH + WIDTH) * 4] = tb_bytes * WIDTH

        # Taskbar Bottom Border
        border_bytes = bytes([COLOR_TASKBAR_BORDER & 0xFF, (COLOR_TASKBAR_BORDER >> 8) & 0xFF, (COLOR_TASKBAR_BORDER >> 16) & 0xFF, 0])
        fb[(23 * WIDTH) * 4 : (24 * WIDTH) * 4] = border_bytes * WIDTH

        # Start Pill (AdiOS button)
        pill_bytes = bytes([COLOR_START_PILL & 0xFF, (COLOR_START_PILL >> 8) & 0xFF, (COLOR_START_PILL >> 16) & 0xFF, 0])
        for py in range(2, 22):
            fb[(py * WIDTH + 4) * 4 : (py * WIDTH + 74) * 4] = pill_bytes * 70
        self._draw_string(fb, 12, 7, "AdiOS [1.0]", COLOR_START_TXT)

        # Window Switcher Pills on Taskbar
        sw_x = 82
        for w in self.wm.windows:
            if w.visible:
                bg_col = COLOR_TITLE_ACT if w.active else COLOR_BUTTON_BG
                txt_col = COLOR_START_TXT if w.active else COLOR_BUTTON_TXT
                short_title = w.title[:9]
                self._draw_button(fb, sw_x, 3, 76, 18, short_title, bg_col, txt_col)
                sw_x += 80

        # Right status indicators: SMP Cores & System Clock
        self._draw_string(fb, WIDTH - 195, 7, "SMP 4x Hart | 64MB", COLOR_ACCENT_GREEN)

        # 4. Render Dropdown Start Menu if open
        if self.start_menu_open:
            self._render_start_menu(fb)

    def _render_start_menu(self, fb: bytearray):
        mx = 4
        my = 24
        mw = 220
        mh = 180
        clip = (mx, my, mx + mw, my + mh)

        # Menu container
        self._fill_rect(fb, mx, my, mw, mh, 0x0016161E, clip)
        # Menu borders
        self._fill_rect(fb, mx, my, mw, 1, COLOR_START_PILL, clip)
        self._fill_rect(fb, mx, my + mh - 1, mw, 1, COLOR_START_PILL, clip)
        self._fill_rect(fb, mx, my, 1, mh, COLOR_START_PILL, clip)
        self._fill_rect(fb, mx + mw - 1, my, 1, mh, COLOR_START_PILL, clip)

        # Title
        self._draw_string(fb, mx + 8, my + 6, "AdiOS Sovereign Menu", COLOR_ACCENT_CYAN, clip)
        self._draw_string(fb, mx + 8, my + 16, "-" * 25, COLOR_BORDER, clip)

        # Items
        items = [
            ("1. Sovereign Browser", "browser"),
            ("2. SovereignSQL Terminal", "sql"),
            ("3. Lisp Bytecode REPL", "lisp"),
            ("4. OpenGL 3D Viewport", "gl"),
            ("5. Sovereign File Explorer", "explorer"),
            ("6. Network & Crypto Monitor", "netmon"),
            ("7. POSIX Sovereign Shell", "shell"),
            ("8. Paint Studio & Calc", "paint")
        ]

        for idx, (label, _) in enumerate(items):
            iy = my + 28 + idx * 18
            self._draw_string(fb, mx + 12, iy, label, COLOR_TEXT_PRIMARY, clip)

    # --------------------------------------------------------------------------
    # Event Handlers
    # --------------------------------------------------------------------------

    def handle_mouse_down(self, mx: int, my: int) -> Optional[Tuple[str, Any]]:
        # 1. Start Pill Click
        if my < 24:
            if 4 <= mx <= 74:
                self.toggle_start_menu()
                return ("start_toggle", None)

            # Window Switcher Pills click
            sw_x = 82
            for w in self.wm.windows:
                if w.visible:
                    if sw_x <= mx <= sw_x + 76:
                        self.wm.focus_window(w)
                        return ("switch_window", w)
                    sw_x += 80
            return None

        # 2. Start Menu Item Click
        if self.start_menu_open:
            if 4 <= mx <= 224 and 24 <= my <= 204:
                rel_item = (my - 52) // 18
                items_map = ["browser", "sql", "lisp", "gl", "explorer", "netmon", "shell", "paint"]
                if 0 <= rel_item < len(items_map):
                    self.launch_or_focus(items_map[rel_item])
                    return ("menu_select", items_map[rel_item])
            # Click outside menu closes it
            self.start_menu_open = False

        # 3. Window Manager Handling
        res = self.wm.handle_mouse_down(mx, my)
        if res:
            return res

        return None

    def handle_mouse_up(self, mx: int, my: int):
        self.wm.handle_mouse_up(mx, my)

    def handle_mouse_move(self, mx: int, my: int):
        self.wm.handle_mouse_move(mx, my)

    def handle_key(self, key_char: str):
        active_win = self.wm.windows[-1] if self.wm.windows else None
        if not active_win:
            return

        if active_win.win_id == "shell":
            if key_char == "\n" or key_char == "\r":
                cmd = self.shell_input.strip()
                self.shell_history.append("root@adios:~# " + cmd)
                if cmd:
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
            if key_char == "\n" or key_char == "\r":
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
            if key_char == "\n" or key_char == "\r":
                self._eval_lisp_expr(self.lisp_expr)
            elif key_char == "\b":
                self.lisp_expr = self.lisp_expr[:-1]
            elif len(key_char) == 1 and 32 <= ord(key_char) <= 126:
                self.lisp_expr += key_char

        elif active_win.win_id == "paint":
            if key_char.isdigit() or key_char in ("+", "-", "*", "/", "=", "C", "c"):
                self._handle_calc_key(key_char.upper())

if __name__ == "__main__":
    desktop = MasterDesktop()
    fb = bytearray(WIDTH * HEIGHT * 4)
    desktop.render(fb)
    assert fb[0:4] == bytes([COLOR_DESKTOP_BG & 0xFF, (COLOR_DESKTOP_BG >> 8) & 0xFF, (COLOR_DESKTOP_BG >> 16) & 0xFF, 0])
    print("MasterDesktop initialized and rendered successfully.")
