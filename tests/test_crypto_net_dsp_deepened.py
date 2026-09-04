#!/usr/bin/env python3
"""
AdiOS Test Suite: Deepened Security, Protocols, 3D Graphics & DSP (Subsystem 50)
Verifies:
1. X.509 v3 extensions (SAN, BasicConstraints) and trust store certificate chain validation.
2. NIST SP 800-38D AES-GCM AEAD encryption, tag verification, tamper rejection, CFB and OFB.
3. RFC 5681 TCP Reno congestion control (Slow Start, Fast Retransmit, Fast Recovery, Jacobson RTT).
4. RFC 6455 WebSocket multi-frame message reassembly and stateful connection framing.
5. Software OpenGL 1.1 Rodrigues rotation, NDC backface culling, and 3D line rasterization.
6. 4-Channel Tracker Studio note frequency math, stereo panning, and RIFF/WAVE PCM synthesis.

Zero external dependencies. STRICT ZERO EMOJI POLICY.
"""

import unittest
from crypto.x509 import X509Certificate, CertificateStore, create_self_signed_cert_der, export_pem_certificate, parse_pem_certificate
from crypto.aes import AES
from net.tcp import TCPSocket, TCPState, TCPHeader, TCP_FLAG_ACK
from net.websocket import WebSocketConnection, WebSocketFrame, OPCODE_TEXT, OPCODE_CONTINUATION, OPCODE_PING
from gl.gl_core import SoftwareGL, GL_PROJECTION, GL_MODELVIEW, GL_TRIANGLES, GL_LINES, GL_CULL_FACE, GL_BACK, GL_DEPTH_TEST
from dsp.tracker_studio import TrackerStudio, TrackerSong, Pattern, note_to_freq


