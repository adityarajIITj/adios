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
import os
import io
import time
import subprocess
import threading
import traceback
from typing import List, Tuple, Dict, Optional, Any

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from .theme import ThemeManager
from .clipboard import SovereignClipboard

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
        
        # Editor Buffer - clean, functional, and fully editable
        self.filepath: str = "storage/code/script.py"
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
        self.lines: List[str] = [
            "# AdiOS Sovereign Code Studio",
            "def main():",
            "    print('Hello from AdiOS Sovereign Workstation!')",
            "    for i in range(1, 6):",
            "        print(f'Step {i}: Ready to code.')",
            "",
            "main()"
        ]
        self.cursor_line: int = 6
        self.cursor_col: int = 6
        self.scroll_line: int = 0
        self.font_scale: int = 1

        # Undo / Redo & Selection State
        self.undo_stack: List[Tuple[List[str], int, int]] = []
        self.redo_stack: List[Tuple[List[str], int, int]] = []
        self.select_all_active: bool = False
        self.last_key_time: float = time.time()
        
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

        # Action Buttons on right side: [New], [Save], [Template], [Zoom], [Run]
        btn_run_x = x + w - 68
        self._fill_rect(fb, btn_run_x, y + 4, 60, h - 8, pal.accent_primary)
        self._draw_text(fb, btn_run_x + 10, y + 8, "[Run]", 0x000F172A if pal.name == "Arctic Minimal" else 0x00FFFFFF, font_dict)

        btn_z_x = btn_run_x - 56
        self._fill_rect(fb, btn_z_x, y + 4, 50, h - 8, pal.btn_bg)
        self._draw_rect_outline(fb, btn_z_x, y + 4, 50, h - 8, pal.btn_border)
        self._draw_text(fb, btn_z_x + 6, y + 8, f"Z:{self.font_scale}x", pal.text_muted, font_dict)

        btn_t_x = btn_z_x - 72
        self._fill_rect(fb, btn_t_x, y + 4, 66, h - 8, pal.btn_bg)
        self._draw_rect_outline(fb, btn_t_x, y + 4, 66, h - 8, pal.btn_border)
        self._draw_text(fb, btn_t_x + 6, y + 8, "Template", pal.text_primary, font_dict)

        btn_save_x = btn_t_x - 50
        self._fill_rect(fb, btn_save_x, y + 4, 44, h - 8, pal.btn_bg)
        self._draw_rect_outline(fb, btn_save_x, y + 4, 44, h - 8, pal.btn_border)
        self._draw_text(fb, btn_save_x + 8, y + 8, "Save", pal.text_primary, font_dict)

        btn_new_x = btn_save_x - 46
        self._fill_rect(fb, btn_new_x, y + 4, 40, h - 8, pal.btn_bg)
        self._draw_rect_outline(fb, btn_new_x, y + 4, 40, h - 8, pal.btn_border)
        self._draw_text(fb, btn_new_x + 8, y + 8, "New", pal.text_primary, font_dict)

    def _render_editor(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders code editor with line number gutter, syntax tokenization, cursor bar, and bottom status bar."""
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

            # Active line subtle highlight or selection highlight
            if self.select_all_active:
                sel_bg = 0x001E3A5F if pal.name != "Arctic Minimal" else 0x00C7D2FE
                self._fill_rect(fb, code_x - 4, line_y - 2, code_w, line_h, sel_bg)
            elif line_idx == self.cursor_line:
                self._fill_rect(fb, code_x - 4, line_y - 2, code_w, line_h, pal.btn_bg)

            # Render line tokens
            raw_line = self.lines[line_idx]
            self._render_highlighted_line(fb, code_x, line_y, raw_line, pal, font_dict)

            # Render active cursor bar (solid while typing, gentle blink when idle)
            is_typing = (time.time() - getattr(self, "last_key_time", 0) < 0.8)
            blink_on = is_typing or ((int(time.time() * 2.2) % 2) == 0)
            if not self.select_all_active and line_idx == self.cursor_line and self.active_tab == TAB_EDITOR and blink_on:
                cur_x = code_x + self.cursor_col * CHAR_WIDTH * self.font_scale
                if code_x <= cur_x <= x + w - 4:
                    self._fill_rect(fb, cur_x, line_y - 1, 2, line_h - 2, pal.accent_primary)

        # Bottom Editor Status Bar
        sb_y = y + canvas_h
        self._fill_rect(fb, x, sb_y, w, status_bar_h, pal.gutter_bg)
        self._draw_hline(fb, x, sb_y, w, pal.card_border)
        sel_tag = " | [ALL SELECTED]" if self.select_all_active else ""
        stat_txt = f"Ln {self.cursor_line + 1}, Col {self.cursor_col + 1} | UTF-8 | Python 3 | {len(self.lines)} lines{sel_tag}"
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
        """Renders non-comment code tokens with rich Python syntax classification."""
        import re
        keywords = {
            "def", "class", "import", "from", "return", "if", "elif", "else", "for", "while",
            "in", "is", "not", "and", "or", "try", "except", "finally", "with", "as", "pass",
            "break", "continue", "yield", "lambda", "global", "nonlocal", "async", "await"
        }
        builtins = {
            "print", "len", "range", "enumerate", "int", "float", "str", "list", "dict", "set",
            "bool", "tuple", "type", "open", "sum", "min", "max", "abs", "round", "zip", "map",
            "filter", "self", "True", "False", "None"
        }
        
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

            # Check action buttons on right side: [New], [Save], [Template], [Zoom], [Run]
            cw = self.client_rect[2]
            if cw - 68 <= rel_x <= cw - 8:
                self.run_code()
            elif cw - 124 <= rel_x <= cw - 74:
                self.font_scale = 2 if self.font_scale == 1 else 1
            elif cw - 196 <= rel_x <= cw - 130:
                # Cycle preloaded templates
                keys = list(TEMPLATES.keys())
                curr_idx = 0
                for i, k in enumerate(keys):
                    if self.lines == TEMPLATES[k].strip().split("\n"):
                        curr_idx = (i + 1) % len(keys)
                        break
                self.load_template(keys[curr_idx])
            elif cw - 246 <= rel_x <= cw - 202:
                self.save_buffer()
            elif cw - 292 <= rel_x <= cw - 252:
                self.new_buffer()
            return

        # Editor canvas click to position cursor
        if self.active_tab == TAB_EDITOR and rel_y > 28:
            self.select_all_active = False
            canvas_y = 28
            line_h = 16 * self.font_scale
            gutter_w = 44
            clicked_idx = self.scroll_line + (rel_y - canvas_y) // line_h
            if 0 <= clicked_idx < len(self.lines):
                self.cursor_line = clicked_idx
                code_x = gutter_w + 10
                if rel_x >= code_x:
                    col = (rel_x - code_x) // (CHAR_WIDTH * self.font_scale)
                    self.cursor_col = min(col, len(self.lines[self.cursor_line]))
                else:
                    self.cursor_col = 0
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

    def _push_undo(self):
        """Snapshots current buffer and cursor position into undo stack."""
        self.undo_stack.append(([l for l in self.lines], self.cursor_line, self.cursor_col))
        if len(self.undo_stack) > 64:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        """Reverts code buffer to previous snapshot."""
        if self.undo_stack:
            self.redo_stack.append(([l for l in self.lines], self.cursor_line, self.cursor_col))
            lines, cline, ccol = self.undo_stack.pop()
            self.lines = [l for l in lines]
            self.cursor_line = max(0, min(cline, len(self.lines) - 1))
            self.cursor_col = max(0, min(ccol, len(self.lines[self.cursor_line])))
            self.select_all_active = False
            self.output_logs.append(f">> Undo ({len(self.undo_stack)} actions remaining).")
            self._ensure_cursor_visible()

    def redo(self):
        """Restores previously undone code buffer snapshot."""
        if self.redo_stack:
            self.undo_stack.append(([l for l in self.lines], self.cursor_line, self.cursor_col))
            lines, cline, ccol = self.redo_stack.pop()
            self.lines = [l for l in lines]
            self.cursor_line = max(0, min(cline, len(self.lines) - 1))
            self.cursor_col = max(0, min(ccol, len(self.lines[self.cursor_line])))
            self.select_all_active = False
            self.output_logs.append(f">> Redo ({len(self.redo_stack)} actions remaining).")
            self._ensure_cursor_visible()

    def select_all(self):
        """Selects all lines in editor buffer."""
        self.select_all_active = True
        self.output_logs.append(f">> Selected all code ({sum(len(l) for l in self.lines)} chars).")

    def copy_selection(self):
        """Copies selection or active line to clipboard."""
        if self.select_all_active:
            text = "\n".join(self.lines)
        else:
            text = self.lines[self.cursor_line] if self.lines else ""
        SovereignClipboard.get_instance().set_text(text)
        self.output_logs.append(f">> Copied {len(text)} chars to clipboard.")

    def cut_selection(self):
        """Cuts selection or active line to clipboard."""
        self._push_undo()
        if self.select_all_active:
            text = "\n".join(self.lines)
            SovereignClipboard.get_instance().set_text(text)
            self.lines = [""]
            self.cursor_line = 0
            self.cursor_col = 0
            self.select_all_active = False
        else:
            text = self.lines[self.cursor_line] if self.lines else ""
            SovereignClipboard.get_instance().set_text(text)
            if len(self.lines) > 1:
                del self.lines[self.cursor_line]
                if self.cursor_line >= len(self.lines):
                    self.cursor_line = len(self.lines) - 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            else:
                self.lines = [""]
                self.cursor_col = 0
        self.output_logs.append(f">> Cut {len(text)} chars to clipboard.")
        self._ensure_cursor_visible()

    def paste_clipboard(self):
        """Pastes clipboard text into editor buffer."""
        clip_text = SovereignClipboard.get_instance().get_text()
        if not clip_text:
            return
        self._push_undo()
        paste_lines = clip_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if self.select_all_active:
            self.lines = paste_lines or [""]
            self.cursor_line = len(self.lines) - 1
            self.cursor_col = len(self.lines[-1])
            self.select_all_active = False
        else:
            line = self.lines[self.cursor_line]
            left = line[:self.cursor_col]
            right = line[self.cursor_col:]
            if len(paste_lines) == 1:
                self.lines[self.cursor_line] = left + paste_lines[0] + right
                self.cursor_col += len(paste_lines[0])
            else:
                self.lines[self.cursor_line] = left + paste_lines[0]
                for idx in range(1, len(paste_lines) - 1):
                    self.lines.insert(self.cursor_line + idx, paste_lines[idx])
                self.lines.insert(self.cursor_line + len(paste_lines) - 1, paste_lines[-1] + right)
                self.cursor_line += len(paste_lines) - 1
                self.cursor_col = len(paste_lines[-1])
        self.output_logs.append(f">> Pasted {len(clip_text)} chars.")
        self._ensure_cursor_visible()

    def _delete_word_backward(self):
        """Performs word-level backward deletion across whitespace and tokens."""
        if not self.lines:
            self.lines = [""]
            return
        line = self.lines[self.cursor_line]
        if self.cursor_col == 0:
            if self.cursor_line > 0:
                self._push_undo()
                prev_line = self.lines[self.cursor_line - 1]
                prev_len = len(prev_line)
                self.lines[self.cursor_line - 1] = prev_line + line
                del self.lines[self.cursor_line]
                self.cursor_line -= 1
                self.cursor_col = prev_len
                self._ensure_cursor_visible()
            return

        self._push_undo()
        left = line[:self.cursor_col]
        right = line[self.cursor_col:]

        i = len(left)
        while i > 0 and left[i - 1] in (' ', '\t'):
            i -= 1

        if i == 0:
            self.lines[self.cursor_line] = right
            self.cursor_col = 0
            self._ensure_cursor_visible()
            return

        def is_word_char(c: str) -> bool:
            return c.isalnum() or c == '_'

        is_word = is_word_char(left[i - 1])
        while i > 0 and left[i - 1] not in (' ', '\t') and (is_word_char(left[i - 1]) == is_word):
            i -= 1

        self.lines[self.cursor_line] = left[:i] + right
        self.cursor_col = i
        self._ensure_cursor_visible()

    def duplicate_line(self):
        """Duplicates current line directly below and shifts cursor down."""
        self._push_undo()
        self.lines.insert(self.cursor_line + 1, self.lines[self.cursor_line])
        self.cursor_line += 1
        self._ensure_cursor_visible()

    def toggle_comment(self):
        """Toggles Python line comment (# ) on active line."""
        self._push_undo()
        line = self.lines[self.cursor_line]
        stripped = line.lstrip(' ')
        indent = len(line) - len(stripped)
        if stripped.startswith('# '):
            self.lines[self.cursor_line] = line[:indent] + stripped[2:]
            self.cursor_col = max(indent, self.cursor_col - 2)
        elif stripped.startswith('#'):
            self.lines[self.cursor_line] = line[:indent] + stripped[1:]
            self.cursor_col = max(indent, self.cursor_col - 1)
        else:
            self.lines[self.cursor_line] = line[:indent] + '# ' + stripped
            self.cursor_col += 2
        self._ensure_cursor_visible()

    def unindent_line(self):
        """Removes up to 4 spaces of leading indentation from current line."""
        line = self.lines[self.cursor_line]
        spaces = 0
        while spaces < 4 and spaces < len(line) and line[spaces] == ' ':
            spaces += 1
        if spaces > 0:
            self._push_undo()
            self.lines[self.cursor_line] = line[spaces:]
            self.cursor_col = max(0, self.cursor_col - spaces)
            self._ensure_cursor_visible()

    def delete_forward(self):
        """Deletes character directly under cursor or merges next line."""
        if not self.lines:
            return
        line = self.lines[self.cursor_line]
        if self.cursor_col < len(line):
            self._push_undo()
            self.lines[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col + 1:]
        elif self.cursor_line < len(self.lines) - 1:
            self._push_undo()
            next_line = self.lines[self.cursor_line + 1]
            self.lines[self.cursor_line] = line + next_line
            del self.lines[self.cursor_line + 1]
        self._ensure_cursor_visible()

    def move_cursor_home(self):
        """Moves cursor to start of indentation or column 0."""
        line = self.lines[self.cursor_line]
        first_non_ws = len(line) - len(line.lstrip(' '))
        if self.cursor_col == first_non_ws:
            self.cursor_col = 0
        else:
            self.cursor_col = first_non_ws
        self._ensure_cursor_visible()

    def move_cursor_end(self):
        """Moves cursor to end of current line."""
        self.cursor_col = len(self.lines[self.cursor_line])
        self._ensure_cursor_visible()

    def page_up(self):
        """Scrolls cursor and view up by one page."""
        jump = 16
        self.cursor_line = max(0, self.cursor_line - jump)
        self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
        self._ensure_cursor_visible()

    def page_down(self):
        """Scrolls cursor and view down by one page."""
        jump = 16
        self.cursor_line = min(len(self.lines) - 1, self.cursor_line + jump)
        self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
        self._ensure_cursor_visible()

    def scroll_up(self, count: int = 3):
        """Smoothly scrolls editor buffer viewport upwards."""
        self.scroll_line = max(0, self.scroll_line - count)

    def scroll_down(self, count: int = 3):
        """Smoothly scrolls editor buffer viewport downwards."""
        max_scroll = max(0, len(self.lines) - 1)
        self.scroll_line = min(max_scroll, self.scroll_line + count)

    def new_buffer(self):
        """Clears buffer to a clean, empty script ready for coding."""
        self._push_undo()
        self.lines = ["# Sovereign Python Script", ""]
        self.cursor_line = 1
        self.cursor_col = 0
        self.scroll_line = 0
        self.select_all_active = False
        self.active_tab = TAB_EDITOR

    def save_buffer(self, path: Optional[str] = None):
        """Saves current code buffer to disk."""
        target = path or getattr(self, "filepath", "storage/code/script.py")
        try:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines))
            self.filepath = target
            self.output_logs.append(f">> Saved {len(self.lines)} lines to '{target}'.")
        except Exception as e:
            self.output_logs.append(f">> Save error: {e}")

    def open_buffer(self, path: str):
        """Loads a file from disk into the editor buffer."""
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._push_undo()
                self.lines = content.splitlines() or [""]
                self.filepath = path
                self.cursor_line = 0
                self.cursor_col = 0
                self.scroll_line = 0
                self.select_all_active = False
                self.active_tab = TAB_EDITOR
                self.output_logs.append(f">> Loaded '{path}' ({len(self.lines)} lines).")
        except Exception as e:
            self.output_logs.append(f">> Open error: {e}")

    def handle_key(self, key_char: str):
        """Processes keystrokes for direct in-buffer code editing, shortcuts, and terminal input."""
        self.last_key_time = time.time()

        if self.active_tab != TAB_EDITOR:
            if self.active_tab == TAB_PACKAGES:
                if key_char in ("\r", "\n"):
                    if self.pkg_input.strip():
                        self.install_package(self.pkg_input.strip())
                elif key_char in ("\b", "\x08"):
                    self.pkg_input = self.pkg_input[:-1]
                elif len(key_char) == 1 and ord(key_char) >= 32:
                    self.pkg_input += key_char
            return

        # Productivity Shortcuts
        if key_char in ("CTRL_A", "\x01"):
            self.select_all()
            return

        if key_char in ("CTRL_C", "\x03"):
            self.copy_selection()
            return

        if key_char in ("CTRL_X", "\x18"):
            self.cut_selection()
            return

        if key_char in ("CTRL_V", "\x16"):
            self.paste_clipboard()
            return

        if key_char in ("CTRL_Z", "\x1a"):
            self.undo()
            return

        if key_char in ("CTRL_Y", "\x19"):
            self.redo()
            return

        if key_char in ("CTRL_S", "\x13"):
            self.save_buffer()
            return

        if key_char in ("CTRL_D", "\x04"):
            self.duplicate_line()
            return

        if key_char in ("CTRL_SLASH", "\x1f"):
            self.toggle_comment()
            return

        if key_char in ("CTRL_BACKSPACE", "\x7f"):
            self._delete_word_backward()
            return

        if key_char == "CTRL_ENTER":
            self.run_code()
            return

        # Navigation & Editing Keys
        if key_char in ("DELETE", "\x1b[3~"):
            self.delete_forward()
            return

        if key_char in ("HOME", "\x1b[H", "\x1b[1~"):
            self.move_cursor_home()
            return

        if key_char in ("END", "\x1b[F", "\x1b[4~"):
            self.move_cursor_end()
            return

        if key_char in ("PAGE_UP", "\x1b[5~"):
            self.page_up()
            return

        if key_char in ("PAGE_DOWN", "\x1b[6~"):
            self.page_down()
            return

        if key_char == "SCROLL_UP":
            self.scroll_up(3)
            return

        if key_char == "SCROLL_DOWN":
            self.scroll_down(3)
            return

        if key_char == "SHIFT_TAB":
            self.unindent_line()
            return

        if not self.lines:
            self.lines = [""]

        self.cursor_line = max(0, min(len(self.lines) - 1, self.cursor_line))
        self.cursor_col = max(0, min(len(self.lines[self.cursor_line]), self.cursor_col))

        # Handle active selection replacement
        if self.select_all_active:
            if key_char in ("\b", "\x08"):
                self._push_undo()
                self.lines = [""]
                self.cursor_line = 0
                self.cursor_col = 0
                self.select_all_active = False
                self._ensure_cursor_visible()
                return
            elif key_char in ("\r", "\n"):
                self._push_undo()
                self.lines = ["", ""]
                self.cursor_line = 1
                self.cursor_col = 0
                self.select_all_active = False
                self._ensure_cursor_visible()
                return
            elif key_char in ("KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT", "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"):
                self.select_all_active = False
            elif len(key_char) == 1 and ord(key_char) >= 32:
                self._push_undo()
                self.lines = [key_char]
                self.cursor_line = 0
                self.cursor_col = 1
                self.select_all_active = False
                self._ensure_cursor_visible()
                return

        # Smart Bracket & Quote Auto-Closing and Step-Over
        if key_char in ("(", "[", "{"):
            pair = {"(": ")", "[": "]", "{": "}"}[key_char]
            self._push_undo()
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col] + key_char + pair + line[self.cursor_col:]
            self.cursor_col += 1
            self._ensure_cursor_visible()
            return

        if key_char in (")", "]", "}"):
            line = self.lines[self.cursor_line]
            if self.cursor_col < len(line) and line[self.cursor_col] == key_char:
                self.cursor_col += 1
                self._ensure_cursor_visible()
                return

        if key_char in ('"', "'"):
            line = self.lines[self.cursor_line]
            if self.cursor_col < len(line) and line[self.cursor_col] == key_char:
                self.cursor_col += 1
                self._ensure_cursor_visible()
                return
            char_after = line[self.cursor_col] if self.cursor_col < len(line) else ""
            char_before = line[self.cursor_col - 1] if self.cursor_col > 0 else ""
            if (not char_before.isalnum()) and (char_after in ("", " ", ")", "]", "}", ",", ":")):
                self._push_undo()
                self.lines[self.cursor_line] = line[:self.cursor_col] + key_char + key_char + line[self.cursor_col:]
                self.cursor_col += 1
                self._ensure_cursor_visible()
                return

        # 1. Newline (Enter) with Auto-Indentation and Pair Expansion
        if key_char in ("\r", "\n"):
            self._push_undo()
            line = self.lines[self.cursor_line]
            left = line[:self.cursor_col]
            right = line[self.cursor_col:]
            
            leading_spaces = len(left) - len(left.lstrip(' '))
            extra_indent = 4 if left.rstrip().endswith(":") else 0
            
            # Smart expansion between brace pairs { | }
            if (left.rstrip().endswith("{") and right.lstrip().startswith("}")) or \
               (left.rstrip().endswith("(") and right.lstrip().startswith(")")) or \
               (left.rstrip().endswith("[") and right.lstrip().startswith("]")):
                indent_inner = " " * (leading_spaces + 4)
                indent_outer = " " * leading_spaces
                self.lines[self.cursor_line] = left
                self.lines.insert(self.cursor_line + 1, indent_inner)
                self.lines.insert(self.cursor_line + 2, indent_outer + right)
                self.cursor_line += 1
                self.cursor_col = len(indent_inner)
                self._ensure_cursor_visible()
                return

            indent_str = " " * (leading_spaces + extra_indent)
            self.lines[self.cursor_line] = left
            self.lines.insert(self.cursor_line + 1, indent_str + right)
            self.cursor_line += 1
            self.cursor_col = len(indent_str)
            self._ensure_cursor_visible()
            return

        # 2. Backspace (with bracket pair deletion and 4-space unindent)
        if key_char in ("\b", "\x08"):
            line = self.lines[self.cursor_line]
            if self.cursor_col > 0:
                self._push_undo()
                if self.cursor_col < len(line) and line[self.cursor_col - 1 : self.cursor_col + 1] in ("()", "[]", "{}", "''", '""'):
                    self.lines[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col + 1:]
                    self.cursor_col -= 1
                elif line[:self.cursor_col].endswith("    ") and self.cursor_col >= 4:
                    self.lines[self.cursor_line] = line[:self.cursor_col - 4] + line[self.cursor_col:]
                    self.cursor_col -= 4
                else:
                    self.lines[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
                    self.cursor_col -= 1
            elif self.cursor_line > 0:
                self._push_undo()
                prev_line = self.lines[self.cursor_line - 1]
                prev_len = len(prev_line)
                self.lines[self.cursor_line - 1] = prev_line + line
                del self.lines[self.cursor_line]
                self.cursor_line -= 1
                self.cursor_col = prev_len
            self._ensure_cursor_visible()
            return

        # 3. Tab (4 spaces)
        if key_char == "\t":
            self._push_undo()
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col] + "    " + line[self.cursor_col:]
            self.cursor_col += 4
            self._ensure_cursor_visible()
            return

        # 4. Arrow Navigation
        if key_char in ("KEY_UP", "\x1b[A"):
            if self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            self._ensure_cursor_visible()
            return

        if key_char in ("KEY_DOWN", "\x1b[B"):
            if self.cursor_line < len(self.lines) - 1:
                self.cursor_line += 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            self._ensure_cursor_visible()
            return

        if key_char in ("KEY_LEFT", "\x1b[D"):
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = len(self.lines[self.cursor_line])
            self._ensure_cursor_visible()
            return

        if key_char in ("KEY_RIGHT", "\x1b[C"):
            if self.cursor_col < len(self.lines[self.cursor_line]):
                self.cursor_col += 1
            elif self.cursor_line < len(self.lines) - 1:
                self.cursor_line += 1
                self.cursor_col = 0
            self._ensure_cursor_visible()
            return

        # 5. Printable character insertion
        if len(key_char) == 1 and ord(key_char) >= 32:
            if key_char == " " or self.cursor_col == 0 or self.cursor_col % 8 == 0:
                self._push_undo()
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col] + key_char + line[self.cursor_col:]
            self.cursor_col += 1
            self._ensure_cursor_visible()

    def _ensure_cursor_visible(self):
        """Scrolls editor buffer so cursor remains visible."""
        _, _, _, ch = self.client_rect
        line_h = 16 * self.font_scale
        visible_lines = max(1, (ch - 48) // line_h)
        if self.cursor_line < self.scroll_line:
            self.scroll_line = self.cursor_line
        elif self.cursor_line >= self.scroll_line + visible_lines:
            self.scroll_line = self.cursor_line - visible_lines + 1

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
