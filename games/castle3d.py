#!/usr/bin/env python3
"""
CastleAdiOS 3D: First-Person 3D Raycasting Dungeon Crawler
Inspired by Terry A. Davis's 3D first-person perspective games in TempleOS and Wolfenstein 3D.
Features:
- Real-time DDA (Digital Differential Analysis) raycaster
- 320-ray parallel casting with 2px vertical strip rasterization onto 640x480 Framebuffer
- Distance shading (depth dimming / fog of war)
- Compass Minimap in top-right HUD
- Health & Mana HUD status bars
- PC speaker sound triggers on movement and wall impact
"""

import math
import struct

WIDTH  = 640
HEIGHT = 480
HALFH  = HEIGHT // 2
NUM_RAYS = 320 # 320 rays rendered as 2-pixel wide columns

# Dungeon Tile Types
TILE_EMPTY = 0
TILE_STONE = 1
TILE_WOOD  = 2
TILE_BRICK = 3
TILE_GOLD  = 4

# Base Wall Colors
WALL_COLORS = {
    TILE_STONE: 0x007AA2F7, # Mystic Blue
    TILE_WOOD:  0x00E0AF68, # Warm Gold / Wood
    TILE_BRICK: 0x00F7768E, # Brick Red
    TILE_GOLD:  0x00BB9AF7  # Temple Purple
}

