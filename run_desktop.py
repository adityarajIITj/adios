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
from vm.vm import VM, RAM_SIZE_1024MB
from vm.vpu import VideoProcessingUnit

WIDTH = 1280
HEIGHT = 720
FPS = 60

def main():
    pygame.init()
    pygame.display.set_caption("AdiOS Sovereign Workstation (1280x720 HD @ 60 FPS)")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Initialize Bare-Metal Hardware Simulation with 1024 MB (1.0 GB) RAM
    vm = VM(ram_size=RAM_SIZE_1024MB)
    vm.vpu = VideoProcessingUnit(vm)
    fb = bytearray(WIDTH * HEIGHT * 4)

    # Initialize Sovereign Master Desktop Compositor
    desktop = MasterDesktop(vm=vm, width=WIDTH, height=HEIGHT, ram_capacity_mb=1024)
    if hasattr(desktop, "sound_server") and hasattr(desktop.sound_server, "start"):
        desktop.sound_server.start()

    running = True
    last_mouse_pos = (WIDTH // 2, HEIGHT // 2)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEMOTION:
                last_mouse_pos = event.pos
                desktop.handle_mouse_move(event.pos[0], event.pos[1])
            elif event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    desktop.handle_key("SCROLL_UP")
                elif event.y < 0:
                    desktop.handle_key("SCROLL_DOWN")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    desktop.handle_mouse_down(event.pos[0], event.pos[1])
                elif event.button == 4:
                    desktop.handle_key("SCROLL_UP")
                elif event.button == 5:
                    desktop.handle_key("SCROLL_DOWN")
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    desktop.handle_mouse_up(event.pos[0], event.pos[1])
            elif event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl_held = bool(mods & (pygame.KMOD_CTRL | pygame.KMOD_META))
                alt_held = bool(mods & pygame.KMOD_ALT)
                shift_held = bool(mods & pygame.KMOD_SHIFT)

                if event.key == pygame.K_ESCAPE and shift_held:
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    desktop.handle_key("ESCAPE")
                elif ctrl_held and shift_held and event.key == pygame.K_k:
                    desktop.handle_key("CTRL_SHIFT_K")
                elif ctrl_held and event.key == pygame.K_a:
                    desktop.handle_key("CTRL_A")
                elif ctrl_held and event.key == pygame.K_c:
                    desktop.handle_key("CTRL_C")
                elif ctrl_held and event.key == pygame.K_v:
                    desktop.handle_key("CTRL_V")
                elif ctrl_held and event.key == pygame.K_x:
                    desktop.handle_key("CTRL_X")
                elif ctrl_held and event.key == pygame.K_z:
                    desktop.handle_key("CTRL_Z")
                elif ctrl_held and event.key == pygame.K_y:
                    desktop.handle_key("CTRL_Y")
                elif ctrl_held and event.key == pygame.K_s:
                    desktop.handle_key("CTRL_S")
                elif ctrl_held and event.key == pygame.K_d:
                    desktop.handle_key("CTRL_D")
                elif ctrl_held and event.key == pygame.K_f:
                    desktop.handle_key("CTRL_F")
                elif ctrl_held and event.key in (pygame.K_SLASH, pygame.K_KP_DIVIDE):
                    desktop.handle_key("CTRL_SLASH")
                elif ctrl_held and event.key == pygame.K_BACKSPACE:
                    desktop.handle_key("CTRL_BACKSPACE")
                elif ctrl_held and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    desktop.handle_key("CTRL_ENTER")
                elif ctrl_held and event.key == pygame.K_LEFT:
                    desktop.handle_key("CTRL_LEFT")
                elif ctrl_held and event.key == pygame.K_RIGHT:
                    desktop.handle_key("CTRL_RIGHT")
                elif ctrl_held and event.key == pygame.K_HOME:
                    desktop.handle_key("CTRL_HOME")
                elif ctrl_held and event.key == pygame.K_END:
                    desktop.handle_key("CTRL_END")
                elif alt_held and event.key == pygame.K_UP:
                    desktop.handle_key("ALT_UP")
                elif alt_held and event.key == pygame.K_DOWN:
                    desktop.handle_key("ALT_DOWN")
                elif shift_held and event.key == pygame.K_LEFT:
                    desktop.handle_key("SHIFT_LEFT")
                elif shift_held and event.key == pygame.K_RIGHT:
                    desktop.handle_key("SHIFT_RIGHT")
                elif shift_held and event.key == pygame.K_UP:
                    desktop.handle_key("SHIFT_UP")
                elif shift_held and event.key == pygame.K_DOWN:
                    desktop.handle_key("SHIFT_DOWN")
                elif shift_held and event.key == pygame.K_HOME:
                    desktop.handle_key("SHIFT_HOME")
                elif shift_held and event.key == pygame.K_END:
                    desktop.handle_key("SHIFT_END")
                elif event.key == pygame.K_DELETE:
                    desktop.handle_key("DELETE")
                elif event.key == pygame.K_HOME:
                    desktop.handle_key("HOME")
                elif event.key == pygame.K_END:
                    desktop.handle_key("END")
                elif event.key == pygame.K_PAGEUP:
                    desktop.handle_key("PAGE_UP")
                elif event.key == pygame.K_PAGEDOWN:
                    desktop.handle_key("PAGE_DOWN")
                elif event.key == pygame.K_TAB and shift_held:
                    desktop.handle_key("SHIFT_TAB")
                elif event.key == pygame.K_BACKSPACE:
                    desktop.handle_key("\b")
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    desktop.handle_key("\n")
                elif event.key == pygame.K_TAB:
                    desktop.handle_key("\t")
                elif event.key == pygame.K_UP:
                    desktop.handle_key("KEY_UP")
                elif event.key == pygame.K_DOWN:
                    desktop.handle_key("KEY_DOWN")
                elif event.key == pygame.K_LEFT:
                    desktop.handle_key("KEY_LEFT")
                elif event.key == pygame.K_RIGHT:
                    desktop.handle_key("KEY_RIGHT")
                elif event.key == pygame.K_F11:
                    desktop.handle_key("F11")
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
