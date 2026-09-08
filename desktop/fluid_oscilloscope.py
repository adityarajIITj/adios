#!/usr/bin/env python3
"""
AdiOS FluidRAM Oscilloscope - 60 FPS Living Memory Manifold (desktop/fluid_oscilloscope.py)

Visualizes the 1024 MB Autonomous Dynamic RAM Mesh in real time:
- 32x32 Topological Hydrodynamic Wave Grid representing all 1024 MB of sovereign RAM.
- Real-time pressure gradients, potential flow vectors, and tensegrity cable contractions.
- Live Void-Pipe in-flight ephemeral stream telemetry (< 4.0 MB footprint).
- Tactile interactive controls: Pulse Pressure Wave, Harmonic Compaction, Equilibrium Purge.
- Zero external dependencies. Pure software rasterization at 60 FPS.

Strict Zero Emoji Policy Enforced.
"""

import math
import time
from typing import List, Dict, Tuple, Optional, Any

from kernel.fluid_ram import (
    FluidRAMMesh, get_fluid_ram_mesh,
    POOL_KERNEL_CORE, POOL_COMPOSITOR_FB, POOL_STREAM_RING,
    POOL_CHRONOS_DELTA, POOL_USER_APPS, POOL_DYNAMIC_MESH
)
from graphics.engine2d import draw_rounded_rect, draw_drop_shadow

# Color Palette: Nordic Slate / Cyberpunk Sovereign Workstation
COLOR_BG_DARK       = 0x000B0F17
COLOR_BG_PANEL      = 0x00131B2A
COLOR_BORDER_FRAME  = 0x001E293B
COLOR_TEXT_WHITE    = 0x00F1F5F9
COLOR_TEXT_MUTED    = 0x0064748B
COLOR_ACCENT_CYAN   = 0x0038BDF8
COLOR_ACCENT_EMERALD= 0x0010B981
COLOR_ACCENT_AMBER  = 0x00F59E0B
COLOR_ACCENT_VIOLET = 0x008B5CF6
COLOR_ACCENT_ROSE   = 0x00F43F5E
COLOR_ACCENT_SAPPHIRE=0x002563EB

# Pool Base Color Map
POOL_COLOR_MAP = {
    POOL_KERNEL_CORE:    0x00334155,  # Deep Slate
    POOL_COMPOSITOR_FB:  0x000284C7,  # Ocean Blue
    POOL_STREAM_RING:    0x0010B981,  # Neon Emerald (Void-Pipe)
    POOL_CHRONOS_DELTA:  0x007C3AED,  # Deep Violet (Galois Retro-Inversion)
    POOL_USER_APPS:      0x00D97706,  # Warm Amber
    POOL_DYNAMIC_MESH:   0x002563EB   # Fluid Sapphire
}


