#!/usr/bin/env python3
"""
AdiOS Sovereign Workstation 1280x720 HD 60 FPS Launcher
Launches the full interactive sovereign desktop with:
- Minimalist Modern Theme Engine (Nordic, Mono, Arctic, Emerald)
- In-OS Code Studio with online PyPI package manager (pip install)
- AdioFiles dual-pane visual file explorer
- Interactive 3D Spatial Scene Studio with mouse drag rotation
- Sovereign YouTube player with 32-band audio spectrum visualizer
- Top taskbar with window switcher, minimization, and system telemetry

Strict zero emoji policy.
"""

import sys
import os
import time

try:
    import pygame
except ImportError:
    print("Error: Pygame is required to run the interactive AdiOS workstation window.")
    print("Install via: pip install pygame")
    sys.exit(1)

from desktop.master_desktop import MasterDesktop
from vm.vm import VM, RAM_SIZE_512MB
from vm.vpu import VideoProcessingUnit

WIDTH = 1280
HEIGHT = 720
FPS = 60

def main():
    pygame.init()
    pygame.display.set_caption("AdiOS Sovereign Workstation (1280x720 HD @ 60 FPS)")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Initialize Bare-Metal Hardware Simulation
    vm = VM(ram_size=RAM_SIZE_512MB)
    vm.vpu = VideoProcessingUnit(vm)
    fb = bytearray(WIDTH * HEIGHT * 4)

    # Initialize Sovereign Master Desktop Compositor
    desktop = MasterDesktop(vm=vm, width=WIDTH, height=HEIGHT, ram_capacity_mb=512)

    running = True
    last_mouse_pos = (0, 0)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEMOTION:
                last_mouse_pos = event.pos
                desktop.handle_mouse_move(event.pos[0], event.pos[1])
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    desktop.handle_mouse_down(event.pos[0], event.pos[1])
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    desktop.handle_mouse_up(event.pos[0], event.pos[1])
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    running = False
                elif event.unicode:
                    desktop.handle_key(event.unicode)

        # Step frame simulations (animations, 3D rotations, media playback)
        desktop.step_frame(last_mouse_pos[0], last_mouse_pos[1])

        # Composite frame to framebuffer
        desktop.render(fb)

        # Blit 32-bit BGRA framebuffer directly with full opacity
        surf = pygame.image.frombuffer(fb, (WIDTH, HEIGHT), "BGRA")
        surf.set_alpha(None)
        screen.blit(surf, (0, 0))
        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
