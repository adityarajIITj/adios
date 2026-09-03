#!/usr/bin/env python3
"""
Test Suite: Block T Cryptographic TLS 1.3 Record Layer & Handshake Engine
Verifies:
1. crypto/tls13: RFC 5869 HKDF Extract & Expand functions
2. crypto/tls13: TLS 1.3 Key Schedule (early, handshake, master secrets & Finished tag)
3. crypto/tls13: TLSRecordLayer framing (pack/unpack)
4. crypto/tls13: ChaCha20-Poly1305 AEAD record encryption, decryption & tamper resistance
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from crypto.tls13 import (
    hkdf_extract, hkdf_expand, hkdf_expand_label,
    TLS13KeySchedule, TLSRecordLayer,
    TLS_RECORD_APP_DATA, TLS_RECORD_HANDSHAKE
)

def test_tls13_block_t_suite():
    print("[Test TLS 1.3 Block T] Initializing TLS 1.3 Security Verification...")

    # 1. Test HKDF Extract & Expand
    print("  -> Testing RFC 5869 HKDF Extract & Expand...")
    salt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    ikm = b"SovereignAdiOSMasterKeyMaterial"
    prk = hkdf_extract(salt, ikm)
    assert len(prk) == 32

    okm = hkdf_expand(prk, b"expansion-context", length=42)
    assert len(okm) == 42
    print("  -> [PASS] HKDF Extract & Expand verified.")

    # 2. Test TLS 1.3 Key Schedule
    print("  -> Testing TLS 1.3 Multi-Stage Key Schedule (Early -> Handshake -> Master)...")
    ks = TLS13KeySchedule()
    assert len(ks.early_secret) == 32

    synthetic_dhe = b"\x5A" * 32
    transcript_hello = b"ClientHelloRawBytes...ServerHelloRawBytes..."
    ks.compute_handshake_secrets(synthetic_dhe, transcript_hello)

    assert len(ks.handshake_secret) == 32
    assert len(ks.client_hs_key) == 32 # 256-bit key
    assert len(ks.client_hs_iv) == 12   # 96-bit IV
    assert len(ks.server_hs_key) == 32
    assert len(ks.server_hs_iv) == 12

    # Verify Finished HMAC authentication tag
    client_finished = ks.calculate_finished(ks.client_handshake_traffic_secret, transcript_hello)
    server_finished = ks.calculate_finished(ks.server_handshake_traffic_secret, transcript_hello)
    assert len(client_finished) == 32
    assert len(server_finished) == 32
    assert client_finished != server_finished # Different keys produce distinct authenticators

    # Master Application Secrets
    full_transcript = transcript_hello + client_finished + server_finished
    ks.compute_master_secrets(full_transcript)
    assert len(ks.master_secret) == 32
    assert len(ks.client_app_key) == 32
    assert len(ks.server_app_key) == 32
    print("  -> [PASS] TLS 1.3 Key Schedule & Finished tag generation verified.")

    # 3. Test TLS Record Layer Framing
    print("  -> Testing TLS Record Layer Framing (Pack & Unpack)...")
    raw_record = TLSRecordLayer.pack_record(TLS_RECORD_HANDSHAKE, b"\x01\x00\x00\x10SyntheticClientHello")
    assert raw_record[0] == TLS_RECORD_HANDSHAKE
    assert raw_record[1:3] == b"\x03\x03" # Legacy version 0x0303
    c_type, ver, payload = TLSRecordLayer.unpack_record(raw_record)
    assert c_type == TLS_RECORD_HANDSHAKE
    assert ver == 0x0303
    assert payload == b"\x01\x00\x00\x10SyntheticClientHello"
    print("  -> [PASS] Record framing verified.")

    # 4. Test ChaCha20-Poly1305 Application Record Encryption & Tamper Resistance
    print("  -> Testing ChaCha20-Poly1305 AEAD Record Encryption & Decryption...")
    app_key = ks.client_app_key
    app_iv  = ks.client_app_iv
    seq_num = 0

    secret_message = b"GET /sovereign/quantum-node HTTP/1.1\r\nHost: secure.adios\r\n\r\n"
    enc_record = TLSRecordLayer.encrypt_app_record(app_key, app_iv, seq_num, secret_message)
    assert enc_record[0] == TLS_RECORD_APP_DATA
    assert len(enc_record) == 5 + len(secret_message) + 1 + 16 # 5 hdr + msg + 1 tag + 16 mac

    # Decrypt
    decrypted = TLSRecordLayer.decrypt_app_record(app_key, app_iv, seq_num, enc_record)
    assert decrypted == secret_message

    # Tamper resistance test
    tampered = bytearray(enc_record)
    tampered[10] ^= 0xFF # Flip a bit in ciphertext
    tamper_failed = False
    try:
        TLSRecordLayer.decrypt_app_record(app_key, app_iv, seq_num, bytes(tampered))
    except Exception:
        tamper_failed = True
    assert tamper_failed is True
    print("  -> [PASS] ChaCha20-Poly1305 AEAD encryption & tamper detection verified.")

    print("\n[Test TLS 1.3 Block T] ALL BLOCK T TLS 1.3 CRYPTOGRAPHIC TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_tls13_block_t_suite()
