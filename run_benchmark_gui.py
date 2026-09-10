#!/usr/bin/env python3
"""
run_benchmark_gui.py - Linux Kernel Memory Benchmark & Stress Studio Launcher
Launches the standalone interactive 60 FPS GUI window with:
- Interactive toggleable stress test buttons
- Side-by-side Linux without FluidRAM vs Linux with FluidRAM comparative bar graphs
- Real-time telemetry log console with microsecond timestamps
- Live parameter adjustments (Task count, pressure levels)

Usage:
  python run_benchmark_gui.py                 # Interactive 60 FPS Pygame GUI
  python run_benchmark_gui.py --screenshot    # Renders high-res screenshot to docs/assets/
"""

import sys
import os
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from desktop.memory_benchmark_studio import MemoryBenchmarkStudioApp
from desktop.font import get_default_font

WIDTH = 1024
HEIGHT = 640
FPS = 60

def render_screenshot_png(output_path: str = "docs/assets/adios_gui_benchmark_studio.png"):
    """Renders a pixel-perfect frame of the Benchmark Studio and saves to PNG."""
    from PIL import Image

    app = MemoryBenchmarkStudioApp(screen_w=WIDTH, screen_h=HEIGHT)
    font = get_default_font()
    fb = bytearray(WIDTH * HEIGHT * 4)

    # Trigger test 1 and test 4 to populate live metrics
    app.run_all_tests()
    # Step simulation to advance animation bars to full
    for _ in range(60):
        app.step()

    app.render(fb, font, 0, 0, WIDTH, HEIGHT)

    # Convert BGRA bytearray to RGBA image
    # Note: in BGRA, byte 0 is B, byte 1 is G, byte 2 is R, byte 3 is A
    img_bytes = bytearray(WIDTH * HEIGHT * 4)
    for i in range(0, len(fb), 4):
        b = fb[i]
        g = fb[i + 1]
        r = fb[i + 2]
        a = fb[i + 3]
        img_bytes[i] = r
        img_bytes[i + 1] = g
        img_bytes[i + 2] = b
        img_bytes[i + 3] = a

    img = Image.frombytes("RGBA", (WIDTH, HEIGHT), bytes(img_bytes))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    print(f"[Benchmark Studio] Screenshot saved successfully: {output_path}")

def main():
    if "--screenshot" in sys.argv or "--render" in sys.argv:
        render_screenshot_png()
        return

    try:
        import pygame
    except ImportError:
        print("[Error] Pygame is required for interactive window. Run: pip install pygame")
        print("[Alternative] Rendering high-res screenshot to docs/assets/adios_gui_benchmark_studio.png...")
        render_screenshot_png()
        return

    pygame.init()
    pygame.display.set_caption("Linux Kernel Memory Benchmark: With FluidRAM vs Without FluidRAM (60 FPS)")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    font = get_default_font()
    fb = bytearray(WIDTH * HEIGHT * 4)
    app = MemoryBenchmarkStudioApp(screen_w=WIDTH, screen_h=HEIGHT)

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    app.handle_click(event.pos[0], event.pos[1], win_w=WIDTH, win_h=HEIGHT)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    app.run_test_1()
                elif event.key == pygame.K_2:
                    app.run_test_2()
                elif event.key == pygame.K_3:
                    app.run_test_3()
                elif event.key == pygame.K_4:
                    app.run_test_4()
                elif event.key == pygame.K_a or event.key == pygame.K_SPACE:
                    app.run_all_tests()
                elif event.key == pygame.K_r:
                    app.reset_metrics()

        # Step 60 FPS animations
        app.step()

        # Render application into framebuffer
        app.render(fb, font, 0, 0, WIDTH, HEIGHT)

        # Blit BGRA buffer to screen
        surf = pygame.image.frombuffer(fb, (WIDTH, HEIGHT), "BGRA")
        surf.set_alpha(None)
        screen.blit(surf, (0, 0))
        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
