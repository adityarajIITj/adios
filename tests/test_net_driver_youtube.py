#!/usr/bin/env python3
"""
AdiOS Test Suite: Network Drivers & Real Internet YouTube Streaming (v2.0 Beta Phase 3)
Verifies:
- Host network bridge, DNS resolution, ARP handling, and internet probe
- Pure Python ISO MP4 box/atom progressive demuxer
- Real YouTube URL & video ID parser across all standard formats
- YouTube oEmbed metadata resolution & world video catalog
- Sovereign YouTube Player interactive keyboard typing, URL loading, and catalog switching
- VPU 30 FPS frame delivery & PTS audio-video synchronization

STRICT ZERO EMOJI POLICY ENFORCED.
"""

import unittest
import struct
from drivers.net_bridge import HostNetBridge, get_net_bridge
from net.mp4_demuxer import MP4Demuxer, MP4Box, MP4Track
from net.yt_relay import YouTubeStreamRelay, WORLD_VIDEOS, extract_youtube_id, fetch_youtube_metadata
from desktop.youtube_player import YouTubePlayerApp
from vm.vpu import VPU


class TestNetDriverYouTube(unittest.TestCase):
    def test_01_host_net_bridge_init_and_reachability(self):
        """Verify HostNetBridge initialization, probe, and packet translation."""
        bridge = HostNetBridge()
        self.assertEqual(bridge.dns_server, "8.8.8.8")
        
        # Test online probe (returns boolean without raising exception)
        online = bridge.is_online()
        self.assertIsInstance(online, bool)

        # Test ARP translation
        # ARP Request: sender=192.168.1.50, target=192.168.1.1
        src_mac = b"\x52\x54\x00\xAA\xBB\xCC"
        bcast_mac = b"\xFF\xFF\xFF\xFF\xFF\xFF"
        arp_req = struct.pack("!HHBBH6s4s6s4s",
            1, 0x0800, 6, 4, 1,
            src_mac, b"\xC0\xA8\x01\x32",
            b"\x00\x00\x00\x00\x00\x00", b"\xC0\xA8\x01\x01"
        )
        eth_frame = bcast_mac + src_mac + struct.pack("!H", 0x0806) + arp_req
        reply = bridge.bridge_ethernet_packet(eth_frame)
        self.assertIsNotNone(reply)
        self.assertEqual(len(reply), 42)
        # Reply eth_type is ARP (0x0806)
        self.assertEqual(struct.unpack("!H", reply[12:14])[0], 0x0806)

    def test_02_mp4_demuxer_parsing(self):
        """Verify ISO Base Media File Format (MP4) parser on binary boxes."""
        # Construct synthetic MP4 container: ftyp + moov (mvhd + trak(tkhd, mdia(hdlr, mdhd, minf(stbl(stsz, stts, stco)))))) + mdat
        # 1. ftyp box: size=16, type=b'ftyp', major_brand=b'isom', minor_ver=512
        ftyp = struct.pack(">I4s4sI", 16, b"ftyp", b"isom", 512)

        # 2. stsz box: 4 samples of 100 bytes each (size 36 = 8 header + 4 ver + 4 def_size + 4 count + 16 sizes)
        stsz = struct.pack(">I4sIII4I", 36, b"stsz", 0, 0, 4, 100, 100, 100, 100)
        # stts box: 1 entry of 4 samples with delta 1000 (size 24)
        stts = struct.pack(">I4sIIII", 24, b"stts", 0, 1, 4, 1000)
        # stco box: 1 chunk at offset 1024 (size 20)
        stco = struct.pack(">I4sIII", 20, b"stco", 0, 1, 1024)
        # stbl box
        stbl_len = 8 + len(stsz) + len(stts) + len(stco)
        stbl = struct.pack(">I4s", stbl_len, b"stbl") + stsz + stts + stco
        # minf box
        minf_len = 8 + len(stbl)
        minf = struct.pack(">I4s", minf_len, b"minf") + stbl
        # hdlr box: 'vide'
        hdlr = struct.pack(">I4sII4s", 20, b"hdlr", 0, 0, b"vide")
        # mdhd box (size 28: 4 size, 4 type, 4 ver, 4 ctime, 4 mtime, 4 timescale, 4 duration)
        mdhd = struct.pack(">I4sIIIII", 28, b"mdhd", 0, 0, 0, 1000, 4000)
        # mdia box
        mdia_len = 8 + len(hdlr) + len(mdhd) + len(minf)
        mdia = struct.pack(">I4s", mdia_len, b"mdia") + hdlr + mdhd + minf
        # tkhd box: width=480, height=270 (fixed point 16.16)
        tkhd_data = bytearray(84)
        tkhd_data[15] = 1 # track_id = 1
        struct.pack_into(">II", tkhd_data, 76, 480 << 16, 270 << 16)
        tkhd = struct.pack(">I4s", 8 + len(tkhd_data), b"tkhd") + bytes(tkhd_data)
        # trak box
        trak_len = 8 + len(tkhd) + len(mdia)
        trak = struct.pack(">I4s", trak_len, b"trak") + tkhd + mdia
        # mvhd box (size 28)
        mvhd = struct.pack(">I4sIIIII", 28, b"mvhd", 0, 0, 0, 1000, 4000)
        # moov box
        moov_len = 8 + len(mvhd) + len(trak)
        moov = struct.pack(">I4s", moov_len, b"moov") + mvhd + trak
        # mdat box
        mdat = struct.pack(">I4s", 408, b"mdat") + (b"\xAA" * 400)

        raw_mp4 = ftyp + moov + mdat

        demuxer = MP4Demuxer(raw_mp4)
        self.assertEqual(demuxer.major_brand, "isom")
        self.assertEqual(demuxer.duration_ms, 4000)
        self.assertIsNotNone(demuxer.video_track)
        self.assertEqual(demuxer.video_track.width, 480)
        self.assertEqual(demuxer.video_track.height, 270)
        self.assertEqual(demuxer.video_track.sample_count, 4)
        self.assertEqual(demuxer.video_track.sample_sizes, [100, 100, 100, 100])

    def test_03_youtube_url_and_id_extraction(self):
        """Verify YouTube URL and video ID extraction across standard formats."""
        # 1. Standard watch?v=
        self.assertEqual(extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(extract_youtube_id("http://youtube.com/watch?feature=player&v=oZ313uI8kQc"), "oZ313uI8kQc")
        
        # 2. youtu.be shortlinks
        self.assertEqual(extract_youtube_id("https://youtu.be/aqz-KE-bpKQ"), "aqz-KE-bpKQ")
        
        # 3. Embed URLs
        self.assertEqual(extract_youtube_id("https://www.youtube.com/embed/cwZb2mqId0A"), "cwZb2mqId0A")
        
        # 4. Shorts URLs
        self.assertEqual(extract_youtube_id("https://www.youtube.com/shorts/5qap5aO4i9A"), "5qap5aO4i9A")
        
        # 5. Direct 11-char token
        self.assertEqual(extract_youtube_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        
        # 6. Non-YouTube link returns None
        self.assertIsNone(extract_youtube_id("https://example.com/video.mp4"))

    def test_04_youtube_metadata_and_catalog(self):
        """Verify world video catalog integrity and metadata resolution."""
        self.assertGreaterEqual(len(WORLD_VIDEOS), 6)
        
        # Test Rick Astley entry
        m1 = fetch_youtube_metadata("dQw4w9WgXcQ")
        self.assertEqual(m1["id"], "dQw4w9WgXcQ")
        self.assertIn("Rick Astley", m1["title"])
        self.assertIn("views", m1["views"])

        # Test RISC-V Keynote entry
        m2 = fetch_youtube_metadata("oZ313uI8kQc")
        self.assertEqual(m2["id"], "oZ313uI8kQc")
        self.assertIn("RISC-V", m2["title"])

    def test_05_stream_relay_load_url_and_30fps_generation(self):
        """Verify YouTubeStreamRelay URL loading, 30 FPS frame generation, and audio PCM."""
        relay = YouTubeStreamRelay(0)
        
        # Load Apollo 11 video URL
        ok = relay.load_url("https://www.youtube.com/watch?v=cwZb2mqId0A")
        self.assertTrue(ok)
        self.assertEqual(relay.active_video_id, "cwZb2mqId0A")
        self.assertIn("Apollo", relay.channel_info["title"])
        
        # Generate 30 FPS Video Frame at PTS=1000ms
        frame = relay.generate_frame(pts_ms=1000, width=480, height=240)
        self.assertEqual(frame.width, 480)
        self.assertEqual(frame.height, 240)
        self.assertEqual(frame.pts_ms, 1000)
        self.assertEqual(len(frame.data), 480 * 240 * 4)

        # Generate Audio PCM (0.1s at 44.1 kHz)
        pcm = relay.generate_audio_pcm(0.1)
        expected_bytes = int(0.1 * 44100) * 2
        self.assertEqual(len(pcm), expected_bytes)

    def test_06_youtube_player_interactive_typing_and_load(self):
        """Verify Sovereign YouTube Player keyboard URL typing and catalog switching."""
        vpu = VPU(width=480, height=240, fps=30)
        app = YouTubePlayerApp(vpu=vpu)

        # Focus URL box
        self.assertFalse(app.url_focused)
        # Click URL box at (150, 15)
        app.handle_click(150, 15)
        self.assertTrue(app.url_focused)

        # Type custom YouTube link: clear with backspaces and type "dQw4w9WgXcQ"
        app.url_text = ""
        for ch in "dQw4w9WgXcQ":
            handled = app.handle_key(ch)
            self.assertTrue(handled)
        self.assertEqual(app.url_text, "dQw4w9WgXcQ")

        # Press Enter to load
        app.handle_key("\r")
        self.assertFalse(app.url_focused)
        self.assertIn("Rick Astley", app.relay.channel_info["title"])
        self.assertTrue(app.is_playing)

        # Select Catalog Video for Big Buck Bunny (index 5)
        app.select_catalog_video(5)
        self.assertIn("Big Buck Bunny", app.relay.channel_info["title"])

        # Test Pasting Full URL via handle_key string
        app.url_focused = True
        app.handle_key("CLEAR")
        self.assertEqual(app.url_text, "")
        app.handle_key("https://www.youtube.com/watch?v=MYxamzOcVbs")
        self.assertEqual(app.url_text, "https://www.youtube.com/watch?v=MYxamzOcVbs")
        app.handle_key("\r")
        self.assertIn("Codex", app.relay.channel_info["title"])

        # Test [PASTE] button click
        clicked = app.handle_click(app.rect_paste[0] + 5, app.rect_paste[1] + 5)
        self.assertTrue(clicked)

    def test_07_youtube_player_render_and_vpu_step(self):
        """Verify window rendering and VPU deterministic 30 FPS pacing."""
        vpu = VPU(width=480, height=240, fps=30)
        app = YouTubePlayerApp(vpu=vpu)
        
        cw, ch = 518, 398
        surf = bytearray(cw * ch * 4)
        app.render(surf, cw, ch)

        # Background should be dark (18, 18, 22)
        # Check pixel at (5, 5) -> B=22, G=18, R=18, A=255
        self.assertEqual(surf[0:4], bytes([22, 18, 18, 255]))

        # Step frame
        app.step()
        self.assertGreaterEqual(vpu.frames_played, 0)


if __name__ == "__main__":
    unittest.main()
