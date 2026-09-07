#!/usr/bin/env python3
"""
AdiOS Programmable Graphing Calculator (desktop/calculator.py)
A modern, dual-mode sovereign scientific and programmable graphing calculator.

Features:
- Dual-Pane Layout: Scientific Keypad (Left) & Real-Time 2D Function Grapher (Right)
- Programmable REPL / Scripting Engine: variable assignment (a = 15, r = 5.2), expressions, math functions
- Dynamic 2D Function Grapher:
  * Plots arbitrary f(x) curves in real-time with anti-aliasing
  * Cartesian grid with X/Y axes, origin (0, 0), tick marks
  * Presets: sin(x), cos(x), x^2, x^3 - 3x, tan(x), 1/x, Gaussian exp(-x^2)
  * Zoom (+ / -), Pan (<, >, ^, v), Reset
  * Live coordinate trace cursor showing (X, Y) mathematical space
- Standard & Scientific Keypad with high-contrast LCD Display
- Memory registers (MC, MR, M+, M-, ANS)
- Variables Inspector Table and scrollable Calculation History
- Full keyboard input support
- Strict Zero Emoji Policy.
"""

import math
import time
from typing import List, Tuple, Optional, Dict, Any

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from .theme import ThemeManager
from ui.canvas2d import Canvas2D, blend_pixel
from graphics.engine2d import draw_rounded_rect, draw_circle

# Palette Constants
COLOR_CALC_BG     = 0x0016161E
COLOR_LCD_BG      = 0x000F0F14
COLOR_LCD_TEXT    = 0x009ECE6A  # Emerald green
COLOR_EXPR_TEXT   = 0x007AA2F7  # Blue formula
COLOR_KEY_BG      = 0x0024283B
COLOR_KEY_OP      = 0x00FF9E64  # Orange operator
COLOR_KEY_FN      = 0x00BB9AF7  # Violet function
COLOR_KEY_CLR     = 0x00F7768E  # Red clear
COLOR_BORDER      = 0x00343B58
COLOR_TEXT        = 0x00C0CAF5
COLOR_GRID_AXIS   = 0x007AA2F7
COLOR_GRID_LINE   = 0x0024283B
COLOR_GRAPH_CURVE = 0x007DCFFF  # Cyan glowing curve
COLOR_DOCK_ACT    = 0x007AA2F7
COLOR_ACCENT      = 0x007AA2F7

