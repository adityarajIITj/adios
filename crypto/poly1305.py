#!/usr/bin/env python3
"""
AdiOS Cryptographic Subsystem: Poly1305 Authenticator & AEAD (poly1305.py)
Implements RFC 7539 standard Poly1305 MAC and ChaCha20-Poly1305 AEAD.
Zero external dependencies.
"""

import struct
from crypto.chacha20 import ChaCha20

P = (1 << 130) - 5

def clamp(r_bytes: bytes) -> int:
    """Clamps the 16-byte 'r' key according to RFC 7539 Section 2.5."""
    r = bytearray(r_bytes)
    r[3]  &= 15
    r[7]  &= 15
    r[11] &= 15
    r[15] &= 15
    r[4]  &= 252
    r[8]  &= 252
    r[12] &= 252
    return int.from_bytes(r, "little")

class Poly1305:
    """
    RFC 7539 standard Poly1305 One-Time Message Authenticator.
    """
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("Poly1305 key must be exactly 32 bytes")
        self.r = clamp(key[:16])
        self.s = int.from_bytes(key[16:], "little")
        self.accumulator = 0

    def update(self, data: bytes):
        """Processes message bytes in 16-byte blocks."""
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            # Pad with 0x01 byte at chunk end
            val = int.from_bytes(chunk + b"\x01", "little")
            self.accumulator = ((self.accumulator + val) * self.r) % P

    def digest(self) -> bytes:
        """Returns 16-byte authentication tag."""
        tag_int = (self.accumulator + self.s) % (1 << 128)
        return tag_int.to_bytes(16, "little")

class ChaCha20Poly1305AEAD:
    """
    RFC 7539 ChaCha20-Poly1305 Authenticated Encryption with Associated Data (AEAD).
    """
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("AEAD key must be exactly 32 bytes")
        self.key = key

    def _poly1305_key_gen(self, nonce: bytes) -> bytes:
        """Generates the one-time Poly1305 key using ChaCha20 block 0."""
        cipher = ChaCha20(self.key, nonce, counter=0)
        # First 32 bytes of block 0
        return cipher._block(0)[:32]

    def seal(self, nonce: bytes, plaintext: bytes, associated_data: bytes = b"") -> tuple:
        """
        Encrypts plaintext and returns (ciphertext, 16_byte_tag).
        """
        poly_key = self._poly1305_key_gen(nonce)
        # Encrypt with counter = 1
        cipher = ChaCha20(self.key, nonce, counter=1)
        ciphertext = cipher.crypt(plaintext)

        # Construct MAC authentication stream:
        # AAD + padding to 16B + Ciphertext + padding to 16B + len(AAD) (64-bit LE) + len(Ciphertext) (64-bit LE)
        mac_data = bytearray()
        mac_data.extend(associated_data)
        if len(associated_data) % 16 != 0:
            mac_data.extend(b"\x00" * (16 - (len(associated_data) % 16)))

        mac_data.extend(ciphertext)
        if len(ciphertext) % 16 != 0:
            mac_data.extend(b"\x00" * (16 - (len(ciphertext) % 16)))

        mac_data.extend(struct.pack("<QQ", len(associated_data), len(ciphertext)))

        poly = Poly1305(poly_key)
        poly.update(mac_data)
        tag = poly.digest()

        return ciphertext, tag

    def open(self, nonce: bytes, ciphertext: bytes, tag: bytes, associated_data: bytes = b"") -> bytes:
        """
        Authenticates tag and decrypts ciphertext.
        Returns plaintext, or raises ValueError if authentication fails.
        """
        poly_key = self._poly1305_key_gen(nonce)

        mac_data = bytearray()
        mac_data.extend(associated_data)
        if len(associated_data) % 16 != 0:
            mac_data.extend(b"\x00" * (16 - (len(associated_data) % 16)))

        mac_data.extend(ciphertext)
        if len(ciphertext) % 16 != 0:
            mac_data.extend(b"\x00" * (16 - (len(ciphertext) % 16)))

        mac_data.extend(struct.pack("<QQ", len(associated_data), len(ciphertext)))

        poly = Poly1305(poly_key)
        poly.update(mac_data)
        expected_tag = poly.digest()

        # Constant-time comparison
        diff = 0
        for b1, b2 in zip(tag, expected_tag):
            diff |= (b1 ^ b2)

        if diff != 0 or len(tag) != len(expected_tag):
            raise ValueError("ChaCha20-Poly1305 authentication failed (Tag mismatch)")

        # Decrypt with counter = 1
        cipher = ChaCha20(self.key, nonce, counter=1)
        return cipher.crypt(ciphertext)

if __name__ == "__main__":
    key = b"12345678901234567890123456789012"
    nonce = b"nonce1234567"
    aead = ChaCha20Poly1305AEAD(key)
    msg = b"Top Secret Sovereign OS Network Packet"
    aad = b"HeaderInfo"
    ciphertext, tag = aead.seal(nonce, msg, aad)
    print(f"Sealed: {len(ciphertext)} bytes, Tag: {tag.hex()}")
    decrypted = aead.open(nonce, ciphertext, tag, aad)
    assert decrypted == msg
    print("ChaCha20-Poly1305 AEAD authenticated encryption verified.")