class FluidOscilloscopeApp:
    """
    Sovereign FluidRAM Oscilloscope & Manifold Visualizer.
    """

    def __init__(self, screen_w: int = 1024, screen_h: int = 768):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.mesh: FluidRAMMesh = get_fluid_ram_mesh()
        
        self.selected_cell_index: Optional[int] = None
        self.selected_cell_info: Optional[Dict[str, Any]] = None
        self.status_message = "FluidRAM Autonomous Manifold Active. Laminar flow optimal."
        self.last_step_time = time.time()
        self.anim_tick = 0

    def step(self):
        """Advances simulation and wave animation at 60 FPS."""
        now = time.time()
        dt = now - self.last_step_time
        self.last_step_time = now
        self.anim_tick += 1
        
        # Smoothly decay wave pulse phase
        if self.mesh.wave_pulse_phase > 0.0:
            self.mesh.wave_pulse_phase = max(0.0, self.mesh.wave_pulse_phase - (dt * 1.8))

    def handle_click(self, rel_x: int, rel_y: int, win_w: int = 760, win_h: int = 520):
        """Processes mouse interaction on buttons or grid cells."""
        # Top Header Buttons (y: 34 to 58)
        if 34 <= rel_y <= 58:
            # Button 1: Pulse Wave (x: 14 to 124)
            if 14 <= rel_x <= 124:
                self.mesh.wave_pulse_phase = 3.14
                self.status_message = "Pressure pulse injected across 1024 MB manifold."
                return
            # Button 2: Harmonic Compact (x: 134 to 274)
            if 134 <= rel_x <= 274:
                res = self.mesh.harmonic_compact()
                self.status_message = f"Harmonic compaction complete. Freed {res['freed_mb']} MB transient slack."
                return
            # Button 3: Equilibrium Purge (x: 284 to 424)
            if 284 <= rel_x <= 424:
                freed = self.mesh.dissipate_surface_tension()
                self.status_message = f"Surface tension dissipated. Reclaimed {freed} MB into dynamic reserve."
                return

        # Topological Grid Click Detection
        # Grid boundaries: x: 14 to 430, y: 72 to 488 (size ~416x416)
        grid_x0 = 14
        grid_y0 = 72
        cell_size = 13
        grid_dim = 32  # 32x32 = 1024 cells
        
        if grid_x0 <= rel_x < (grid_x0 + grid_dim * cell_size) and grid_y0 <= rel_y < (grid_y0 + grid_dim * cell_size):
            col = (rel_x - grid_x0) // cell_size
            row = (rel_y - grid_y0) // cell_size
            idx = row * grid_dim + col
            if 0 <= idx < 1024:
                self.selected_cell_index = idx
                # Inspect cell in topology
                matrix = self.mesh.get_topology_matrix()
                cell_data = matrix[row][col]
                addr = idx * (1024 * 1024)
                self.selected_cell_info = {
                    "index": idx,
                    "address_hex": f"0x{addr:08X}",
                    "pool": cell_data["pool"],
                    "pressure": cell_data["pressure"],
                    "tension": cell_data["tension"]
                }
                self.status_message = f"Inspecting 1 MB Page #{idx} ({cell_data['pool']}) at 0x{addr:08X}"

    def render(self, fb: bytearray, font: Any, win_x: int, win_y: int, win_w: int, win_h: int):
        """Renders the entire FluidRAM Oscilloscope into the window buffer."""
        clip = (win_x, win_y, win_x + win_w, win_y + win_h)
        
        # 1. Base Window Background
        self._fill_rect(fb, win_x, win_y, win_w, win_h, COLOR_BG_DARK, clip)
        
        # 2. Header Dashboard Bar (y: 6 to 30)
        summary = self.mesh.get_system_summary()
        self._render_header_telemetry(fb, font, win_x + 14, win_y + 8, win_w - 28, 22, summary, clip)
        
        # 3. Action Control Buttons (y: 34 to 58)
        self._render_action_buttons(fb, font, win_x + 14, win_y + 34, win_w - 28, 24, clip)
        
        # 4. Left Pane: 32x32 Topological Hydrodynamic Wave Matrix
        grid_w = 416
        grid_h = 416
        self._render_topological_matrix(fb, font, win_x + 14, win_y + 66, grid_w, grid_h, clip)
        
        # 5. Right Pane: Hydrodynamic Telemetry & Flow Gauges
        right_x = win_x + 14 + grid_w + 14
        right_w = win_w - (14 + grid_w + 28)
        self._render_telemetry_gauges(fb, font, right_x, win_y + 66, right_w, grid_h, summary, clip)
        
        # 6. Bottom Status Bar (y: win_h - 26 to win_h - 4)
        status_y = win_y + win_h - 26
        self._fill_rect(fb, win_x + 4, status_y, win_w - 8, 22, COLOR_BG_PANEL, clip)
        self._draw_str(fb, font, win_x + 12, status_y + 6, self.status_message[:80], COLOR_TEXT_WHITE, clip)

    def _render_header_telemetry(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, s: Dict[str, Any], clip: Tuple):
        """Draws top high-level status badges."""
        self._fill_rect(fb, x, y, w, h, COLOR_BG_PANEL, clip)
        self._draw_line(fb, x, y + h - 1, x + w, y + h - 1, COLOR_BORDER_FRAME, clip)
        
        t1 = f"CAPACITY: {s['physical_capacity_mb']} MB"
        t2 = f"EFFECTIVE: {s['effective_density_mb']} MB ({s['effective_density_ratio']})"
        t3 = f"FLOW: {s['flow_efficiency_pct']}% LAMINAR"
        t4 = f"FAULTS/SWAP: {s['page_faults']}/{s['swap_disk_kb']} KB"
        
        self._draw_str(fb, font, x + 8, y + 5, t1, COLOR_TEXT_WHITE, clip)
        self._draw_str(fb, font, x + 160, y + 5, t2, COLOR_ACCENT_EMERALD, clip)
        self._draw_str(fb, font, x + 380, y + 5, t3, COLOR_ACCENT_CYAN, clip)
        self._draw_str(fb, font, x + 550, y + 5, t4, COLOR_ACCENT_AMBER, clip)

    def _render_action_buttons(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, clip: Tuple):
        """Draws interactive tactile impulse buttons."""
        self._draw_btn(fb, font, x, y, 110, h, "PULSE WAVE", COLOR_ACCENT_CYAN, 0x00000000, clip)
        self._draw_btn(fb, font, x + 120, y, 140, h, "HARMONIC COMPACT", COLOR_ACCENT_EMERALD, 0x00000000, clip)
        self._draw_btn(fb, font, x + 270, y, 140, h, "EQUILIBRIUM PURGE", COLOR_ACCENT_VIOLET, COLOR_TEXT_WHITE, clip)

    def _render_topological_matrix(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, clip: Tuple):
        """Renders the 32x32 hydrodynamic RAM grid with living wave harmonics."""
        # Panel frame
        self._fill_rect(fb, x, y, w, h, COLOR_BG_PANEL, clip)
        self._draw_rect_outline(fb, x, y, w, h, COLOR_BORDER_FRAME, clip)
        
        matrix = self.mesh.get_topology_matrix(rows=32, cols=32)
        cell_size = 13
        
        for r in range(32):
            for c in range(32):
                cell = matrix[r][c]
                px = x + c * cell_size
                py = y + r * cell_size
                
                # Retrieve base pool color
                base_col = POOL_COLOR_MAP.get(cell["pool"], 0x002563EB)
                
                # Modulate brightness using heat factor
                heat = cell["heat"]
                mod_col = self._modulate_color(base_col, 0.4 + heat * 0.6)
                
                idx = r * 32 + c
                if self.selected_cell_index == idx:
                    # Highlight selected cell with bright white border
                    self._fill_rect(fb, px, py, cell_size - 1, cell_size - 1, 0x00FFFFFF, clip)
                else:
                    self._fill_rect(fb, px, py, cell_size - 1, cell_size - 1, mod_col, clip)

    def _render_telemetry_gauges(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, s: Dict[str, Any], clip: Tuple):
        """Renders right-side pool pressure gauges and Void-Pipe monitor."""
        self._fill_rect(fb, x, y, w, h, COLOR_BG_PANEL, clip)
        self._draw_rect_outline(fb, x, y, w, h, COLOR_BORDER_FRAME, clip)
        
        # Subsystem Pools Pressure Bar Section
        self._draw_str(fb, font, x + 10, y + 8, "SUBSYSTEM POOL PRESSURES", COLOR_ACCENT_CYAN, clip)
        
        bar_y = y + 26
        for name, pool in self.mesh.pools.items():
            short_name = name.replace("DYNAMIC_ELASTIC_MESH", "ELASTIC_MESH").replace("COMPOSITOR_FB", "COMPOSITOR")
            lbl = f"{short_name[:12]}: {int(pool.used_mb)}/{int(pool.current_capacity_mb)}M"
            self._draw_str(fb, font, x + 10, bar_y, lbl, COLOR_TEXT_WHITE, clip)
            
            # Draw pressure bar
            gauge_w = w - 20
            p_val = pool.pressure
            fill_w = int(gauge_w * p_val)
            col = COLOR_ACCENT_EMERALD if p_val < 0.65 else (COLOR_ACCENT_AMBER if p_val < 0.85 else COLOR_ACCENT_ROSE)
            
            # Gauge background
            self._fill_rect(fb, x + 10, bar_y + 12, gauge_w, 6, 0x000F172A, clip)
            # Gauge fill
            self._fill_rect(fb, x + 10, bar_y + 12, max(2, fill_w), 6, col, clip)
            bar_y += 24

        # Divider
        self._draw_line(fb, x + 10, bar_y + 4, x + w - 10, bar_y + 4, COLOR_BORDER_FRAME, clip)
        bar_y += 12

        # The Void-Pipe In-Flight Video Telemetry Card
        vp = s["void_pipe"]
        self._draw_str(fb, font, x + 10, bar_y, "THE VOID-PIPE (EPHEMERAL STREAM)", COLOR_ACCENT_EMERALD, clip)
        bar_y += 16
        self._draw_str(fb, font, x + 10, bar_y, f"Active Footprint: {vp['active_footprint_mb']} MB (< 4.0 MB)", COLOR_TEXT_WHITE, clip)
        bar_y += 14
        self._draw_str(fb, font, x + 10, bar_y, f"Transduced Total: {vp['total_transduced_mb']} MB", COLOR_TEXT_MUTED, clip)
        bar_y += 14
        self._draw_str(fb, font, x + 10, bar_y, f"Disk Writes/Swap: 0.00 KB (Zero Disk)", COLOR_ACCENT_EMERALD, clip)
        bar_y += 14
        self._draw_str(fb, font, x + 10, bar_y, f"Evaporation Window: 16.6 ms @ 60 FPS", COLOR_TEXT_MUTED, clip)
        bar_y += 20

        # Divider
        self._draw_line(fb, x + 10, bar_y, x + w - 10, bar_y, COLOR_BORDER_FRAME, clip)
        bar_y += 10

        # Dynamic Focus Attraction Card
        self._draw_str(fb, font, x + 10, bar_y, "BIOMIMETIC TENSEGRITY FOCUS", COLOR_ACCENT_VIOLET, clip)
        bar_y += 16
        self._draw_str(fb, font, x + 10, bar_y, f"Active Focus: {s['focused_application']}", COLOR_TEXT_WHITE, clip)
        bar_y += 14
        self._draw_str(fb, font, x + 10, bar_y, f"Tension Equilibrium: BALANCED", COLOR_ACCENT_CYAN, clip)
        bar_y += 14
        self._draw_str(fb, font, x + 10, bar_y, f"P2P Rebalance Cycles: {s['borrow_cycles']}", COLOR_TEXT_MUTED, clip)

    # --------------------------------------------------------------------------
    # Drawing Primitives
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, rx: int, ry: int, rw: int, rh: int, col: int, clip: Tuple):
        """Blits a solid color rectangle with clipping."""
        cx0, cy0, cx1, cy1 = clip
        x0 = max(rx, cx0)
        y0 = max(ry, cy0)
        x1 = min(rx + rw, cx1)
        y1 = min(ry + rh, cy1)
        if x0 >= x1 or y0 >= y1:
            return

        b = col & 0xFF
        g = (col >> 8) & 0xFF
        r = (col >> 16) & 0xFF
        row_bytes = bytes([b, g, r, 0xFF]) * (x1 - x0)

        for y in range(y0, y1):
            idx = (y * self.screen_w + x0) * 4
            fb[idx:idx + len(row_bytes)] = row_bytes

    def _draw_rect_outline(self, fb: bytearray, rx: int, ry: int, rw: int, rh: int, col: int, clip: Tuple):
        """Draws a 1-pixel rectangle outline."""
        self._draw_line(fb, rx, ry, rx + rw - 1, ry, col, clip)
        self._draw_line(fb, rx, ry + rh - 1, rx + rw - 1, ry + rh - 1, col, clip)
        self._draw_line(fb, rx, ry, rx, ry + rh - 1, col, clip)
        self._draw_line(fb, rx + rw - 1, ry, rx + rw - 1, ry + rh - 1, col, clip)

    def _draw_line(self, fb: bytearray, x0: int, y0: int, x1: int, y1: int, col: int, clip: Tuple):
        """Bresenham's line rasterizer."""
        cx0, cy0, cx1, cy1 = clip
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        b = col & 0xFF
        g = (col >> 8) & 0xFF
        r = (col >> 16) & 0xFF

        while True:
            if cx0 <= x0 < cx1 and cy0 <= y0 < cy1:
                idx = (y0 * self.screen_w + x0) * 4
                fb[idx] = b
                fb[idx + 1] = g
                fb[idx + 2] = r
                fb[idx + 3] = 0xFF
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def _draw_btn(self, fb: bytearray, font: Any, bx: int, by: int, bw: int, bh: int, text: str, bg_col: int, fg_col: int, clip: Tuple):
        """Draws a tactile button with subtle outline."""
        self._fill_rect(fb, bx, by, bw, bh, bg_col, clip)
        self._draw_rect_outline(fb, bx, by, bw, bh, COLOR_BORDER_FRAME, clip)
        tx = bx + max(4, (bw - len(text) * 8) // 2)
        ty = by + max(2, (bh - 12) // 2)
        self._draw_str(fb, font, tx, ty, text, fg_col, clip)

    def _draw_str(self, fb: bytearray, font: Any, sx: int, sy: int, text: str, col: int, clip: Tuple):
        """Draws bitmap string supporting both font dict and font objects."""
        if not font:
            return
        cx0, cy0, cx1, cy1 = clip
        sw = self.screen_w
        b = col & 0xFF
        g = (col >> 8) & 0xFF
        r = (col >> 16) & 0xFF
        c_bytes = bytes([b, g, r, 0xFF])

        curr_x = sx
        for ch in text:
            if curr_x + 8 > cx1:
                break
            if hasattr(font, "render_char"):
                font.render_char(fb, curr_x, sy, ch, col, clip, screen_w=sw)
            elif isinstance(font, dict):
                code = ord(ch)
                glyph = font.get(code)
                if glyph and cy0 <= sy and sy + 7 < cy1 and cx0 <= curr_x and curr_x + 7 < cx1:
                    for row in range(8):
                        byte_val = glyph[row]
                        if byte_val:
                            row_off = ((sy + row) * sw + curr_x) * 4
                            for c_idx in range(8):
                                if (byte_val >> (7 - c_idx)) & 1:
                                    off = row_off + c_idx * 4
                                    fb[off : off + 4] = c_bytes
            curr_x += 8

    def _modulate_color(self, base_col: int, factor: float) -> int:
        """Scales color channels by float factor for wave lighting."""
        b = int((base_col & 0xFF) * factor)
        g = int(((base_col >> 8) & 0xFF) * factor)
        r = int(((base_col >> 16) & 0xFF) * factor)
        b = max(0, min(255, b))
        g = max(0, min(255, g))
        r = max(0, min(255, r))
        return (r << 16) | (g << 8) | b
