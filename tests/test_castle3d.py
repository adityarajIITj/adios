#!/usr/bin/env python3
"""
Test Suite: CastleAdiOS 3D Raycasting Game
Verifies:
1. DDA raycasting distance calculations
2. Player movement and collision detection
3. Framebuffer rendering (walls, floor, ceiling, and minimap)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from games.castle3d import CastleAdiOS3D, DUNGEON_MAP

def test_castle3d_suite():
    print("[Test Castle3D] Testing CastleAdiOS 3D Raycaster Engine...")
    vm = VM()
    game = CastleAdiOS3D(vm)

    # 1. Test Raycasting DDA
    print("  -> Testing DDA ray calculation...")
    # Cast center ray (ray 160 out of 320)
    dist, lh, start_y, end_y, tile, side = game.cast_ray(160)
    assert dist > 0.0, f"Ray distance should be positive, got {dist}"
    assert lh > 0, f"Line height should be positive, got {lh}"
    assert 0 <= start_y <= end_y < 480, f"Invalid vertical slice bounds: ({start_y}, {end_y})"
    assert tile > 0, f"Center ray hit non-wall: {tile}"
    print(f"  -> Center Ray (r=160): dist={dist:.2f}, height={lh}, tile={tile}, side={side}")
    print("  -> [PASS] DDA raycasting verified.")

    # 2. Test Player Movement & Rotation
    print("  -> Testing player movement and collision...")
    init_x, init_y = game.pos_x, game.pos_y
    # Move forward (+X along corridor at row 1)
    game.move_forward(0.5)
    assert game.pos_x > init_x, "Player failed to move forward in corridor"

    # Rotate 90 degrees
    game.rotate(1.5708)

    # Collision test: attempt to walk through outer boundary wall (y=0)
    game.pos_x = 1.5
    game.pos_y = 1.1
    game.dir_x = 0.0
    game.dir_y = -1.0 # Facing outer wall
    game.move_forward(0.5)
    assert game.pos_y == 1.1, "Collision detection failed (walked into wall!)"
    print("  -> [PASS] Movement and collision verified.")

    # 3. Test Framebuffer Rendering
    print("  -> Testing full Framebuffer rendering and HUD...")
    game.pos_x = 1.5
    game.pos_y = 1.5
    game.dir_x = 1.0
    game.dir_y = 0.0
    game.render_frame(mouse_dx=0)

    # Check ceiling pixel (y=50, x=320)
    ceil_off = (50 * 640 + 320) * 4
    ceil_bytes = list(vm.fb[ceil_off : ceil_off + 4])
    assert ceil_bytes == [0x1F, 0x23, 0x35, 0], f"Ceiling pixel mismatch: {ceil_bytes}"

    # Check floor pixel (y=400, x=320)
    floor_off = (400 * 640 + 320) * 4
    floor_bytes = list(vm.fb[floor_off : floor_off + 4])
    assert floor_bytes == [0x16, 0x16, 0x1E, 0], f"Floor pixel mismatch: {floor_bytes}"

    # Check Minimap pixel (top right area: y=50, x=550)
    map_off = (50 * 640 + 550) * 4
    map_bytes = list(vm.fb[map_off : map_off + 4])
    assert any(b > 0 for b in map_bytes), "Minimap pixel was not drawn"
    print(f"  -> Framebuffer verified (Ceil: {ceil_bytes}, Floor: {floor_bytes}, Minimap: {map_bytes})")

    print("\n[Test Castle3D] ALL CASTLEADIOS 3D TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_castle3d_suite()
