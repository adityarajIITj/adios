#!/usr/bin/env python3
"""
Render live 1280x720 HD AdiOS v4.0 Beta Screenshots.
Saves PNG to docs/assets/ and brain artifacts.
Pure Python + zlib (zero external dependencies).
"""

import sys
import os
import struct
import zlib
import time

sys.path.insert(0, os.path.abspath(r"C:\Users\adity\.gemini\antigravity-ide\scratch\adios"))

from vm.vm import VM, RAM_SIZE_1024MB
from vm.vpu import VideoProcessingUnit
from desktop.master_desktop import MasterDesktop
from kernel.fluid_ram import (
    get_fluid_ram_mesh,
    POOL_KERNEL_CORE,
    POOL_COMPOSITOR_FB,
    POOL_STREAM_RING,
    POOL_CHRONOS_DELTA,
    POOL_USER_APPS,
    POOL_DYNAMIC_MESH
)

def save_png(width, height, rgb_data, filepath):
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    raw_lines = []
    for y in range(height):
        start = y * width * 3
        raw_lines.append(b"\x00" + rgb_data[start : start + width * 3])
    compressed = zlib.compress(b"".join(raw_lines), 9)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(png_bytes)
    print("Saved PNG file successfully.")


def render_v4_workstation():
    width, height = 1280, 720
    vm = VM(ram_size=RAM_SIZE_1024MB)
    vm.vpu = VideoProcessingUnit(vm)
    fb = bytearray(width * height * 4)

    desktop = MasterDesktop(vm, width=width, height=height, ram_capacity_mb=1024)

    # Initialize FluidRAM with some active process allocations
    mesh = get_fluid_ram_mesh()
    mesh.pools[POOL_USER_APPS].used_mb = 112.0
    mesh.pools[POOL_DYNAMIC_MESH].used_mb = 48.0
    mesh.pools[POOL_STREAM_RING].used_mb = 3.9
    mesh.wave_pulse_phase = 1.8

    # Open Code Studio in background
    desktop.launch_or_focus("studio")
    desktop.win_studio.x = 80
    desktop.win_studio.y = 50
    desktop.win_studio.w = 580
    desktop.win_studio.h = 440

    # Open FluidRAM Oscilloscope in foreground
    desktop.launch_or_focus("fluid_ram")
    desktop.win_fluid.x = 440
    desktop.win_fluid.y = 70
    desktop.win_fluid.w = 790
    desktop.win_fluid.h = 560

    # Hover over FluidRAM desktop icon on the left
    fluid_icon = [i for i in desktop.icons.icons if i.icon_id == "fluid_ram"][0]
    fluid_icon.selected = True

    # Step simulation frames to get rich wave dynamics
    for _ in range(30):
        desktop.step_frame(600, 300)

    desktop.render(fb)

    # Convert BGRX to RGB
    rgb = bytearray(width * height * 3)
    rgb[0::3] = fb[2::4]  # Red
    rgb[1::3] = fb[1::4]  # Green
    rgb[2::3] = fb[0::4]  # Blue

    # Save to scratch docs/assets
    p1 = r"C:\Users\adity\.gemini\antigravity-ide\scratch\adios\docs\assets\adios_v4_beta_workstation.png"
    save_png(width, height, rgb, p1)

    # Save to git docs/assets
    p2 = r"C:\Users\adity\OneDrive\文档\adios\docs\assets\adios_v4_beta_workstation.png"
    save_png(width, height, rgb, p2)

    # Save to artifacts directory for inspection
    p3 = r"C:\Users\adity\.gemini\antigravity-ide\brain\5d018b15-41a1-466c-8c1d-f3083c26a742\adios_v4_beta_workstation.png"
    save_png(width, height, rgb, p3)


