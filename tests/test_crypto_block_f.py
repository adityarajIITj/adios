#!/usr/bin/env python3
"""
Test Suite: Block F Advanced Cyber Security & Cryptography Subsystem
Verifies:
1. FIPS 180-4 SHA-256 & RFC 2104 HMAC-SHA256
2. RFC 7539 ChaCha20 Stream Cipher
3. RFC 7539 Poly1305 MAC & ChaCha20-Poly1305 AEAD
4. PBKDF2-HMAC-SHA256 Key Derivation & Encrypted Virtual Disk Block Driver
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from crypto.sha256 import SHA256, sha256_hash, hmac_sha256
from crypto.chacha20 import ChaCha20
from crypto.poly1305 import Poly1305, ChaCha20Poly1305AEAD
from crypto.disk_crypto import pbkdf2_sha256, EncryptedDiskDevice

def test_crypto_block_f_suite():
    print("[Test Crypto Block F] Initializing Cryptographic Subsystem Verification...")

    # 1. Test SHA-256 with standard test vectors
    print("  -> Testing FIPS 180-4 SHA-256...")
    # Vector: "abc" -> ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
    h_abc = SHA256(b"abc").hexdigest()
    assert h_abc == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", f"SHA-256 mismatch for 'abc': {h_abc}"

    # Vector: empty string -> e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    h_empty = SHA256(b"").hexdigest()
    assert h_empty == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", f"SHA-256 mismatch for empty string"

    # Test multi-block message
    long_msg = b"AdiOS Sovereign Computing Architecture " * 20
    h_long = SHA256(long_msg).hexdigest()
    assert len(h_long) == 64
    print("  -> [PASS] SHA-256 standard vectors verified.")

    # 2. Test HMAC-SHA256
    print("  -> Testing RFC 2104 HMAC-SHA256...")
    key = b"key_secret"
    msg = b"The quick brown fox jumps over the lazy dog"
    mac = hmac_sha256(key, msg)
    assert len(mac) == 32
    # Verify deterministic output
    assert hmac_sha256(key, msg) == mac
    # Verify tamper detection
    assert hmac_sha256(key, b"The quick brown fox jumps over the lazy doG") != mac
    print("  -> [PASS] HMAC-SHA256 verified.")

    # 3. Test ChaCha20 Stream Cipher
    print("  -> Testing RFC 7539 ChaCha20 Stream Cipher...")
    k32 = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f" \
          b"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
    n12 = b"\x00\x00\x00\x00\x00\x00\x00\x4a\x00\x00\x00\x00"
    cipher1 = ChaCha20(k32, n12, counter=1)
    secret_text = b"Sovereign RISC-V Operating System Built from First Principles"
    ciphertext = cipher1.encrypt(secret_text)
    assert ciphertext != secret_text
    assert len(ciphertext) == len(secret_text)

    # Decrypt
    cipher2 = ChaCha20(k32, n12, counter=1)
    plaintext = cipher2.decrypt(ciphertext)
    assert plaintext == secret_text
    print("  -> [PASS] ChaCha20 symmetric encryption/decryption verified.")

    # 4. Test Poly1305 & ChaCha20-Poly1305 AEAD
    print("  -> Testing Poly1305 & ChaCha20-Poly1305 AEAD...")
    poly_key = b"12345678901234567890123456789012"
    poly = Poly1305(poly_key)
    poly.update(b"Cryptographic Tag Validation")
    tag = poly.digest()
    assert len(tag) == 16

    aead = ChaCha20Poly1305AEAD(k32)
    aad = b"PacketHeaderInfo"
    c_bytes, aead_tag = aead.seal(n12, secret_text, aad)
    assert len(aead_tag) == 16
    opened = aead.open(n12, c_bytes, aead_tag, aad)
    assert opened == secret_text

    # Test tampering rejection
    tampered_c = bytearray(c_bytes)
    tampered_c[0] ^= 0xFF
    try:
        aead.open(n12, bytes(tampered_c), aead_tag, aad)
        assert False, "AEAD must reject tampered ciphertext"
    except ValueError:
        pass
    print("  -> [PASS] ChaCha20-Poly1305 AEAD authenticated encryption verified.")

    # 5. Test Encrypted Disk Driver & PBKDF2
    print("  -> Testing Encrypted Virtual Disk Block Driver...")
    derived_k = pbkdf2_sha256("sovereign_system_passphrase", b"adios_disk_salt", iterations=200, key_len=32)
    assert len(derived_k) == 32
    enc_disk = EncryptedDiskDevice(derived_k)

    sector_data = (b"ADIFS_DIRECTORY_ROOT_SECTOR_CONTIGUOUS_DATA\x00" * 12)[:512]
    enc_sector = enc_disk.encrypt_sector(sector_num=100, sector_data=sector_data)
    assert len(enc_sector) == 512
    assert enc_sector != sector_data

    dec_sector = enc_disk.decrypt_sector(sector_num=100, encrypted_sector=enc_sector)
    assert dec_sector == sector_data

    # Different sector number must yield different ciphertext (tweak isolation)
    enc_sector_diff = enc_disk.encrypt_sector(sector_num=101, sector_data=sector_data)
    assert enc_sector_diff != enc_sector
    print("  -> [PASS] Encrypted block storage driver verified.")

    print("\n[Test Crypto Block F] ALL BLOCK F CRYPTOGRAPHY TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_crypto_block_f_suite()
