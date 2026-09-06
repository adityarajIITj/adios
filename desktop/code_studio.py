#!/usr/bin/env python3
"""
AdiOS Sovereign Code Studio (desktop/code_studio.py)
A modern, tabbed in-OS developer studio featuring:
1. Code Editor: Multi-line text buffer, line numbers, cursor, syntax highlighting.
2. Output Terminal: Real-time stdout/stderr execution sandbox with timing telemetry.
3. Online Package Manager: Background asynchronous `pip install` with live logs.
4. Preloaded Templates: 3D geometry, chiptune sound, and benchmark algorithms.

Strict Zero Emoji Policy.
"""

import sys
import io
import time
import subprocess
import threading
import traceback
from typing import List, Tuple, Dict, Optional, Any

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from .theme import ThemeManager

# Studio Tab Identifiers
TAB_EDITOR = 0
TAB_OUTPUT = 1
TAB_PACKAGES = 2

# Preloaded Sovereign Templates
TEMPLATES = {
    "math3d": (
        "# 3D Spatial Geometry Matrix Projection\n"
        "import math\n\n"
        "def project_point(x, y, z, fov=256, viewer_dist=64):\n"
        "    factor = fov / (viewer_dist + z)\n"
        "    return int(x * factor + 320), int(-y * factor + 240)\n\n"
        "points = [(-10, -10, 10), (10, -10, 10), (10, 10, 10), (-10, 10, 10)]\n"
        "print('Projected 3D coordinates:')\n"
        "for i, p in enumerate(points):\n"
        "    sx, sy = project_point(*p)\n"
        "    print(f'  Vertex {i}: Screen({sx}, {sy})')\n"
    ),
    "benchmark": (
        "# Integer Sieve of Eratosthenes Benchmark\n"
        "import time\n\n"
        "def sieve(limit):\n"
        "    primes = [True] * limit\n"
        "    primes[0] = primes[1] = False\n"
        "    for i in range(2, int(limit**0.5) + 1):\n"
        "        if primes[i]:\n"
        "            for j in range(i*i, limit, i):\n"
        "                primes[j] = False\n"
        "    return [i for i, p in enumerate(primes) if p]\n\n"
        "t0 = time.perf_counter()\n"
        "count = len(sieve(100000))\n"
        "dt = (time.perf_counter() - t0) * 1000.0\n"
        "print(f'Primes found under 100,000: {count}')\n"
        "print(f'Elapsed execution time: {dt:.2f} ms')\n"
    ),
    "webrequest": (
        "# Online HTTP Request Test\n"
        "import urllib.request\n"
        "import json\n\n"
        "try:\n"
        "    url = 'https://httpbin.org/get'\n"
        "    print(f'Connecting to {url}...')\n"
        "    req = urllib.request.Request(url, headers={'User-Agent': 'AdiOS-Workstation'})\n"
        "    with urllib.request.urlopen(req, timeout=3) as resp:\n"
        "        data = json.loads(resp.read().decode('utf-8'))\n"
        "        print('Response Status: 200 OK')\n"
        "        print('Origin IP:', data.get('origin'))\n"
        "except Exception as e:\n"
        "    print('Network request error:', e)\n"
    )
}