def render_v4_soundtracker():
    width, height = 1280, 720
    vm = VM(ram_size=RAM_SIZE_1024MB)
    vm.vpu = VideoProcessingUnit(vm)
    fb = bytearray(width * height * 4)

    desktop = MasterDesktop(vm, width=width, height=height, ram_capacity_mb=1024)

    # Open SoundTracker in center
    desktop.launch_or_focus("tracker")
    desktop.win_tracker.x = 220
    desktop.win_tracker.y = 80
    desktop.win_tracker.w = 840
    desktop.win_tracker.h = 560

    for _ in range(15):
        desktop.step_frame(400, 300)

    desktop.render(fb)

    rgb = bytearray(width * height * 3)
    rgb[0::3] = fb[2::4]
    rgb[1::3] = fb[1::4]
    rgb[2::3] = fb[0::4]

    p1 = r"C:\Users\adity\.gemini\antigravity-ide\scratch\adios\docs\assets\adios_v4_beta_soundtracker.png"
    save_png(width, height, rgb, p1)
    p2 = r"C:\Users\adity\OneDrive\文档\adios\docs\assets\adios_v4_beta_soundtracker.png"
    save_png(width, height, rgb, p2)
    p3 = r"C:\Users\adity\.gemini\antigravity-ide\brain\5d018b15-41a1-466c-8c1d-f3083c26a742\adios_v4_beta_soundtracker.png"
    save_png(width, height, rgb, p3)


def render_v4_fluid_ram():
    width, height = 1280, 720
    vm = VM(ram_size=RAM_SIZE_1024MB)
    vm.vpu = VideoProcessingUnit(vm)
    fb = bytearray(width * height * 4)

    desktop = MasterDesktop(vm, width=width, height=height, ram_capacity_mb=1024)

    mesh = get_fluid_ram_mesh()
    mesh.pools[POOL_USER_APPS].used_mb = 145.0
    mesh.pools[POOL_DYNAMIC_MESH].used_mb = 64.0
    mesh.pools[POOL_STREAM_RING].used_mb = 3.9
    mesh.wave_pulse_phase = 2.4

    # Center FluidRAM window
    desktop.launch_or_focus("fluid_ram")
    desktop.win_fluid.x = 240
    desktop.win_fluid.y = 65
    desktop.win_fluid.w = 800
    desktop.win_fluid.h = 570

    # Trigger cell inspection on cell 512
    desktop.fluid_oscilloscope.selected_cell_index = 512
    matrix = mesh.get_topology_matrix()
    cell_data = matrix[16][0]
    desktop.fluid_oscilloscope.selected_cell_info = {
        "index": 512,
        "address_hex": "0x20000000",
        "pool": cell_data["pool"],
        "pressure": cell_data["pressure"],
        "tension": cell_data["tension"]
    }
    desktop.fluid_oscilloscope.status_message = "Inspecting 1 MB Page #512 (USER_APPS) at 0x20000000 [Laminar Equilibrium]"

    for _ in range(20):
        desktop.step_frame(500, 300)

    desktop.render(fb)

    rgb = bytearray(width * height * 3)
    rgb[0::3] = fb[2::4]
    rgb[1::3] = fb[1::4]
    rgb[2::3] = fb[0::4]

    p1 = r"C:\Users\adity\.gemini\antigravity-ide\scratch\adios\docs\assets\adios_v4_beta_fluid_ram.png"
    save_png(width, height, rgb, p1)
    p2 = r"C:\Users\adity\OneDrive\文档\adios\docs\assets\adios_v4_beta_fluid_ram.png"
    save_png(width, height, rgb, p2)
    p3 = r"C:\Users\adity\.gemini\antigravity-ide\brain\5d018b15-41a1-466c-8c1d-f3083c26a742\adios_v4_beta_fluid_ram.png"
    save_png(width, height, rgb, p3)


if __name__ == "__main__":
    print("Rendering AdiOS v4.0 Beta Workstation...")
    render_v4_workstation()
    print("Rendering AdiOS v4.0 Beta FluidRAM Oscilloscope...")
    render_v4_fluid_ram()
    print("Rendering AdiOS v4.0 Beta SoundTracker...")
    render_v4_soundtracker()
    print("Done!")
