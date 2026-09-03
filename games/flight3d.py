#!/usr/bin/env python3
"""
AdiOS 3D Flight & Wireframe Simulator ("StarFlight 3D")
Inspired by Terry A. Davis's TempleOS 3D Flight Simulator and CastleFrankenstein.
Features:
- Real-time 3D rotation matrix transformations
- Perspective 3D camera projection on 640x480 Framebuffer
- Infinite scrolling 3D wireframe ground terrain grid with horizon convergence
- 3D wireframe starfighter with responsive pitch and bank controls
- Dynamic 3D rings/gates to navigate through with collision detection
- Real-time HUD: 3D artificial horizon pitch ladder, altitude, speed, score
- Audio tone feedback on gate passage via MMIO audio
"""

import math
import time
import random
import os
import sys

# Screen constants
SCREEN_W = 640
SCREEN_H = 480
HALF_W = SCREEN_W // 2
HALF_H = SCREEN_H // 2
FOCAL_LEN = 320

# Colors (ARGB 32-bit hex)
COLOR_BG       = 0x0010121C # Deep Space Navy
COLOR_GRID     = 0x002A324B # Ground Grid
COLOR_HORIZON  = 0x007AA2F7 # Electric Blue Horizon
COLOR_SHIP     = 0x00E0AF68 # Gold Starfighter
COLOR_WING     = 0x00BB9AF7 # Purple Wings
COLOR_RING     = 0x009ECE6A # Vibrant Green Gate
COLOR_RING_HIT = 0x007DCFFF # Cyan Flash
COLOR_HUD      = 0x0000FFCC # Neon Cyan HUD
COLOR_TEXT     = 0x00FFFFFF # White