class CodeStudio(Window):
    """
    Sovereign Code Studio Window.
    Integrates code editing, execution runner, and online package manager.
    """
    def __init__(self, win_id: str = "studio", x: int = 80, y: int = 50, w: int = 760, h: int = 540):
        super().__init__(
            win_id=win_id,
            title="AdiOS Code Studio",
            x=x,
            y=y,
            w=w,
            h=h,
            bg_color=0x00121820
        )
        self.active_tab: int = TAB_EDITOR
        
        # Editor Buffer
        self.lines: List[str] = TEMPLATES["math3d"].strip().split("\n")
        self.cursor_line: int = 0
        self.cursor_col: int = 0
        self.scroll_line: int = 0
        self.font_scale: int = 1
        
        # Execution State
        self.output_logs: List[str] = [
            "AdiOS Sovereign Python 3 Execution Environment Ready.",
            "Click [Run] or press Ctrl+Enter to execute buffer."
        ]
        self.is_running: bool = False
        self.last_exec_ms: float = 0.0
        
        # Package Manager State
        self.pkg_input: str = ""
        self.pkg_logs: List[str] = [
            "AdiOS Online Package Manager (pip bridge).",
            "Type a library name below and click [Install] to fetch from PyPI."
        ]
        self.is_installing: bool = False
        self.pkg_process: Optional[subprocess.Popen] = None
        self.packages_view_mode: str = "logs"  # "logs" or "installed"
        self.installed_packages: List[Tuple[str, str]] = []
        self.pkg_scroll_idx: int = 0
        self.refresh_installed_packages()
        
        # Register window content callbacks
        self.on_draw_content = self._render_content
        self.on_click_content = self._handle_click

    def _render_content(self, win: Window, fb: bytearray, font_dict: Dict):
        """Draws tabs, toolbar, and active tab content."""
        cx, cy, cw, ch = self.client_rect
        tm = ThemeManager.get_instance()
        pal = tm.palette

        # 1. Tab Bar Header
        self._render_tab_bar(fb, cx, cy, cw, 28, pal, font_dict)

        # 2. Main Content Area depending on active tab
        content_y = cy + 28
        content_h = ch - 28

        if self.active_tab == TAB_EDITOR:
            self._render_editor(fb, cx, content_y, cw, content_h, pal, font_dict)
        elif self.active_tab == TAB_OUTPUT:
            self._render_output(fb, cx, content_y, cw, content_h, pal, font_dict)
        elif self.active_tab == TAB_PACKAGES:
            self._render_packages(fb, cx, content_y, cw, content_h, pal, font_dict)

    def _render_tab_bar(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders modern minimalist segmented tab bar with action buttons."""
        # Tab bar background
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        self._draw_hline(fb, x, y + h - 1, w, pal.card_border)

        tabs = [("1: Editor", TAB_EDITOR), ("2: Terminal", TAB_OUTPUT), ("3: Packages (pip)", TAB_PACKAGES)]
        tab_x = x + 8
        for name, tab_id in tabs:
            is_active = (self.active_tab == tab_id)
            tab_w = len(name) * CHAR_WIDTH + 18
            
            if is_active:
                self._fill_rect(fb, tab_x, y + 3, tab_w, h - 4, pal.win_bg)
                self._draw_rect_outline(fb, tab_x, y + 3, tab_w, h - 4, pal.card_border)
                # Active indicator hairline
                self._draw_hline(fb, tab_x + 2, y + 3, tab_w - 4, pal.accent_primary)
                txt_col = pal.text_primary
            else:
                txt_col = pal.text_muted

            self._draw_text(fb, tab_x + 9, y + 8, name, txt_col, font_dict)
            tab_x += tab_w + 6

        # Action Buttons on right side: [Zoom], [Load Template], [Run]
        btn_run_x = x + w - 75
        self._fill_rect(fb, btn_run_x, y + 4, 65, h - 8, pal.accent_primary)
        self._draw_text(fb, btn_run_x + 12, y + 8, "[Run]", 0x000F172A if pal.name == "Arctic Minimal" else 0x00FFFFFF, font_dict)

        btn_t_x = btn_run_x - 125
        self._fill_rect(fb, btn_t_x, y + 4, 115, h - 8, pal.btn_bg)
        self._draw_rect_outline(fb, btn_t_x, y + 4, 115, h - 8, pal.btn_border)
        self._draw_text(fb, btn_t_x + 8, y + 8, "Load Template", pal.text_primary, font_dict)

        btn_z_x = btn_t_x - 70
        self._fill_rect(fb, btn_z_x, y + 4, 62, h - 8, pal.btn_bg)
        self._draw_rect_outline(fb, btn_z_x, y + 4, 62, h - 8, pal.btn_border)
        zoom_lbl = f"Zoom:{self.font_scale}x"
        self._draw_text(fb, btn_z_x + 6, y + 8, zoom_lbl, pal.text_muted, font_dict)

    def _render_editor(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders code editor with line number gutter, syntax tokenization, and bottom status bar."""
        status_bar_h = 20
        canvas_h = h - status_bar_h
        gutter_w = 44
        
        # Gutter background & hairline divider
        self._fill_rect(fb, x, y, gutter_w, canvas_h, pal.gutter_bg)
        self._draw_vline(fb, x + gutter_w, y, canvas_h, pal.card_border)

        # Editor code canvas
        code_x = x + gutter_w + 10
        code_w = w - gutter_w - 10
        self._fill_rect(fb, x + gutter_w + 1, y, code_w + 9, canvas_h, pal.win_bg)

        # Calculate visible lines based on scale
        line_h = 16 * self.font_scale
        visible_count = canvas_h // line_h

        for idx in range(visible_count):
            line_idx = self.scroll_line + idx
            if line_idx >= len(self.lines):
                break

            line_y = y + idx * line_h + 3
            
            # Line number
            num_str = f"{line_idx + 1:3d}"
            num_col = pal.text_highlight if line_idx == self.cursor_line else pal.text_muted
            self._draw_text(fb, x + 8, line_y, num_str, num_col, font_dict)

            # Active line subtle highlight
            if line_idx == self.cursor_line:
                self._fill_rect(fb, code_x - 4, line_y - 2, code_w, line_h, pal.btn_bg)

            # Render line tokens
            raw_line = self.lines[line_idx]
            self._render_highlighted_line(fb, code_x, line_y, raw_line, pal, font_dict)

        # Bottom Editor Status Bar
        sb_y = y + canvas_h
        self._fill_rect(fb, x, sb_y, w, status_bar_h, pal.gutter_bg)
        self._draw_hline(fb, x, sb_y, w, pal.card_border)
        stat_txt = f"Ln {self.cursor_line + 1}, Col {self.cursor_col + 1} | UTF-8 | Python 3 | {len(self.lines)} lines"
        self._draw_text(fb, x + 12, sb_y + 6, stat_txt, pal.text_muted, font_dict)

    def _render_highlighted_line(self, fb: bytearray, x: int, y: int, line: str, pal: Any, font_dict: Dict):
        """Tokenizes line and applies minimalist syntax coloring."""
        curr_x = x
        
        # Check comment
        if "#" in line:
            code_part, comment_part = line.split("#", 1)
            self._render_tokens(fb, curr_x, y, code_part, pal, font_dict)
            curr_x += len(code_part) * CHAR_WIDTH
            self._draw_text(fb, curr_x, y, "#" + comment_part, pal.text_muted, font_dict)
        else:
            self._render_tokens(fb, curr_x, y, line, pal, font_dict)

    def _render_tokens(self, fb: bytearray, x: int, y: int, text: str, pal: Any, font_dict: Dict):
        """Renders non-comment code tokens."""
        import re
        keywords = {"def", "class", "import", "from", "return", "if", "elif", "else", "for", "while", "in", "try", "except", "as"}
        builtins = {"print", "len", "range", "enumerate", "int", "float", "str", "list", "dict", "set"}
        
        tokens = re.findall(r'(\b\w+\b|\"[^\"]*\"|\'[^\']*\'|[^\w\s]|\s+)', text)
        curr_x = x
        for tok in tokens:
            if tok in keywords:
                col = pal.accent_primary
            elif tok in builtins:
                col = pal.text_highlight
            elif tok.isdigit():
                col = 0x00E0AF68 if pal.name != "Arctic Minimal" else 0x00B45309  # Subtle Amber
            elif (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
                col = 0x002EA043 if pal.name != "Arctic Minimal" else 0x0015803D  # Subtle Green
            else:
                col = pal.text_primary

            self._draw_text(fb, curr_x, y, tok, col, font_dict)
            curr_x += len(tok) * CHAR_WIDTH

    def _render_output(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders live terminal execution stdout/stderr logs."""
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        
        # Header bar
        self._fill_rect(fb, x, y, w, 22, pal.card_bg)
        self._draw_hline(fb, x, y + 21, w, pal.card_border)
        status_txt = f"Status: {'Running...' if self.is_running else f'Idle (Last run: {self.last_exec_ms:.1f} ms)'}"
        self._draw_text(fb, x + 10, y + 6, status_txt, pal.text_highlight, font_dict)

        # Clear output button
        btn_clr_x = x + w - 70
        self._fill_rect(fb, btn_clr_x, y + 2, 60, 18, pal.btn_bg)
        self._draw_rect_outline(fb, btn_clr_x, y + 2, 60, 18, pal.btn_border)
        self._draw_text(fb, btn_clr_x + 12, y + 6, "Clear", pal.text_primary, font_dict)

        # Draw log lines
        line_y = y + 28
        for log in self.output_logs[-28:]:
            col = pal.text_primary
            if log.startswith("Error") or "Traceback" in log or "Exception" in log:
                col = 0x00F87171  # Subtle red
            elif log.startswith(">>") or log.startswith("Status:"):
                col = pal.accent_primary
            self._draw_text(fb, x + 12, line_y, log[:w // CHAR_WIDTH - 3], col, font_dict)
            line_y += 15

    def refresh_installed_packages(self):
        """Scans installed Python distributions via importlib.metadata."""
        pkgs = []
        try:
            import importlib.metadata
            for dist in importlib.metadata.distributions():
                name = dist.metadata.get("Name") or dist.name
                ver = dist.version
                if name:
                    pkgs.append((name, ver))
        except Exception as e:
            pkgs.append(("error", str(e)))
        pkgs.sort(key=lambda p: p[0].lower())
        self.installed_packages = pkgs
        self.pkg_scroll_idx = 0

    def _render_packages(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders online package manager with live install input, logs, and installed package catalog."""
        self._fill_rect(fb, x, y, w, h, pal.win_bg)

        # Search/Input bar area
        input_bar_h = 36
        self._fill_rect(fb, x, y, w, input_bar_h, pal.gutter_bg)
        self._draw_hline(fb, x, y + input_bar_h - 1, w, pal.card_border)

        # Input box
        in_x, in_y, in_w, in_h = x + 12, y + 6, 190, 24
        self._fill_rect(fb, in_x, in_y, in_w, in_h, pal.win_bg)
        self._draw_rect_outline(fb, in_x, in_y, in_w, in_h, pal.accent_primary if self.is_installing else pal.card_border)
        display_in = self.pkg_input if self.pkg_input else "Type package name..."
        in_col = pal.text_primary if self.pkg_input else pal.text_muted
        self._draw_text(fb, in_x + 8, in_y + 7, display_in[:23], in_col, font_dict)

        # [Install] Button
        btn_inst_x = in_x + in_w + 6
        self._fill_rect(fb, btn_inst_x, in_y, 62, in_h, pal.accent_primary)
        self._draw_text(fb, btn_inst_x + 8, in_y + 7, "Install", 0x000F172A if pal.name == "Arctic Minimal" else 0x00FFFFFF, font_dict)

        # View Mode Switcher: [Logs] / [Installed]
        mode_x = btn_inst_x + 70
        is_logs = (self.packages_view_mode == "logs")
        self._fill_rect(fb, mode_x, in_y, 48, in_h, pal.accent_primary if is_logs else pal.btn_bg)
        self._draw_rect_outline(fb, mode_x, in_y, 48, in_h, pal.btn_border)
        self._draw_text(fb, mode_x + 8, in_y + 7, "Logs", 0x000F172A if (is_logs and pal.name == "Arctic Minimal") else (0x00FFFFFF if is_logs else pal.text_primary), font_dict)

        is_inst = (self.packages_view_mode == "installed")
        inst_label = f"Catalog ({len(self.installed_packages)})"
        inst_w = len(inst_label) * CHAR_WIDTH + 14
        self._fill_rect(fb, mode_x + 53, in_y, inst_w, in_h, pal.accent_primary if is_inst else pal.btn_bg)
        self._draw_rect_outline(fb, mode_x + 53, in_y, inst_w, in_h, pal.btn_border)
        self._draw_text(fb, mode_x + 60, in_y + 7, inst_label, 0x000F172A if (is_inst and pal.name == "Arctic Minimal") else (0x00FFFFFF if is_inst else pal.text_primary), font_dict)

        content_y = y + input_bar_h + 8
        content_h = h - input_bar_h - 16

        if is_logs:
            # Quick-Install Shortcuts
            qk_x = mode_x + 58 + inst_w
            self._draw_text(fb, qk_x, in_y + 7, "Quick:", pal.text_muted, font_dict)
            qk_x += 44
            for qp in ["cowsay", "requests"]:
                qw = len(qp) * CHAR_WIDTH + 10
                self._fill_rect(fb, qk_x, in_y, qw, in_h, pal.btn_bg)
                self._draw_rect_outline(fb, qk_x, in_y, qw, in_h, pal.btn_border)
                self._draw_text(fb, qk_x + 5, in_y + 7, qp, pal.text_primary, font_dict)
                qk_x += qw + 4

            # Package Log Console
            self._fill_rect(fb, x + 12, content_y, w - 24, content_h, pal.gutter_bg)
            self._draw_rect_outline(fb, x + 12, content_y, w - 24, content_h, pal.card_border)
            curr_log_y = content_y + 8
            for log in self.pkg_logs[-22:]:
                col = pal.accent_primary if "Successfully installed" in log else (0x00F87171 if "ERROR" in log else pal.text_primary)
                self._draw_text(fb, x + 20, curr_log_y, log[:(w - 40) // CHAR_WIDTH], col, font_dict)
                curr_log_y += 15
        else:
            # Installed Packages Table View
            self._fill_rect(fb, x + 12, content_y, w - 24, content_h, pal.gutter_bg)
            self._draw_rect_outline(fb, x + 12, content_y, w - 24, content_h, pal.card_border)

            # Table Header
            hdr_y = content_y + 6
            self._draw_text(fb, x + 24, hdr_y, "PACKAGE NAME", pal.text_muted, font_dict)
            self._draw_text(fb, x + 320, hdr_y, "INSTALLED VERSION", pal.text_muted, font_dict)

            # Up / Down Scroll Buttons
            btn_up_x = x + w - 75
            self._fill_rect(fb, btn_up_x, hdr_y - 2, 24, 18, pal.btn_bg)
            self._draw_rect_outline(fb, btn_up_x, hdr_y - 2, 24, 18, pal.btn_border)
            self._draw_text(fb, btn_up_x + 5, hdr_y + 1, "Up", pal.text_primary, font_dict)

            btn_dn_x = btn_up_x + 28
            self._fill_rect(fb, btn_dn_x, hdr_y - 2, 24, 18, pal.btn_bg)
            self._draw_rect_outline(fb, btn_dn_x, hdr_y - 2, 24, 18, pal.btn_border)
            self._draw_text(fb, btn_dn_x + 5, hdr_y + 1, "Dn", pal.text_primary, font_dict)

            self._draw_hline(fb, x + 14, hdr_y + 18, w - 28, pal.card_border)

            # Table Rows
            row_y = hdr_y + 24
            visible_rows = self.installed_packages[self.pkg_scroll_idx:self.pkg_scroll_idx + 18]
            for pname, pver in visible_rows:
                self._draw_text(fb, x + 24, row_y, str(pname)[:32], pal.text_primary, font_dict)
                self._draw_text(fb, x + 320, row_y, f"v{pver}"[:20], pal.accent_primary, font_dict)
                row_y += 16

            # Bottom Status Bar in Installed Table
            stat_y = content_y + content_h - 20
            self._draw_hline(fb, x + 14, stat_y - 4, w - 28, pal.card_border)
            info_str = f"Catalog: {len(self.installed_packages)} packages installed | Offset: {self.pkg_scroll_idx + 1}-{min(len(self.installed_packages), self.pkg_scroll_idx + 18)}"
            self._draw_text(fb, x + 24, stat_y, info_str, pal.text_muted, font_dict)

    def _handle_click(self, win: Window, rel_x: int, rel_y: int):
        """Handles user mouse clicks across tabs and actions."""
        # Check tab clicks
        if rel_y <= 28:
            if rel_x < 90:
                self.active_tab = TAB_EDITOR
            elif rel_x < 185:
                self.active_tab = TAB_OUTPUT
            elif rel_x < 330:
                self.active_tab = TAB_PACKAGES

            # Check [Run] button
            cw = self.client_rect[2]
            if rel_x >= cw - 75:
                self.run_code()
            elif cw - 190 <= rel_x < cw - 75:
                # Cycle template
                keys = list(TEMPLATES.keys())
                curr_idx = 0
                for i, k in enumerate(keys):
                    if self.lines == TEMPLATES[k].strip().split("\n"):
                        curr_idx = (i + 1) % len(keys)
                        break
                self.load_template(keys[curr_idx])
            elif cw - 265 <= rel_x < cw - 190:
                # Toggle Zoom
                self.font_scale = 2 if self.font_scale == 1 else 1
            return

        # Output tab clear button
        if self.active_tab == TAB_OUTPUT and 28 <= rel_y <= 50:
            cw = self.client_rect[2]
            if rel_x >= cw - 70:
                self.output_logs.clear()
                self.output_logs.append("Output logs cleared.")
            return

        # Packages tab clicks
        if self.active_tab == TAB_PACKAGES:
            if 28 <= rel_y <= 64:
                # Install button
                if 208 <= rel_x <= 270:
                    if self.pkg_input:
                        self.install_package(self.pkg_input.strip())
                    return
                # Logs mode button
                if 278 <= rel_x <= 326:
                    self.packages_view_mode = "logs"
                    return
                # Catalog mode button
                inst_w = len(f"Catalog ({len(self.installed_packages)})") * CHAR_WIDTH + 14
                if 331 <= rel_x <= 331 + inst_w:
                    self.packages_view_mode = "installed"
                    self.refresh_installed_packages()
                    return
                # Quick install shortcuts when in logs mode
                if self.packages_view_mode == "logs":
                    qk_x = 331 + inst_w + 50
                    if qk_x <= rel_x <= qk_x + 50:
                        self.install_package("cowsay")
                    elif qk_x + 54 <= rel_x <= qk_x + 115:
                        self.install_package("requests")
            elif self.packages_view_mode == "installed" and rel_y > 64:
                cw = self.client_rect[2]
                if cw - 75 <= rel_x <= cw - 51 and 68 <= rel_y <= 90:
                    self.pkg_scroll_idx = max(0, self.pkg_scroll_idx - 10)
                elif cw - 47 <= rel_x <= cw - 23 and 68 <= rel_y <= 90:
                    self.pkg_scroll_idx = min(max(0, len(self.installed_packages) - 18), self.pkg_scroll_idx + 10)

    def load_template(self, name: str):
        """Loads a pre-built code template into editor buffer."""
        if name in TEMPLATES:
            self.lines = TEMPLATES[name].strip().split("\n")
            self.cursor_line = 0
            self.scroll_line = 0
            self.active_tab = TAB_EDITOR

    def run_code(self):
        """Executes current editor code buffer in an isolated output sandbox."""
        self.active_tab = TAB_OUTPUT
        self.is_running = True
        self.output_logs.append(f">> Execution started at {time.strftime('%H:%M:%S')}")
        
        code_str = "\n".join(self.lines)
        
        def _exec_worker():
            t0 = time.perf_counter()
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            redirected_out = io.StringIO()
            redirected_err = io.StringIO()
            sys.stdout = redirected_out
            sys.stderr = redirected_err
            
            try:
                exec_globals = {"__name__": "__main__"}
                exec(code_str, exec_globals)
                out_val = redirected_out.getvalue()
                err_val = redirected_err.getvalue()
                if out_val:
                    for line in out_val.strip().split("\n"):
                        self.output_logs.append(line)
                if err_val:
                    for line in err_val.strip().split("\n"):
                        self.output_logs.append(f"STDERR: {line}")
            except Exception as e:
                err_lines = traceback.format_exc().strip().split("\n")
                for el in err_lines:
                    self.output_logs.append(el)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                self.last_exec_ms = (time.perf_counter() - t0) * 1000.0
                self.is_running = False
                self.output_logs.append(f">> Finished in {self.last_exec_ms:.2f} ms")

        threading.Thread(target=_exec_worker, daemon=True).start()

    def install_package(self, pkg_name: str):
        """Asynchronously runs pip install in a background thread with real-time log streaming."""
        if self.is_installing:
            return
        
        self.is_installing = True
        self.active_tab = TAB_PACKAGES
        self.pkg_logs.append(f"\n[pip] Starting installation of '{pkg_name}'...")

        def _pip_worker():
            cmd = [sys.executable, "-m", "pip", "install", pkg_name]
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                self.pkg_process = proc
                for line in iter(proc.stdout.readline, ''):
                    if line:
                        self.pkg_logs.append(line.rstrip())
                proc.stdout.close()
                proc.wait()
                if proc.returncode == 0:
                    self.pkg_logs.append(f"[pip] Successfully installed '{pkg_name}'. Ready to import!")
                    self.refresh_installed_packages()
                else:
                    self.pkg_logs.append(f"[pip] Installation failed with exit code {proc.returncode}")
            except Exception as e:
                self.pkg_logs.append(f"[pip] Execution error: {e}")
            finally:
                self.is_installing = False
                self.pkg_process = None

        threading.Thread(target=_pip_worker, daemon=True).start()

    # --------------------------------------------------------------------------
    # Framebuffer Rendering Primitives
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        for dy in range(h):
            py = y + dy
            if 0 <= py < HEIGHT:
                for dx in range(w):
                    px = x + dx
                    if 0 <= px < WIDTH:
                        fb[(py * WIDTH + px) * 4 : (py * WIDTH + px + 1) * 4] = c_bytes

    def _draw_hline(self, fb: bytearray, x: int, y: int, w: int, color: int):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        if 0 <= y < HEIGHT:
            for dx in range(w):
                px = x + dx
                if 0 <= px < WIDTH:
                    fb[(y * WIDTH + px) * 4 : (y * WIDTH + px + 1) * 4] = c_bytes

    def _draw_vline(self, fb: bytearray, x: int, y: int, h: int, color: int):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        if 0 <= x < WIDTH:
            for dy in range(h):
                py = y + dy
                if 0 <= py < HEIGHT:
                    fb[(py * WIDTH + x) * 4 : (py * WIDTH + x + 1) * 4] = c_bytes

    def _draw_rect_outline(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int):
        self._draw_hline(fb, x, y, w, color)
        self._draw_hline(fb, x, y + h - 1, w, color)
        self._draw_vline(fb, x, y, h, color)
        self._draw_vline(fb, x + w - 1, y, h, color)

    def _draw_text(self, fb: bytearray, x: int, y: int, text: str, color: int, font_dict: Dict):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        curr_x = x
        for ch in text:
            if curr_x + CHAR_WIDTH > WIDTH:
                break
            glyph = font_dict.get(ord(ch), font_dict.get(ch, None)) if font_dict else None
            if glyph:
                for row in range(CHAR_HEIGHT):
                    py = y + row
                    if 0 <= py < HEIGHT:
                        bits = glyph[row] if row < len(glyph) else 0
                        for col in range(CHAR_WIDTH):
                            px = curr_x + col
                            if 0 <= px < WIDTH and (bits & (1 << (7 - col))):
                                fb[(py * WIDTH + px) * 4 : (py * WIDTH + px + 1) * 4] = c_bytes
            curr_x += CHAR_WIDTH
