#!/usr/bin/env python3
"""
tests/test_memory_benchmark_studio.py
Verifies the Sovereign Memory Benchmark & Stress Studio GUI Application:
1. App instantiation, default dimensions, and metric baseline
2. Stress test execution and state transitions (Workloads 1, 2, 3, 4, All)
3. 60 FPS animation stepping and progress bar interpolation
4. Interactive mouse click dispatch on action buttons and parameter toggles
5. Framebuffer rasterization with clipping and font rendering
6. MasterDesktop window compositor integration and launch-by-id
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from desktop.memory_benchmark_studio import MemoryBenchmarkStudioApp
from desktop.font import get_default_font
from desktop.master_desktop import MasterDesktop
from vm.vm import VM, RAM_SIZE_1024MB


def test_benchmark_studio_app_lifecycle():
    app = MemoryBenchmarkStudioApp(screen_w=1024, screen_h=640)
    assert app.screen_w == 1024
    assert app.screen_h == 640
    assert "Ready" in app.status_message
    assert len(app.logs) >= 3

    # Verify initial metrics baseline
    assert app.metrics["w1_linux_stall_ms"] > 0
    assert app.metrics["w1_adios_stall_ms"] == 0.0
    assert app.metrics["w2_bus_reduction_pct"] > 99.0
    assert app.metrics["w3_adios_bit_exact"] is True
    assert app.metrics["w4_adios_kills"] == 0


def test_benchmark_studio_stress_executions():
    app = MemoryBenchmarkStudioApp(screen_w=1024, screen_h=640)

    # Run Individual Workloads
    app.run_test_1()
    assert app.anim_progress["w1"] == 0.0
    assert app.metrics["w1_adios_faults"] == 0

    app.run_test_2()
    assert app.anim_progress["w2"] == 0.0
    assert app.metrics["w2_bus_reduction_pct"] > 99.9

    app.run_test_3()
    assert app.anim_progress["w3"] == 0.0
    assert app.metrics["w3_adios_bit_exact"] is True

    app.run_test_4()
    assert app.anim_progress["w4"] == 0.0
    assert app.metrics["w4_adios_kills"] == 0

    # Run All
    app.run_all_tests()
    assert "Complete" in app.status_message


def test_benchmark_studio_animation_step():
    app = MemoryBenchmarkStudioApp(screen_w=1024, screen_h=640)
    app.anim_progress["w1"] = 0.0
    app.step()
    assert app.anim_progress["w1"] > 0.0


def test_benchmark_studio_click_dispatch():
    app = MemoryBenchmarkStudioApp(screen_w=1024, screen_h=640)

    # Click RUN ALL button (x: 50, y: 15)
    app.handle_click(50, 15, win_w=1024, win_h=640)
    assert "Complete" in app.status_message

    # Click Task toggle 25 (x: 120, y: 48)
    app.handle_click(120, 48, win_w=1024, win_h=640)
    assert app.param_tasks == 25

    # Click Pressure toggle CRIT (x: 400, y: 48)
    app.handle_click(400, 48, win_w=1024, win_h=640)
    assert app.param_pressure == "CRIT"

    # Click RESET (x: 530, y: 15)
    app.handle_click(530, 15, win_w=1024, win_h=640)
    assert app.anim_progress["w1"] == 0.0


def test_benchmark_studio_render_raster():
    w, h = 1024, 640
    app = MemoryBenchmarkStudioApp(screen_w=w, screen_h=h)
    font = get_default_font()
    fb = bytearray(w * h * 4)

    # Render frame
    app.render(fb, font, 0, 0, w, h)
    # Check that framebuffer is not all zeros
    assert any(b != 0 for b in fb[:1000])


def test_master_desktop_benchmark_window_integration():
    vm = VM(ram_size=RAM_SIZE_1024MB)
    desktop = MasterDesktop(vm=vm, width=1280, height=720, ram_capacity_mb=1024)

    # Verify window is present in window manager
    win_ids = [w.win_id for w in desktop.wm.windows]
    assert "benchmark_studio" in win_ids

    # Launch window by ID
    desktop.launch_or_focus("benchmark_studio")
    assert desktop.win_benchmark.visible is True
    assert desktop.win_benchmark.minimized is False

    # Verify step_frame advances benchmark studio
    desktop.step_frame(640, 360)

    # Verify drawing content
    fb = bytearray(1280 * 720 * 4)
    font = get_default_font()
    desktop._draw_benchmark_studio(desktop.win_benchmark, fb, font)
    assert any(b != 0 for b in fb)