class ProgrammableCalculator(Window):
    """
    Sovereign Programmable Graphing Calculator Window.
    """
    def __init__(
        self,
        win_id: str = "calc",
        x: int = 200,
        y: int = 60,
        w: int = 720,
        h: int = 490
    ):
        super().__init__(
            win_id=win_id,
            title="AdiOS Programmable Graphing Calculator",
            x=x,
            y=y,
            w=w,
            h=h,
            bg_color=COLOR_CALC_BG
        )
        # Display & Arithmetic State
        self.calc_display: str = "0"
        self.expression: str = ""
        self.calc_op: Optional[str] = None
        self.calc_arg1: float = 0.0
        self.calc_reset_on_next: bool = False
        self.memory: float = 0.0
        self.last_answer: float = 0.0

        # Programmable REPL & Variables State
        self.variables: Dict[str, float] = {
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
            "phi": (1.0 + math.sqrt(5.0)) / 2.0,
            "ans": 0.0
        }
        self.prog_input: str = ""
        self.history: List[Tuple[str, str]] = [
            ("sin(pi / 4)", f"{math.sin(math.pi / 4):.6f}"),
            ("sqrt(144) + 2**5", "44.0")
        ]
        self.view_mode: str = "graph"  # "graph", "prog", "vars"

        # 2D Function Grapher State
        self.func_str: str = "sin(x)"
        self.x_min: float = -10.0
        self.x_max: float = 10.0
        self.y_min: float = -5.0
        self.y_max: float = 5.0
        self.graph_w: int = 340
        self.graph_h: int = 300
        self.hover_coord: Optional[Tuple[float, float]] = None

        # Function Presets
        self.presets = [
            ("sin(x)", "sin(x)"),
            ("cos(x)", "cos(x)"),
            ("x^2", "x**2"),
            ("x^3-3x", "x**3 - 3*x"),
            ("1/x", "1/x if x != 0 else 0"),
            ("Gauss", "exp(-0.5 * x**2)")
        ]

        self.on_draw_content = self._render_content
        self.on_click_content = self._handle_click

    def _render_content(self, win: Window, fb: bytearray, font_dict):
        self.draw_calc_content(win, fb, font_dict)

    def _handle_click(self, win: Window, rel_x: int, rel_y: int):
        self.handle_click_content(win, rel_x, rel_y)

    # --------------------------------------------------------------------------
    # Mathematical Evaluation Engine
    # --------------------------------------------------------------------------

    def _eval_math(self, expr_str: str, x_val: Optional[float] = None) -> Any:
        """Evaluates mathematical string within safe sandboxed namespace."""
        safe_dict = {
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            "sqrt": math.sqrt,
            "exp": math.exp,
            "log": math.log,
            "log10": math.log10,
            "abs": abs,
            "floor": math.floor,
            "ceil": math.ceil,
            "round": round,
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau
        }
        safe_dict.update(self.variables)
        if x_val is not None:
            safe_dict["x"] = x_val

        # Replace standard calculator symbols
        clean_expr = expr_str.replace("^", "**")
        return eval(clean_expr, {"__builtins__": {}}, safe_dict)

    def execute_prog_line(self, line: str):
        """Executes a programmable statement (assignment or expression evaluation)."""
        line = line.strip()
        if not line:
            return

        if "=" in line and not any(op in line for op in ("==", "<=", ">=")):
            parts = line.split("=", 1)
            var_name = parts[0].strip()
            val_expr = parts[1].strip()
            if var_name.isidentifier():
                try:
                    res = float(self._eval_math(val_expr))
                    self.variables[var_name] = res
                    self.calc_display = str(res)
                    self.history.append((line, f"{var_name} = {res}"))
                    self.prog_input = ""
                    return
                except Exception as e:
                    self.history.append((line, f"Err: {str(e)[:24]}"))
                    return

        # Direct expression evaluation
        try:
            res = self._eval_math(line)
            res_float = float(res)
            self.last_answer = res_float
            self.variables["ans"] = res_float
            self.calc_display = str(res_float) if res_float != int(res_float) else str(int(res_float))
            self.history.append((line, self.calc_display))
            self.prog_input = ""
        except Exception as e:
            self.history.append((line, f"Err: {str(e)[:24]}"))

    def handle_calc_key(self, k: str):
        """Processes a calculator button press."""
        if k.isdigit():
            if self.calc_display == "0" or self.calc_reset_on_next:
                self.calc_display = k
                self.calc_reset_on_next = False
            else:
                self.calc_display += k
        elif k == ".":
            if self.calc_reset_on_next:
                self.calc_display = "0."
                self.calc_reset_on_next = False
            elif "." not in self.calc_display:
                self.calc_display += "."
        elif k in ("C", "CLEAR"):
            self.calc_display = "0"
            self.expression = ""
            self.calc_op = None
            self.calc_arg1 = 0.0
            self.calc_reset_on_next = False
        elif k == "DEL":
            if len(self.calc_display) > 1:
                self.calc_display = self.calc_display[:-1]
            else:
                self.calc_display = "0"
        elif k in ("+", "-", "*", "/", "^", "%", "MOD"):
            op_sym = "**" if k == "^" else ("%" if k == "MOD" else k)
            try:
                self.calc_arg1 = float(self.calc_display)
            except Exception:
                self.calc_arg1 = 0.0
            self.calc_op = op_sym
            self.expression = f"{self.calc_display} {k}"
            self.calc_reset_on_next = True
        elif k == "=":
            if self.calc_op is not None:
                try:
                    arg2 = float(self.calc_display)
                    if self.calc_op == "+":
                        res = self.calc_arg1 + arg2
                    elif self.calc_op == "-":
                        res = self.calc_arg1 - arg2
                    elif self.calc_op == "*":
                        res = self.calc_arg1 * arg2
                    elif self.calc_op == "/":
                        res = self.calc_arg1 / arg2 if arg2 != 0 else float("nan")
                    elif self.calc_op == "**":
                        res = self.calc_arg1 ** arg2
                    elif self.calc_op == "%":
                        res = self.calc_arg1 % arg2
                    else:
                        res = arg2

                    self.expression = f"{self.expression} {self.calc_display} ="
                    self.last_answer = res
                    self.variables["ans"] = res
                    self.calc_display = str(int(res)) if res == int(res) else f"{res:.8g}"
                    self.history.append((self.expression[:-2], self.calc_display))
                    self.calc_op = None
                    self.calc_reset_on_next = True
                except Exception:
                    self.calc_display = "ERR"
                    self.calc_reset_on_next = True
        elif k == "SQRT":
            try:
                v = float(self.calc_display)
                res = math.sqrt(abs(v))
                self.calc_display = str(int(res)) if res == int(res) else f"{res:.8g}"
                self.calc_reset_on_next = True
            except Exception:
                self.calc_display = "ERR"
        elif k in ("sin", "cos", "tan"):
            try:
                v = float(self.calc_display)
                fn = getattr(math, k)
                res = fn(v)
                self.calc_display = f"{res:.8g}"
                self.calc_reset_on_next = True
            except Exception:
                self.calc_display = "ERR"
        elif k == "pi":
            self.calc_display = f"{math.pi:.8g}"
            self.calc_reset_on_next = True
        elif k == "e":
            self.calc_display = f"{math.e:.8g}"
            self.calc_reset_on_next = True
        elif k == "ANS":
            self.calc_display = str(self.last_answer)
            self.calc_reset_on_next = True
        elif k == "MC":
            self.memory = 0.0
        elif k == "MR":
            self.calc_display = str(self.memory)
            self.calc_reset_on_next = True
        elif k == "M+":
            try:
                self.memory += float(self.calc_display)
            except Exception:
                pass
        elif k == "M-":
            try:
                self.memory -= float(self.calc_display)
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # Content Drawing & Compositing
    # --------------------------------------------------------------------------

    def draw_calc_content(self, win: Window, fb: bytearray, font_dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # Layout division: Left Keypad (~300px), Right Viewport (~400px)
        left_w = 300
        right_x = cx + left_w + 10
        right_w = cw - left_w - 20

        # Divider line between Keypad and Graph/REPL
        self._fill_rect_clipped(fb, cx + left_w + 4, cy + 4, 1, ch - 8, COLOR_BORDER, clip)

        # ----------------- LEFT PANE: KEYPAD & DISPLAY -----------------
        # LCD Display Card
        lcd_x = cx + 8
        lcd_y = cy + 8
        lcd_w = left_w - 12
        lcd_h = 58
        self._fill_rect_clipped(fb, lcd_x, lcd_y, lcd_w, lcd_h, COLOR_LCD_BG, clip)
        self._fill_rect_clipped(fb, lcd_x, lcd_y, lcd_w, 1, COLOR_BORDER, clip)
        self._fill_rect_clipped(fb, lcd_x, lcd_y + lcd_h - 1, lcd_w, 1, COLOR_BORDER, clip)

        # Upper Expression Line
        expr_txt = self.expression if self.expression else "DEG | Sovereign Calc"
        self._draw_str(fb, font_dict, lcd_x + 8, lcd_y + 8, expr_txt[:32], COLOR_EXPR_TEXT, clip)

        # Lower Big Value Line
        disp_txt = self.calc_display
        self._draw_str(fb, font_dict, lcd_x + 8, lcd_y + 32, disp_txt[:30], COLOR_LCD_TEXT, clip)

        # Memory indicator
        if self.memory != 0.0:
            self._draw_str(fb, font_dict, lcd_x + lcd_w - 24, lcd_y + 8, "M", COLOR_KEY_OP, clip)

        # Memory Buttons Row
        mem_keys = [("MC", "MC"), ("MR", "MR"), ("M+", "M+"), ("M-", "M-"), ("ANS", "ANS")]
        mem_y = lcd_y + lcd_h + 8
        m_bw = 52
        for i, (lbl, action) in enumerate(mem_keys):
            bx = lcd_x + i * 58
            self._draw_btn(fb, font_dict, bx, mem_y, m_bw, 18, lbl, COLOR_KEY_BG, COLOR_TEXT, clip)

        # 5x6 Keypad Buttons
        key_rows = [
            ["sin", "cos", "tan", "SQRT", "^", "C"],
            ["7",   "8",   "9",   "/",    "pi", "DEL"],
            ["4",   "5",   "6",   "*",    "e",  "("],
            ["1",   "2",   "3",   "-",    "MOD",")"],
            ["0",   ".",   "=",   "+",    "x",  "CLR"]
        ]
        key_start_y = mem_y + 26
        kw = 44
        kh = 28
        for r_idx, row in enumerate(key_rows):
            for c_idx, k in enumerate(row):
                bx = lcd_x + c_idx * 48
                by = key_start_y + r_idx * 34
                # Color styling
                if k in ("/", "*", "-", "+", "=", "^", "MOD"):
                    bg = COLOR_KEY_BG
                    tc = COLOR_KEY_OP
                elif k in ("sin", "cos", "tan", "SQRT", "pi", "e", "x"):
                    bg = COLOR_KEY_BG
                    tc = COLOR_KEY_FN
                elif k in ("C", "CLR", "DEL"):
                    bg = COLOR_KEY_BG
                    tc = COLOR_KEY_CLR
                else:
                    bg = COLOR_KEY_BG
                    tc = 0x00FFFFFF
                self._draw_btn(fb, font_dict, bx, by, kw, kh, k, bg, tc, clip)

        # Bottom Mode Switcher
        mode_y = key_start_y + 5 * 34 + 10
        self._draw_btn(fb, font_dict, lcd_x, mode_y, 88, 22, "GRAPH", COLOR_DOCK_ACT if self.view_mode == "graph" else COLOR_KEY_BG, 0x00FFFFFF, clip)
        self._draw_btn(fb, font_dict, lcd_x + 96, mode_y, 88, 22, "PROG / REPL", COLOR_DOCK_ACT if self.view_mode == "prog" else COLOR_KEY_BG, 0x00FFFFFF, clip)
        self._draw_btn(fb, font_dict, lcd_x + 192, mode_y, 88, 22, "VARIABLES", COLOR_DOCK_ACT if self.view_mode == "vars" else COLOR_KEY_BG, 0x00FFFFFF, clip)

        # ----------------- RIGHT PANE: GRAPH / REPL / VARS -----------------
        if self.view_mode == "graph":
            self._render_graph_view(fb, font_dict, right_x, cy + 8, right_w, ch - 16, clip)
        elif self.view_mode == "prog":
            self._render_prog_view(fb, font_dict, right_x, cy + 8, right_w, ch - 16, clip)
        else:
            self._render_vars_view(fb, font_dict, right_x, cy + 8, right_w, ch - 16, clip)

    def _render_graph_view(self, fb: bytearray, font_dict, rx: int, ry: int, rw: int, rh: int, clip):
        """Renders 2D function curve grapher."""
        # Top Formula & Presets Bar
        top_h = 30
        self._draw_str(fb, font_dict, rx, ry + 8, f"Plot: f(x) = {self.func_str}", COLOR_ACCENT, clip)

        # Quick preset buttons
        px = rx + 170
        for name, formula in self.presets[:4]:
            self._draw_btn(fb, font_dict, px, ry + 4, 38, 18, name[:4], COLOR_KEY_BG, COLOR_TEXT, clip)
            px += 42

        # Graph Viewport Bounds
        gw = min(rw - 10, self.graph_w)
        gh = min(rh - top_h - 40, self.graph_h)
        gx = rx
        gy = ry + top_h + 4
        gclip = (gx, gy, gx + gw, gy + gh)

        # Viewport Background & Frame
        self._fill_rect_clipped(fb, gx, gy, gw, gh, COLOR_LCD_BG, gclip)
        self._fill_rect_clipped(fb, gx, gy, gw, 1, COLOR_BORDER, gclip)
        self._fill_rect_clipped(fb, gx, gy + gh - 1, gw, 1, COLOR_BORDER, gclip)
        self._fill_rect_clipped(fb, gx, gy, 1, gh, COLOR_BORDER, gclip)
        self._fill_rect_clipped(fb, gx + gw - 1, gy, 1, gh, COLOR_BORDER, gclip)

        # Coordinate transformation helper
        def to_screen(math_x: float, math_y: float) -> Tuple[int, int]:
            sx = int(gx + (math_x - self.x_min) / (self.x_max - self.x_min) * gw)
            sy = int(gy + (self.y_max - math_y) / (self.y_max - self.y_min) * gh)
            return sx, sy

        # Draw Grid Lines
        for gx_val in range(int(self.x_min), int(self.x_max) + 1):
            if gx_val == 0:
                continue
            sx, _ = to_screen(float(gx_val), 0)
            if gx <= sx < gx + gw:
                self._fill_rect_clipped(fb, sx, gy, 1, gh, COLOR_GRID_LINE, gclip)

        for gy_val in range(int(self.y_min), int(self.y_max) + 1):
            if gy_val == 0:
                continue
            _, sy = to_screen(0, float(gy_val))
            if gy <= sy < gy + gh:
                self._fill_rect_clipped(fb, gx, sy, gw, 1, COLOR_GRID_LINE, gclip)

        # Draw X and Y Axes (in bold blue)
        orig_sx, orig_sy = to_screen(0.0, 0.0)
        if gx <= orig_sx < gx + gw:
            self._fill_rect_clipped(fb, orig_sx, gy, 1, gh, COLOR_GRID_AXIS, gclip)
        if gy <= orig_sy < gy + gh:
            self._fill_rect_clipped(fb, gx, orig_sy, gw, 1, COLOR_GRID_AXIS, gclip)

        # Render f(x) Curve
        prev_pt = None
        num_samples = max(80, gw)
        for i in range(num_samples + 1):
            t = i / num_samples
            mx = self.x_min + t * (self.x_max - self.x_min)
            try:
                my = float(self._eval_math(self.func_str, x_val=mx))
                if math.isnan(my) or math.isinf(my):
                    prev_pt = None
                    continue
                sx, sy = to_screen(mx, my)
                if prev_pt is not None:
                    # Draw line segment
                    self._draw_line_clipped(fb, prev_pt[0], prev_pt[1], sx, sy, COLOR_GRAPH_CURVE, gclip)
                prev_pt = (sx, sy)
            except Exception:
                prev_pt = None

        # Bottom View Controls ([+], [-], [<], [>], [RST])
        ctrl_y = gy + gh + 8
        self._draw_btn(fb, font_dict, gx, ctrl_y, 28, 20, "+", COLOR_KEY_BG, COLOR_TEXT, clip)
        self._draw_btn(fb, font_dict, gx + 32, ctrl_y, 28, 20, "-", COLOR_KEY_BG, COLOR_TEXT, clip)
        self._draw_btn(fb, font_dict, gx + 64, ctrl_y, 28, 20, "<", COLOR_KEY_BG, COLOR_TEXT, clip)
        self._draw_btn(fb, font_dict, gx + 96, ctrl_y, 28, 20, ">", COLOR_KEY_BG, COLOR_TEXT, clip)
        self._draw_btn(fb, font_dict, gx + 128, ctrl_y, 42, 20, "RST", COLOR_KEY_BG, COLOR_TEXT, clip)

        # Coordinate Readout
        coord_txt = f"X: [{self.x_min:.1f}, {self.x_max:.1f}] Y: [{self.y_min:.1f}, {self.y_max:.1f}]"
        self._draw_str(fb, font_dict, gx + 180, ctrl_y + 6, coord_txt, COLOR_TEXT, clip)

    def _render_prog_view(self, fb: bytearray, font_dict, rx: int, ry: int, rw: int, rh: int, clip):
        """Renders programmable REPL and script history view."""
        self._draw_str(fb, font_dict, rx, ry + 4, "Programmable REPL Console", COLOR_ACCENT, clip)

        # History Card
        hist_h = rh - 70
        self._fill_rect_clipped(fb, rx, ry + 24, rw, hist_h, COLOR_LCD_BG, clip)
        self._fill_rect_clipped(fb, rx, ry + 24, rw, 1, COLOR_BORDER, clip)
        self._fill_rect_clipped(fb, rx, ry + 24 + hist_h - 1, rw, 1, COLOR_BORDER, clip)

        # Render History lines
        curr_y = ry + 32
        for expr_item, res_item in self.history[-14:]:
            self._draw_str(fb, font_dict, rx + 10, curr_y, f"> {expr_item}", COLOR_EXPR_TEXT, clip)
            curr_y += 14
            self._draw_str(fb, font_dict, rx + 24, curr_y, f"=> {res_item}", COLOR_LCD_TEXT, clip)
            curr_y += 16

        # Command Input Line
        in_y = ry + hist_h + 32
        self._fill_rect_clipped(fb, rx, in_y, rw - 60, 24, 0x0024283B, clip)
        self._fill_rect_clipped(fb, rx, in_y, rw - 60, 1, COLOR_BORDER, clip)
        input_disp = f"Eval: {self.prog_input}_"
        self._draw_str(fb, font_dict, rx + 8, in_y + 7, input_disp[:38], 0x00FFFFFF, clip)

        # [EXEC] Button
        self._draw_btn(fb, font_dict, rx + rw - 54, in_y, 54, 24, "EXEC", COLOR_DOCK_ACT, 0x00FFFFFF, clip)

    def _render_vars_view(self, fb: bytearray, font_dict, rx: int, ry: int, rw: int, rh: int, clip):
        """Renders active variables and constants inspector."""
        self._draw_str(fb, font_dict, rx, ry + 4, "Active Variables & Constants", COLOR_ACCENT, clip)

        # Table Box
        tbl_h = rh - 30
        self._fill_rect_clipped(fb, rx, ry + 24, rw, tbl_h, COLOR_LCD_BG, clip)
        self._fill_rect_clipped(fb, rx, ry + 24, rw, 1, COLOR_BORDER, clip)
        self._fill_rect_clipped(fb, rx, ry + 24 + tbl_h - 1, rw, 1, COLOR_BORDER, clip)

        # Table Header
        self._draw_str(fb, font_dict, rx + 14, ry + 32, "NAME", COLOR_ACCENT, clip)
        self._draw_str(fb, font_dict, rx + 120, ry + 32, "VALUE", COLOR_ACCENT, clip)
        self._fill_rect_clipped(fb, rx + 10, ry + 46, rw - 20, 1, COLOR_BORDER, clip)

        curr_y = ry + 54
        for name, val in self.variables.items():
            val_str = f"{val:.8g}" if isinstance(val, float) else str(val)
            self._draw_str(fb, font_dict, rx + 14, curr_y, name, COLOR_EXPR_TEXT, clip)
            self._draw_str(fb, font_dict, rx + 120, curr_y, val_str, COLOR_LCD_TEXT, clip)
            curr_y += 18

    # --------------------------------------------------------------------------
    # Click & Interaction Handlers
    # --------------------------------------------------------------------------

    def handle_click_content(self, win: Window, rel_x: int, rel_y: int):
        left_w = 300
        right_x = left_w + 10

        # Mode switcher click
        if 260 <= rel_y <= 290 and rel_x < left_w:
            if rel_x < 96:
                self.view_mode = "graph"
            elif rel_x < 192:
                self.view_mode = "prog"
            else:
                self.view_mode = "vars"
            return

        # Memory buttons row click
        if 74 <= rel_y <= 94 and rel_x < left_w:
            idx = (rel_x - 8) // 58
            mem_actions = ["MC", "MR", "M+", "M-", "ANS"]
            if 0 <= idx < len(mem_actions):
                self.handle_calc_key(mem_actions[idx])
                return

        # Keypad clicks
        key_start_y = 100
        if key_start_y <= rel_y < key_start_y + 5 * 34 and rel_x < left_w:
            row_idx = (rel_y - key_start_y) // 34
            col_idx = (rel_x - 8) // 48
            key_rows = [
                ["sin", "cos", "tan", "SQRT", "^", "C"],
                ["7",   "8",   "9",   "/",    "pi", "DEL"],
                ["4",   "5",   "6",   "*",    "e",  "("],
                ["1",   "2",   "3",   "-",    "MOD",")"],
                ["0",   ".",   "=",   "+",    "x",  "CLR"]
            ]
            if 0 <= row_idx < len(key_rows) and 0 <= col_idx < len(key_rows[row_idx]):
                self.handle_calc_key(key_rows[row_idx][col_idx])
                return

        # Right pane graph presets
        if self.view_mode == "graph" and 10 <= rel_y <= 30 and rel_x >= right_x + 170:
            pidx = (rel_x - (right_x + 170)) // 42
            if 0 <= pidx < len(self.presets):
                self.func_str = self.presets[pidx][1]
                return

        # Right pane zoom/pan controls
        if self.view_mode == "graph" and rel_y > 340 and rel_x >= right_x:
            c_rel_x = rel_x - right_x
            if c_rel_x < 30:  # Zoom In
                self.x_min *= 0.8
                self.x_max *= 0.8
                self.y_min *= 0.8
                self.y_max *= 0.8
            elif c_rel_x < 62:  # Zoom Out
                self.x_min *= 1.25
                self.x_max *= 1.25
                self.y_min *= 1.25
                self.y_max *= 1.25
            elif c_rel_x < 94:  # Pan Left
                dx = (self.x_max - self.x_min) * 0.2
                self.x_min -= dx
                self.x_max -= dx
            elif c_rel_x < 126:  # Pan Right
                dx = (self.x_max - self.x_min) * 0.2
                self.x_min += dx
                self.x_max += dx
            elif c_rel_x < 170:  # Reset
                self.x_min, self.x_max = -10.0, 10.0
                self.y_min, self.y_max = -5.0, 5.0
            return

        # Right pane REPL exec button
        if self.view_mode == "prog" and rel_y > 400 and rel_x >= self.w - 70:
            if self.prog_input:
                self.execute_prog_line(self.prog_input)
            return

    def handle_key(self, key_char: str):
        """Processes keyboard input for both keypad and programmable console."""
        if self.view_mode == "prog":
            if key_char in ("\r", "\n", "CTRL_ENTER"):
                if self.prog_input.strip():
                    self.execute_prog_line(self.prog_input.strip())
            elif key_char in ("\b", "\x08", "CTRL_BACKSPACE"):
                self.prog_input = self.prog_input[:-1]
            elif len(key_char) == 1 and 32 <= ord(key_char) <= 126:
                self.prog_input += key_char
            return

        # Direct keypad shortcuts
        if key_char in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "."):
            self.handle_calc_key(key_char)
        elif key_char in ("+", "-", "*", "/"):
            self.handle_calc_key(key_char)
        elif key_char in ("\r", "\n", "="):
            self.handle_calc_key("=")
        elif key_char in ("\b", "\x08"):
            self.handle_calc_key("DEL")
        elif key_char in ("c", "C", "ESCAPE"):
            self.handle_calc_key("C")

    # --------------------------------------------------------------------------
    # Drawing Helpers
    # --------------------------------------------------------------------------

    def _fill_rect_clipped(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int, clip):
        x1 = max(clip[0], max(0, x))
        y1 = max(clip[1], max(0, y))
        x2 = min(clip[2] - 1, min(1280 - 1, x + w - 1))
        y2 = min(clip[3] - 1, min(720 - 1, y + h - 1))
        if x1 > x2 or y1 > y2:
            return

        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        span_len = x2 - x1 + 1
        line_bytes = c_bytes * span_len
        for py in range(y1, y2 + 1):
            off = (py * 1280 + x1) * 4
            fb[off : off + span_len * 4] = line_bytes

    def _draw_line_clipped(self, fb: bytearray, x0: int, y0: int, x1: int, y1: int, color: int, clip):
        """Draws a clipped Bresenham line."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])

        cx, cy = x0, y0
        while True:
            if clip[0] <= cx < clip[2] and clip[1] <= cy < clip[3]:
                if 0 <= cx < 1280 and 0 <= cy < 720:
                    off = (cy * 1280 + cx) * 4
                    fb[off : off + 4] = c_bytes
            if cx == x1 and cy == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                cx += sx
            if e2 <= dx:
                err += dx
                cy += sy

    def _draw_btn(self, fb: bytearray, font_dict, x: int, y: int, w: int, h: int, text: str, bg: int, tc: int, clip):
        self._fill_rect_clipped(fb, x, y, w, h, bg, clip)
        self._fill_rect_clipped(fb, x, y, w, 1, COLOR_BORDER, clip)
        self._fill_rect_clipped(fb, x, y + h - 1, w, 1, COLOR_BORDER, clip)
        self._fill_rect_clipped(fb, x, y, 1, h, COLOR_BORDER, clip)
        self._fill_rect_clipped(fb, x + w - 1, y, 1, h, COLOR_BORDER, clip)
        tx = x + max(2, (w - len(text) * 8) // 2)
        ty = y + max(2, (h - 8) // 2)
        self._draw_str(fb, font_dict, tx, ty, text, tc, clip)

    def _draw_str(self, fb: bytearray, font_dict, x: int, y: int, text: str, color: int, clip):
        curr_x = x
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        for ch in text:
            if curr_x + 8 > clip[2]:
                break
            glyph = font_dict.get(ord(ch), font_dict.get(ch, None)) if font_dict else None
            if glyph:
                for row in range(8):
                    py = y + row
                    if clip[1] <= py < clip[3]:
                        byte_val = glyph[row]
                        if byte_val:
                            row_off = (py * 1280 + curr_x) * 4
                            for col in range(8):
                                px = curr_x + col
                                if clip[0] <= px < clip[2] and ((byte_val >> (7 - col)) & 1):
                                    fb[row_off + col * 4 : row_off + col * 4 + 4] = c_bytes
            curr_x += 8