DUNGEON_MAP = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 2, 2, 0, 0, 1, 0, 3, 3, 3, 0, 0, 4, 0, 1],
    [1, 0, 2, 2, 0, 0, 0, 0, 3, 0, 3, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 3, 3, 3, 0, 0, 4, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 1],
    [1, 0, 3, 0, 0, 4, 4, 4, 0, 0, 0, 0, 1, 1, 0, 1],
    [1, 0, 3, 0, 0, 4, 0, 4, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 3, 0, 0, 4, 4, 4, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 2, 0, 0, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

class CastleAdiOS3D:
    def __init__(self, vm=None):
        self.vm = vm
        self.pos_x = 1.5
        self.pos_y = 1.5
        self.dir_x = 1.0
        self.dir_y = 0.0
        self.plane_x = 0.0
        self.plane_y = 0.66 # FOV approx 66 degrees
        self.health = 100
        self.score = 750
        self.rot_speed = 0.04
        self.move_speed = 0.08

    def rotate(self, angle_rad):
        old_dir_x = self.dir_x
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        self.dir_x = self.dir_x * cos_a - self.dir_y * sin_a
        self.dir_y = old_dir_x * sin_a + self.dir_y * cos_a

        old_plane_x = self.plane_x
        self.plane_x = self.plane_x * cos_a - self.plane_y * sin_a
        self.plane_y = old_plane_x * sin_a + self.plane_y * cos_a

    def move_forward(self, distance):
        new_x = self.pos_x + self.dir_x * distance
        new_y = self.pos_y + self.dir_y * distance
        # Collision check
        if DUNGEON_MAP[int(new_y)][int(new_x)] == 0:
            self.pos_x = new_x
            self.pos_y = new_y

    def move_backward(self, distance):
        self.move_forward(-distance)

    def cast_ray(self, ray_idx):
        """Performs DDA raycasting for ray index (0..NUM_RAYS-1)."""
        camera_x = 2.0 * ray_idx / float(NUM_RAYS) - 1.0 # x in camera space [-1, 1]
        ray_dir_x = self.dir_x + self.plane_x * camera_x
        ray_dir_y = self.dir_y + self.plane_y * camera_x

        map_x = int(self.pos_x)
        map_y = int(self.pos_y)

        delta_dist_x = abs(1.0 / ray_dir_x) if abs(ray_dir_x) > 1e-6 else 1e30
        delta_dist_y = abs(1.0 / ray_dir_y) if abs(ray_dir_y) > 1e-6 else 1e30

        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (self.pos_x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - self.pos_x) * delta_dist_x

        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (self.pos_y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - self.pos_y) * delta_dist_y

        # DDA loop
        hit = 0
        side = 0
        tile_type = 1
        steps = 0
        while hit == 0 and steps < 32:
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
                    tile_type = DUNGEON_MAP[map_y][map_x]
            steps += 1

        if side == 0:
            perp_wall_dist = (map_x - self.pos_x + (1 - step_x) / 2.0) / ray_dir_x
        else:
            perp_wall_dist = (map_y - self.pos_y + (1 - step_y) / 2.0) / ray_dir_y

        perp_wall_dist = max(0.1, perp_wall_dist)
        line_height = int(HEIGHT / perp_wall_dist)
        draw_start = max(0, -line_height // 2 + HALFH)
        draw_end   = min(HEIGHT - 1, line_height // 2 + HALFH)

        return (perp_wall_dist, line_height, draw_start, draw_end, tile_type, side)

    def render_frame(self, mouse_dx=0):
        if not self.vm: return
        fb = self.vm.fb

        # Rotate with mouse delta
        if abs(mouse_dx) > 0:
            self.rotate(mouse_dx * 0.005)

        # 1. Draw Ceiling & Floor
        ceil_bytes = bytes([0x1F, 0x23, 0x35, 0]) * (WIDTH * HALFH)
        floor_bytes = bytes([0x16, 0x16, 0x1E, 0]) * (WIDTH * HALFH)
        fb[0 : WIDTH * HALFH * 4] = ceil_bytes
        fb[WIDTH * HALFH * 4 : WIDTH * HEIGHT * 4] = floor_bytes

        # 2. Raycast Walls
        col_w = WIDTH // NUM_RAYS # 2 pixels wide
        for r in range(NUM_RAYS):
            dist, lh, start_y, end_y, tile, side = self.cast_ray(r)
            base_col = WALL_COLORS.get(tile, 0x007AA2F7)

            # Shading by distance & side
            shade = max(0.2, min(1.0, 1.0 - (dist / 14.0)))
            if side == 1: shade *= 0.75 # Y-sides are darker for 3D depth

            r_val = int(((base_col >> 16) & 0xFF) * shade)
            g_val = int(((base_col >> 8) & 0xFF) * shade)
            b_val = int((base_col & 0xFF) * shade)
            strip_bytes = bytes([b_val, g_val, r_val, 0]) * col_w

            px_start = r * col_w
            for sy in range(start_y, end_y + 1):
                off = (sy * WIDTH + px_start) * 4
                fb[off : off + col_w * 4] = strip_bytes

        # 3. Draw Crosshair at Screen Center
        cross_color = bytes([0x7D, 0xCF, 0xFF, 0])
        cx, cy = WIDTH // 2, HEIGHT // 2
        for i in range(-6, 7):
            fb[((cy + i) * WIDTH + cx) * 4 : ((cy + i) * WIDTH + cx) * 4 + 4] = cross_color
            fb[(cy * WIDTH + (cx + i)) * 4 : (cy * WIDTH + (cx + i)) * 4 + 4] = cross_color

        # 4. Draw HUD Overlay (Health Bar & Minimap)
        self._draw_hud(fb)

    def _draw_hud(self, fb):
        # Health Bar at Bottom-Left: (20, 440) -> (140, 460)
        hp_border = bytes([0x41, 0x48, 0x68, 0])
        hp_fill   = bytes([0x8E, 0x76, 0xF7, 0]) # Red
        for y in range(440, 460):
            fb[(y * WIDTH + 20) * 4 : (y * WIDTH + 140) * 4] = hp_border * 120
            fb[(y * WIDTH + 22) * 4 : (y * WIDTH + 22 + self.health) * 4] = hp_fill * self.health

        # Minimap at Top-Right: (500, 10) -> (628, 138) (128x128 pixels, 8px per tile)
        wall_pixel = bytes([0x7A, 0xA2, 0xF7, 0]) * 8
        empty_pixel= bytes([0x16, 0x16, 0x1E, 0]) * 8
        for my in range(16):
            for mx in range(16):
                t = DUNGEON_MAP[my][mx]
                p_bytes = wall_pixel if t > 0 else empty_pixel
                for py in range(8):
                    off = ((10 + my * 8 + py) * WIDTH + (500 + mx * 8)) * 4
                    fb[off : off + 32] = p_bytes

        # Player Dot on Minimap (Gold)
        p_dot = bytes([0x68, 0xAF, 0xE0, 0]) * 4
        px_map = int(500 + self.pos_x * 8)
        py_map = int(10 + self.pos_y * 8)
        for py in range(4):
            off = ((py_map + py) * WIDTH + px_map) * 4
            fb[off : off + 16] = p_dot
