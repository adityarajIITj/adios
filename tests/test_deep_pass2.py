#!/usr/bin/env python3
"""
AdiOS Test Suite: Pass 2 — Cyber Security, Cryptography & Protocols Deepening
Tests:
- ASN.1 DER Decoder & X.509 Public Key Certificate Parser (crypto/x509.py)
- AES-128/192/256 Block Cipher, ECB, CBC, and CTR Modes (crypto/aes.py)
- RFC 5681 TCP Congestion Control State Machine (net/tcp_congestion.py)
- RFC 6455 WebSocket Framing & Upgrade Handshake Engine (net/websocket.py)

Zero external dependencies. Pure bare-metal verification.
STRICT ZERO EMOJI POLICY.
"""

import unittest
from crypto.x509 import DERDecoder, X509Certificate, create_self_signed_cert_der
from crypto.aes import AES
from net.tcp_congestion import TCPCongestionControl, CongestionState
from net.websocket import WebSocketEngine, OPCODE_TEXT, OPCODE_BINARY, sha1, b64encode

class TestPass2CryptoAndProtocols(unittest.TestCase):

    # --------------------------------------------------------------------------
    # 1. ASN.1 DER & X.509 Certificate Tests
    # --------------------------------------------------------------------------

    def test_01_der_decoding_and_oids(self):
        # Encode and decode an integer and string
        val_bytes = DERDecoder.encode_tlv(0x02, (1337).to_bytes(2, "big"))
        node, consumed = DERDecoder.decode(val_bytes)
        self.assertEqual(node.as_int(), 1337)
        self.assertEqual(consumed, len(val_bytes))

        # Test OID decoding: 2.5.4.3 (commonName) -> 0x55, 0x04, 0x03
        oid_str = DERDecoder.decode_oid(bytes([0x55, 0x04, 0x03]))
        self.assertEqual(oid_str, "2.5.4.3")

    def test_02_x509_certificate_parsing(self):
        cert_der = create_self_signed_cert_der(
            common_name="sovereign.adios.org",
            rsa_modulus=0x100018889999,
            rsa_exp=65537
        )
        cert = X509Certificate(cert_der)

        self.assertEqual(cert.serial_number, 0x012345)
        self.assertEqual(cert.subject.get("commonName"), "sovereign.adios.org")
        self.assertEqual(cert.issuer.get("commonName"), "sovereign.adios.org")
        self.assertEqual(cert.rsa_modulus, 0x100018889999)
        self.assertEqual(cert.rsa_exponent, 65537)

    # --------------------------------------------------------------------------
    # 2. AES Block Cipher & Modes Tests
    # --------------------------------------------------------------------------

    def test_03_aes_block_roundtrip(self):
        key128 = b"0123456789abcdef" # 16 bytes
        cipher = AES(key128)
        block = b"SovereignAdiOS32" # 16 bytes

        encrypted = cipher.encrypt_block(block)
        self.assertNotEqual(encrypted, block)
        decrypted = cipher.decrypt_block(encrypted)
        self.assertEqual(decrypted, block)

        # AES-256 key
        key256 = b"0123456789abcdef0123456789abcdef" # 32 bytes
        cipher256 = AES(key256)
        encrypted256 = cipher256.encrypt_block(block)
        self.assertEqual(cipher256.decrypt_block(encrypted256), block)

    def test_04_aes_cbc_and_ctr_modes(self):
        key = b"SovereignSecretK" # 16 bytes
        iv  = b"InitializationV!" # 16 bytes
        plaintext = b"Ring-0 bare-metal AES encryption test payload across multiple blocks!"

        cipher = AES(key)
        # CBC Mode
        cbc_cipher = cipher.encrypt_cbc(plaintext, iv)
        cbc_plain = cipher.decrypt_cbc(cbc_cipher, iv)
        self.assertEqual(cbc_plain, plaintext)

        # CTR Mode
        nonce = b"123456789012" # 12 bytes
        ctr_cipher = cipher.encrypt_ctr(plaintext, nonce)
        ctr_plain = cipher.decrypt_ctr(ctr_cipher, nonce)
        self.assertEqual(ctr_plain, plaintext)

    # --------------------------------------------------------------------------
    # 3. TCP Congestion Control State Machine Tests
    # --------------------------------------------------------------------------

    def test_05_tcp_congestion_slow_start_and_avoidance(self):
        cc = TCPCongestionControl(smss=1460, initial_ssthresh=5840)
        self.assertEqual(cc.state, CongestionState.SLOW_START)
        self.assertEqual(cc.cwnd, 2920) # 2 SMSS

        # Receive new ACK in Slow Start -> cwnd increases by SMSS
        state, _ = cc.on_ack_received(ack_num=1000, bytes_acked=1460)
        self.assertEqual(cc.cwnd, 4380)

        # Another ACK -> cwnd hits 5840 (ssthresh) -> transitions to Congestion Avoidance
        state, _ = cc.on_ack_received(ack_num=2460, bytes_acked=1460)
        self.assertEqual(state, CongestionState.CONGESTION_AVOIDANCE)

    def test_06_tcp_fast_retransmit_and_recovery(self):
        cc = TCPCongestionControl(smss=1460, initial_ssthresh=65535)
        cc.set_flight_size(14600)

        # Send ACK 1000
        cc.on_ack_received(ack_num=1000, bytes_acked=1460)

        # 3 duplicate ACKs for ack_num 1000
        cc.on_ack_received(ack_num=1000, bytes_acked=0) # dup 1
        cc.on_ack_received(ack_num=1000, bytes_acked=0) # dup 2
        state, fast_rexmit = cc.on_ack_received(ack_num=1000, bytes_acked=0) # dup 3

        self.assertTrue(fast_rexmit)
        self.assertEqual(state, CongestionState.FAST_RECOVERY)
        self.assertEqual(cc.ssthresh, 7300) # flight_size // 2

        # New ACK exits Fast Recovery
        state, _ = cc.on_ack_received(ack_num=3000, bytes_acked=2000)
        self.assertEqual(state, CongestionState.CONGESTION_AVOIDANCE)
        self.assertEqual(cc.cwnd, cc.ssthresh)

        # Timeout resets to Slow Start
        cc.on_timeout()
        self.assertEqual(cc.state, CongestionState.SLOW_START)
        self.assertEqual(cc.cwnd, cc.smss)

    # --------------------------------------------------------------------------
    # 4. WebSocket Protocol & Handshake Tests
    # --------------------------------------------------------------------------

    def test_07_sha1_and_websocket_accept(self):
        # RFC 6455 standard test vector:
        # Client Key: "dGhlIHNhbXBsZSBub25jZQ=="
        # Expected Accept: "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        client_key = "dGhlIHNhbXBsZSBub25jZQ=="
        accept_token = WebSocketEngine.generate_accept_token(client_key)
        self.assertEqual(accept_token, "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")

    def test_08_websocket_framing_and_masking(self):
        text = "AdiOS Sovereign WebSocket Packet"
        payload = text.encode("utf-8")
        mask_key = b"\x12\x34\x56\x78"

        # Pack masked client frame
        frame_bytes = WebSocketEngine.pack_frame(payload, opcode=OPCODE_TEXT, fin=True, mask_key=mask_key)
        self.assertNotEqual(frame_bytes[6:], payload) # masked bytes differ

        # Unpack and verify automatic unmasking
        frame, consumed = WebSocketEngine.unpack_frame(frame_bytes)
        self.assertEqual(consumed, len(frame_bytes))
        self.assertTrue(frame.fin)
        self.assertEqual(frame.opcode, OPCODE_TEXT)
        self.assertEqual(frame.text(), text)

        # Binary unmasked server frame
        bin_data = b"\x00\xFF\xAA\x55" * 10
        bin_frame_bytes = WebSocketEngine.pack_frame(bin_data, opcode=OPCODE_BINARY, fin=True, mask_key=None)
        bin_frame, _ = WebSocketEngine.unpack_frame(bin_frame_bytes)
        self.assertEqual(bin_frame.payload, bin_data)

if __name__ == "__main__":
    unittest.main()