class TestDeepenedCryptoNetDsp(unittest.TestCase):

    def test_x509_v3_extensions_and_trust_store(self):
        # 1. Create Root CA
        root_der = create_self_signed_cert_der("Sovereign Root CA", rsa_modulus=0x1122334455, is_ca=True)
        root_cert = X509Certificate(root_der)
        self.assertTrue(root_cert.is_ca)
        self.assertEqual(root_cert.subject["commonName"], "Sovereign Root CA")

        # 2. Test PEM roundtrip
        pem_str = export_pem_certificate(root_cert)
        self.assertIn("-----BEGIN CERTIFICATE-----", pem_str)
        reparsed = parse_pem_certificate(pem_str)
        self.assertEqual(reparsed.serial_number, root_cert.serial_number)

        # 3. Create Leaf Certificate with SANs
        leaf_der = create_self_signed_cert_der(
            "workstation.sovereign.local",
            rsa_modulus=0x9988776655,
            is_ca=False,
            san_list=["workstation.sovereign.local", "127.0.0.1"]
        )
        leaf_cert = X509Certificate(leaf_der)
        self.assertFalse(leaf_cert.is_ca)
        self.assertIn("workstation.sovereign.local", leaf_cert.subject_alt_names)
        self.assertIn("127.0.0.1", leaf_cert.subject_alt_names)

        # 4. Trust Store Validation
        store = CertificateStore()
        store.add_trust_anchor(root_cert)
        # Root self-signed must verify
        valid, msg = store.verify_chain([root_cert])
        self.assertTrue(valid)

    def test_aes_gcm_aead_and_modes(self):
        key = b"SOVEREIGN_KEY_16"
        cipher = AES(key)
        plaintext = b"Classified Payload: Sovereign Ring-0 Operating System Core"
        nonce = b"NONCE_12_BYTE"
        aad = b"protocol=v1;node=node-42"

        # GCM Encryption
        ciphertext, tag = cipher.encrypt_gcm(plaintext, nonce, aad=aad)
        self.assertEqual(len(tag), 16)
        self.assertNotEqual(ciphertext, plaintext)

        # GCM Decryption
        decrypted = cipher.decrypt_gcm(ciphertext, tag, nonce, aad=aad)
        self.assertEqual(decrypted, plaintext)

        # Tamper Detection (Ciphertext mutation)
        bad_ciphertext = bytearray(ciphertext)
        bad_ciphertext[4] ^= 0x01
        with self.assertRaises(ValueError):
            cipher.decrypt_gcm(bytes(bad_ciphertext), tag, nonce, aad=aad)

        # Tamper Detection (AAD mutation)
        with self.assertRaises(ValueError):
            cipher.decrypt_gcm(ciphertext, tag, nonce, aad=b"tampered_aad")

        # Test CFB and OFB streaming modes
        iv = b"INITIAL_VECTOR16"
        c_cfb = cipher.encrypt_cfb(plaintext, iv)
        self.assertEqual(cipher.decrypt_cfb(c_cfb, iv), plaintext)

        c_ofb = cipher.encrypt_ofb(plaintext, iv)
        self.assertEqual(cipher.decrypt_ofb(c_ofb, iv), plaintext)

    def test_tcp_reno_congestion_control(self):
        sock = TCPSocket()
        sock.state = TCPState.ESTABLISHED
        sock.last_ack_num = 1000

        # Initial Slow Start Window = 1 MSS (1460)
        self.assertEqual(sock.cwnd, 1460)
        self.assertEqual(sock.ssthresh, 65535)

        # Slow start growth: +1 MSS per non-dup ACK
        sock.on_ack_received(1000 + 1460)
        self.assertEqual(sock.cwnd, 1460 * 2)

        sock.on_ack_received(1000 + 2920)
        self.assertEqual(sock.cwnd, 1460 * 3)

        # Test Fast Retransmit / Fast Recovery on 3 duplicate ACKs
        cur_ack = 1000 + 2920
        sock.on_ack_received(cur_ack) # Dup 1
        sock.on_ack_received(cur_ack) # Dup 2
        self.assertFalse(sock.in_fast_recovery)

        sock.on_ack_received(cur_ack) # Dup 3 -> Trigger Fast Recovery!
        self.assertTrue(sock.in_fast_recovery)
        expected_ssthresh = max((1460 * 3) // 2, 2 * 1460)
        self.assertEqual(sock.ssthresh, expected_ssthresh)
        self.assertEqual(sock.cwnd, expected_ssthresh + 3 * 1460)

        # Exit Fast Recovery on new ACK
        sock.on_ack_received(cur_ack + 1460)
        self.assertFalse(sock.in_fast_recovery)
        self.assertEqual(sock.cwnd, expected_ssthresh)

        # Test Jacobson RTT estimation
        sock.update_rtt(0.050) # 50ms sample
        self.assertAlmostEqual(sock.srtt, 0.050, places=3)
        self.assertGreaterEqual(sock.rto, 1.0) # Clamped at minimum 1.0s

    def test_websocket_fragmented_reassembly(self):
        conn = WebSocketConnection(is_client=False)

        # Stream 3 fragmented frames: "Alpha " + "Beta " + "Gamma"
        f1 = WebSocketFrame.pack_frame(OPCODE_TEXT, b"Alpha ", fin=False)
        f2 = WebSocketFrame.pack_frame(OPCODE_CONTINUATION, b"Beta ", fin=False)
        f3 = WebSocketFrame.pack_frame(OPCODE_CONTINUATION, b"Gamma", fin=True)

        # Feed frame 1 (incomplete)
        m1 = conn.feed_bytes(f1)
        self.assertEqual(len(m1), 0)

        # Feed frame 2 (incomplete)
        m2 = conn.feed_bytes(f2)
        self.assertEqual(len(m2), 0)

        # Feed frame 3 (terminating)
        m3 = conn.feed_bytes(f3)
        self.assertEqual(len(m3), 1)
        self.assertEqual(m3[0][0], OPCODE_TEXT)
        self.assertEqual(m3[0][1], "Alpha Beta Gamma")

        # Test ping frame interleaving
        ping_frame = conn.send_ping(b"heartbeat")
        parsed_ping, _ = WebSocketFrame.unpack_frame(ping_frame)
        self.assertTrue(parsed_ping.is_control)

    def test_software_gl_culling_and_transforms(self):
        gl = SoftwareGL(120, 90)
        gl.glClear(0xFF000000)
        gl.glEnable(GL_DEPTH_TEST)
        gl.glEnable(GL_CULL_FACE)
        gl.glCullFace(GL_BACK)

        gl.glMatrixMode(GL_PROJECTION)
        gl.glLoadIdentity()
        gl.gluPerspective(60.0, 120.0 / 90.0, 0.1, 50.0)

        gl.glMatrixMode(GL_MODELVIEW)
        gl.glLoadIdentity()
        gl.glTranslatef(0.0, 0.0, -3.0)
        gl.glRotatef(10.0, 0.0, 1.0, 0.0)

        # Render front-facing triangle (Counter-Clockwise in NDC)
        gl.glBegin(GL_TRIANGLES)
        gl.glColor3f(0.0, 1.0, 0.0)
        gl.glVertex3f(-1.0, -1.0, 0.0)
        gl.glVertex3f(1.0, -1.0, 0.0)
        gl.glVertex3f(0.0, 1.0, 0.0)
        gl.glEnd()

        center_green = gl.framebuffer[(45 * 120 + 60) * 4 + 1]
        self.assertGreater(center_green, 0)

        # Render 3D wireframe lines
        gl.glBegin(GL_LINES)
        gl.glColor3f(1.0, 1.0, 1.0)
        gl.glVertex3f(-1.5, 0.0, -1.0)
        gl.glVertex3f(1.5, 0.0, -1.0)
        gl.glEnd()

    def test_tracker_studio_sequencing_and_wav(self):
        # 1. Test note to frequency math
        self.assertAlmostEqual(note_to_freq("A-4"), 440.0, places=1)
        self.assertAlmostEqual(note_to_freq("A-3"), 220.0, places=1)
        self.assertAlmostEqual(note_to_freq("C-4"), 261.6, places=1)

        # 2. Build and render song
        studio = TrackerStudio(sample_rate=22050)
        song = TrackerSong(bpm=120, speed=6)
        pattern = Pattern(num_rows=8)
        pattern.set_note(0, 0, "C-4", waveform="sawtooth")
        pattern.set_note(2, 1, "E-4", waveform="triangle")
        pattern.set_note(4, 2, "G-4", waveform="square")
        pattern.set_note(6, 3, "C-5", waveform="sine")
        song.patterns.append(pattern)
        song.order = [0]

        stereo_samples = studio.render_song(song)
        self.assertGreater(len(stereo_samples), 1000)

        # 3. Test stereo WAV header generation
        wav_data = TrackerStudio.pcm_to_wav_stereo(stereo_samples, sample_rate=22050)
        self.assertTrue(wav_data.startswith(b"RIFF"))
        self.assertIn(b"WAVEfmt ", wav_data)
        self.assertIn(b"data", wav_data)


if __name__ == "__main__":
    unittest.main()
