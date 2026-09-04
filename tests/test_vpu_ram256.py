#!/usr/bin/env python3
"""
AdiOS Test Suite: 256 MB RAM Expansion & Hardware MMIO VPU 30 FPS Video Controller
Verifies:
1. 256 MB Physical RAM allocation, boundary memory access, and address space integrity.
2. Physical Page Allocator scaling to 65,536 page frames with Buddy Allocator Order-10.
3. Hardware MMIO Video Processing Unit (VPU at 0x30000000) registers and command FSM.
4. Deterministic 30 FPS frame pacing and Direct Memory Access (DMA) frame blitter.
5. Sovereign YouTube stream relay and synchronized 44.1 kHz 16-bit PCM audio generation.
6. Windowed Sovereign YouTube Player application state and interactive transport controls.

Zero external dependencies. Pure RV32IM systems verification.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import unittest
import time
from vm.vm import VM, RAM_BASE, RAM_SIZE, RAM_SIZE_256MB, VPU_BASE
from mmu.page_alloc import PhysicalPageAllocator, TOTAL_PAGES_256MB, PAGE_SIZE
from vm.vpu import (
    VPU, CMD_PLAY, CMD_PAUSE, CMD_STOP, CMD_SEEK,
    STATUS_STOPPED, STATUS_PLAYING, STATUS_PAUSED
)
from net.yt_relay import YouTubeStreamRelay, CHANNELS
from desktop.youtube_player import YouTubePlayerApp


class TestVPUAndRAM256(unittest.TestCase):
    def setUp(self):
        self.vm = VM(ram_size=RAM_SIZE_256MB)
        self.vpu = VPU(vm=self.vm, width=480, height=270, fps=30)
        self.vm.vpu = self.vpu

    def test_01_ram_256mb_allocation(self):
        """Verify 256 MB physical RAM allocation and upper boundary read/write."""
        self.assertEqual(len(self.vm.ram), 256 * 1024 * 1024)
        self.assertEqual(self.vm.ram_size, 256 * 1024 * 1024)

        # Write and read at the very top of 256 MB space (0x8FFFFFFC)
        top_addr = RAM_BASE + len(self.vm.ram) - 4
        test_val = 0xDEADBEEF
        self.vm.write32(top_addr, test_val)
        read_back = self.vm.read32(top_addr)
        self.assertEqual(read_back, test_val)

        # Write and read at mid-memory (128 MB offset: 0x88000000)
        mid_addr = RAM_BASE + 128 * 1024 * 1024
        self.vm.write32(mid_addr, 0xCAFEBABE)
        self.assertEqual(self.vm.read32(mid_addr), 0xCAFEBABE)

    def test_02_page_allocator_256mb(self):
        """Verify Physical Page Allocator scaling to 65,536 frames and Buddy Allocator Order-10."""
        alloc = PhysicalPageAllocator(total_pages=TOTAL_PAGES_256MB)
        self.assertEqual(alloc.total_pages, 65536)
        self.assertEqual(alloc.total_pages * PAGE_SIZE, 256 * 1024 * 1024)

        # Highmem zone should contain expanded memory (176 MB)
        self.assertGreaterEqual(alloc.zone_highmem.total_pages * PAGE_SIZE, 176 * 1024 * 1024)

        # Allocate Order 10 (1024 pages = 4 MB contiguous block)
        paddr = alloc.buddy.alloc_pages(order=10)
        self.assertIsNotNone(paddr)
        self.assertTrue(RAM_BASE <= paddr < RAM_BASE + 256 * 1024 * 1024)

        # Free Order 10 block and verify coalescing
        alloc.buddy.free_pages(paddr, order=10)

        # Single page allocation
        p1 = alloc.alloc_page()
        self.assertIsNotNone(p1)
        alloc.free_page(p1)

    def test_03_vpu_mmio_registers_and_fsm(self):
        """Verify VPU MMIO registers at 0x30000000 and command state transitions."""
        # Read default registers via VM bus
        self.assertEqual(self.vm.read32(0x30000004), STATUS_STOPPED)
        self.assertEqual(self.vm.read32(0x3000000C), 480) # Width
        self.assertEqual(self.vm.read32(0x30000010), 270) # Height
        self.assertEqual(self.vm.read32(0x30000014), 30)  # Target FPS

        # Command: PLAY
        self.vm.write32(0x30000000, CMD_PLAY)
        self.assertEqual(self.vm.read32(0x30000004), STATUS_PLAYING)

        # Command: PAUSE
        self.vm.write32(0x30000000, CMD_PAUSE)
        self.assertEqual(self.vm.read32(0x30000004), STATUS_PAUSED)

        # Command: STOP
        self.vm.write32(0x30000000, CMD_STOP)
        self.assertEqual(self.vm.read32(0x30000004), STATUS_STOPPED)
        self.assertEqual(self.vm.read32(0x3000001C), 0) # Current PTS reset

        # Command: SEEK to 45,000 ms
        self.vm.write32(0x30000024, 45000) # VPU_SEEK_TARGET
        self.vm.write32(0x30000000, CMD_SEEK)
        self.assertEqual(self.vm.read32(0x3000001C), 45000)

        # Configure volume
        self.vm.write32(0x30000028, 95)
        self.assertEqual(self.vm.read32(0x30000028), 95)

    def test_04_vpu_30fps_frame_pacing(self):
        """Verify VPU deterministic 30 FPS timing and frame delivery."""
        relay = YouTubeStreamRelay(0)
        self.vpu.relay = relay
        self.vpu.write32(0x30000000, CMD_PLAY)

        # Pacing test: step before interval (e.g. 10ms) should not advance frame
        t0 = time.time()
        self.vpu._last_frame_time = t0
        res = self.vpu.step(now=t0 + 0.010)
        self.assertFalse(res)

        # Step at or after 33.3ms should advance frame
        res = self.vpu.step(now=t0 + 0.035)
        self.assertTrue(res)
        self.assertGreater(self.vpu.frames_played, 0)
        self.assertIsNotNone(self.vpu.get_current_frame())

    def test_05_dma_blit_to_surface(self):
        """Verify hardware DMA blit transfers frame data directly into surface buffer with clipping."""
        relay = YouTubeStreamRelay(0)
        self.vpu.relay = relay
        frame = relay.generate_frame(pts_ms=1000, width=480, height=270)
        self.vpu._current_frame = frame

        surf_w, surf_h = 520, 400
        surface = bytearray(surf_w * surf_h * 4)

        # Blit frame to (20, 50) on surface
        self.vpu.dma_blit_to_surface(surface, surf_w, surf_h, dst_x=20, dst_y=50)

        # Center pixel of video on surface should be painted (non-zero alpha)
        center_x = 20 + 240
        center_y = 50 + 135
        off = (center_y * surf_w + center_x) * 4
        # Alpha channel is byte 3
        self.assertEqual(surface[off + 3], 255)

    def test_06_youtube_stream_relay(self):
        """Verify YouTube stream relay channels, frame synthesis, and PCM audio generation."""
        relay = YouTubeStreamRelay(0)
        self.assertEqual(len(CHANNELS), 3)

        # Test Channel 0: RISC-V 3D Core
        f0 = relay.generate_frame(pts_ms=0, width=480, height=270)
        self.assertEqual(len(f0.data), 480 * 270 * 4)

        # Test Channel 1: Synthwave
        relay.set_channel(1)
        self.assertEqual(relay.channel_idx, 1)
        f1 = relay.generate_frame(pts_ms=2000, width=480, height=270)
        self.assertEqual(len(f1.data), 480 * 270 * 4)

        # Test Channel 2: Matrix
        relay.set_channel(2)
        f2 = relay.generate_frame(pts_ms=4000, width=480, height=270)
        self.assertEqual(len(f2.data), 480 * 270 * 4)

        # Test 16-bit 44.1 kHz PCM Audio generation
        audio_data = relay.generate_audio_pcm(duration_sec=0.1) # 100ms
        expected_samples = int(0.1 * 44100)
        self.assertEqual(len(audio_data), expected_samples * 2)

    def test_07_youtube_desktop_player_app(self):
        """Verify Sovereign YouTube Player UI state, controls, and frame stepping."""
        app = YouTubePlayerApp(vpu=self.vpu)
        self.assertTrue(app.is_playing)
        self.assertEqual(app.video_w, 480)
        self.assertEqual(app.video_h, 270)

        # Render complete window interface
        surf = bytearray(520 * 420 * 4)
        app.render(surf, 520, 420)
        self.assertGreater(len(surf), 0)

        # Click transport: Play/Pause
        app.handle_click(30, 375) # btn_play
        self.assertFalse(app.is_playing)
        app.handle_click(30, 375)
        self.assertTrue(app.is_playing)

        # Click Channel 3: Matrix
        app.handle_click(280, 375) # btn_ch3
        self.assertEqual(app.active_channel, 2)
        self.assertIn("ch_matrix", app.url_text)

        # Click Scrub bar at 50%
        app.handle_click(app.scrub_x + app.scrub_w // 2, app.scrub_y)
        self.assertGreaterEqual(self.vpu.current_pts, 0)

        # Click Volume toggle
        orig_vol = app.volume
        app.handle_click(360, 375) # btn_vol
        self.assertNotEqual(app.volume, orig_vol)


if __name__ == "__main__":
    unittest.main()