class StarFlight3D:
    def __init__(self, vm):
        self.vm = vm
        self.fb = vm.fb

        # Ship Flight Dynamics
        self.ship_x = 0.0
        self.ship_y = 40.0 # Altitude
        self.ship_z = 0.0
        self.pitch = 0.0   # Radians
        self.bank = 0.0    # Radians
        self.speed = 12.0
        self.score = 0
        self.rings_cleared = 0

        # Terrain & Speed
        self.terrain_offset = 0.0

        # 3D Rings to fly through
        self.gates = []
        for i in range(8):
            self.gates.append({
                "x": random.uniform(-180, 180),
                "y": random.uniform(20, 120),
                "z": 400 + i * 250,
                "radius": 45,
                "hit": False
            })

        # 3D Starfield particles
        self.stars = []
        for _ in range(60):
            self.stars.append({
                "x": random.uniform(-400, 400),
                "y": random.uniform(-100, 300),
                "z": random.uniform(50, 1500),
                "speed": random.uniform(1.5, 3.0)
            })

    def project_3d(self, x, y, z):
        """Perspective 3D Projection: (X, Y, Z) -> (Screen_X, Screen_Y)."""
        if z <= 10.0:
            return None, None
        sx = int(HALF_W + (x * FOCAL_LEN) / z)
        sy = int(HALF_H - (y * FOCAL_LEN) / z)
        return sx, sy

    def draw_line(self, x0, y0, x1, y1, color):
        """Bresenham line rasterizer directly on Framebuffer."""
        if x0 is None or y0 is None or x1 is None or y1 is None:
            return

        # Simple Cohen-Sutherland / bounding clamp
        if not (0 <= x0 < SCREEN_W or 0 <= x1 < SCREEN_W) and not (0 <= y0 < SCREEN_H or 0 <= y1 < SCREEN_H):
            return

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, (color >> 24) & 0xFF])
        fb = self.fb

        while True:
            if 0 <= x0 < SCREEN_W and 0 <= y0 < SCREEN_H:
                off = (y0 * SCREEN_W + x0) * 4
                fb[off:off+4] = c_bytes
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def render_terrain(self):
        """Draws TempleOS-style infinite 3D wireframe ground grid."""
        # Horizontal lines of the grid moving toward the viewer
        spacing_z = 80.0
        self.terrain_offset = (self.terrain_offset + self.speed) % spacing_z

        for i in range(1, 15):
            z = (i * spacing_z) - self.terrain_offset
            if z <= 20.0: continue
            sx0, sy0 = self.project_3d(-600 - self.ship_x, -self.ship_y, z)
            sx1, sy1 = self.project_3d( 600 - self.ship_x, -self.ship_y, z)
            self.draw_line(sx0, sy0, sx1, sy1, COLOR_GRID)

        # Longitudinal perspective lines converging toward horizon
        for x_val in range(-600, 601, 150):
            sx0, sy0 = self.project_3d(x_val - self.ship_x, -self.ship_y, 40.0)
            sx1, sy1 = self.project_3d(x_val - self.ship_x, -self.ship_y, 1200.0)
            self.draw_line(sx0, sy0, sx1, sy1, COLOR_GRID)

        # Horizon Line
        hx0, hy0 = 0, int(HALF_H + (self.ship_y * FOCAL_LEN) / 1500)
        hx1, hy1 = SCREEN_W - 1, hy0
        self.draw_line(hx0, hy0, hx1, hy1, COLOR_HORIZON)

    def render_starfield(self):
        """Renders 3D warp star particles flying past."""
        for s in self.stars:
            s["z"] -= self.speed * s["speed"]
            if s["z"] <= 20:
                s["z"] = random.uniform(1000, 1500)
                s["x"] = random.uniform(-400, 400) + self.ship_x
                s["y"] = random.uniform(-100, 300)

            sx, sy = self.project_3d(s["x"] - self.ship_x, s["y"] - self.ship_y, s["z"])
            if sx is not None and 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
                off = (sy * SCREEN_W + sx) * 4
                self.fb[off:off+4] = b"\xFF\xFF\xFF\x00"

    def render_gates(self):
        """Renders 3D octagonal navigation rings in 3D space."""
        for gate in self.gates:
            gate["z"] -= self.speed
            rel_x = gate["x"] - self.ship_x
            rel_y = gate["y"] - self.ship_y
            rel_z = gate["z"]

            # Check passage through ring
            if -self.speed <= rel_z <= self.speed and not gate["hit"]:
                dist = math.hypot(rel_x, rel_y)
                if dist <= gate["radius"]:
                    gate["hit"] = True
                    self.score += 100
                    self.rings_cleared += 1
                    # Play MMIO victory chime
                    self.vm.write32(0x10000050, 880) # 880 Hz (A5)
                    self.vm.write32(0x10000054, 80)

            # Reset ring if behind player
            if rel_z <= 20:
                gate["z"] = 2000
                gate["x"] = self.ship_x + random.uniform(-200, 200)
                gate["y"] = random.uniform(20, 140)
                gate["hit"] = False
                continue

            # Render 3D Octagon
            num_sides = 8
            pts = []
            for i in range(num_sides):
                angle = (i * 2 * math.pi) / num_sides
                px = rel_x + gate["radius"] * math.cos(angle)
                py = rel_y + gate["radius"] * math.sin(angle)
                sx, sy = self.project_3d(px, py, rel_z)
                pts.append((sx, sy))

            color = COLOR_RING_HIT if gate["hit"] else COLOR_RING
            for i in range(num_sides):
                p1 = pts[i]
                p2 = pts[(i + 1) % num_sides]
                self.draw_line(p1[0], p1[1], p2[0], p2[1], color)

    def render_player_ship(self):
        """Renders the player's 3D wireframe Starfighter."""
        # Ship geometry centered at bottom of screen
        cx, cy = HALF_W, SCREEN_H - 90

        # Bank rotation
        cos_b = math.cos(self.bank)
        sin_b = math.sin(self.bank)

        def rot(lx, ly):
            rx = lx * cos_b - ly * sin_b
            ry = lx * sin_b + ly * cos_b
            return int(cx + rx), int(cy + ry)

        # Starfighter Vertices
        nose   = rot(0, -35)
        cockpit= rot(0, -10)
        tail   = rot(0, 20)
        wing_l = rot(-55, 12)
        wing_r = rot(55, 12)
        fin_l  = rot(-20, 25)
        fin_r  = rot(20, 25)

        # Draw Ship Wireframe
        self.draw_line(nose[0], nose[1], wing_l[0], wing_l[1], COLOR_SHIP)
        self.draw_line(nose[0], nose[1], wing_r[0], wing_r[1], COLOR_SHIP)
        self.draw_line(wing_l[0], wing_l[1], cockpit[0], cockpit[1], COLOR_WING)
        self.draw_line(wing_r[0], wing_r[1], cockpit[0], cockpit[1], COLOR_WING)
        self.draw_line(cockpit[0], cockpit[1], tail[0], tail[1], COLOR_SHIP)
        self.draw_line(wing_l[0], wing_l[1], fin_l[0], fin_l[1], COLOR_SHIP)
        self.draw_line(wing_r[0], wing_r[1], fin_r[0], fin_r[1], COLOR_SHIP)
        self.draw_line(fin_l[0], fin_l[1], tail[0], tail[1], COLOR_WING)
        self.draw_line(fin_r[0], fin_r[1], tail[0], tail[1], COLOR_WING)

        # Twin afterburners
        ab_l = rot(-10, 28)
        ab_r = rot(10, 28)
        self.draw_line(fin_l[0], fin_l[1], ab_l[0], ab_l[1], 0x00F7768E)
        self.draw_line(fin_r[0], fin_r[1], ab_r[0], ab_r[1], 0x00F7768E)

    def render_hud(self):
        """Draws 3D flight HUD (pitch ladder, flight indicators)."""
        # Crosshair reticle in center
        self.draw_line(HALF_W - 15, HALF_H, HALF_W - 5, HALF_H, COLOR_HUD)
        self.draw_line(HALF_W + 5, HALF_H, HALF_W + 15, HALF_H, COLOR_HUD)
        self.draw_line(HALF_W, HALF_H - 15, HALF_W, HALF_H - 5, COLOR_HUD)
        self.draw_line(HALF_W, HALF_H + 5, HALF_W, HALF_H + 15, COLOR_HUD)

        # Artificial Horizon Pitch Bars
        cos_b = math.cos(self.bank)
        sin_b = math.sin(self.bank)
        pitch_offset = int(self.pitch * 120)

        for deg in (-20, -10, 10, 20):
            bar_y = HALF_H + pitch_offset - deg * 3
            bar_len = 30
            x1 = int(HALF_W - bar_len * cos_b)
            y1 = int(bar_y - bar_len * sin_b)
            x2 = int(HALF_W + bar_len * cos_b)
            y2 = int(bar_y + bar_len * sin_b)
            self.draw_line(x1, y1, x2, y2, COLOR_HUD)

    def step_frame(self, mouse_x, mouse_y):
        """Advances simulation by one frame with player mouse controls."""
        # Clear screen to Deep Space Navy
        c_bytes = bytes([COLOR_BG & 0xFF, (COLOR_BG >> 8) & 0xFF, (COLOR_BG >> 16) & 0xFF, (COLOR_BG >> 24) & 0xFF])
        self.fb[:] = c_bytes * (SCREEN_W * SCREEN_H)

        # Calculate steering delta based on mouse offset from center
        dx = (mouse_x - HALF_W) / HALF_W
        dy = (mouse_y - HALF_H) / HALF_H

        # Update ship attitude
        self.bank = dx * 0.7
        self.ship_x += dx * 7.0
        self.pitch = -dy * 0.5
        self.ship_y = max(15.0, min(160.0, self.ship_y - dy * 4.0))

        # Render 3D Pipeline
        self.render_starfield()
        self.render_terrain()
        self.render_gates()
        self.render_player_ship()
        self.render_hud()
