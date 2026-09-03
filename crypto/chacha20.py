#!/usr/bin/env python3
"""
AdiOS Cryptographic Subsystem: ChaCha20 Stream Cipher (chacha20.py)
Implements RFC 7539 standard ChaCha20 stream cipher from first principles.
Zero external dependencies.
"""

import struct

def rotl32(v: int, c: int) -> int:
    """32-bit circular left rotate."""
    return ((v << c) | (v >> (32 - c))) & 0xFFFFFFFF

def quarter_round(state: list, a: int, b: int, c: int, d: int):
    """RFC 7539 ChaCha20 Quarter Round operation."""
    state[a] = (state[a] + state[b]) & 0xFFFFFFFF
    state[d] = rotl32(state[d] ^ state[a], 16)

    state[c] = (state[c] + state[d]) & 0xFFFFFFFF
    state[b] = rotl32(state[b] ^ state[c], 12)

    state[a] = (state[a] + state[b]) & 0xFFFFFFFF
    state[d] = rotl32(state[d] ^ state[a], 8)

    state[c] = (state[c] + state[d]) & 0xFFFFFFFF
    state[b] = rotl32(state[b] ^ state[c], 7)

class ChaCha20:
    """
    RFC 7539 standard ChaCha20 256-bit stream cipher.
    """
    def __init__(self, key: bytes, nonce: bytes, counter: int = 1):
        if len(key) != 32:
            raise ValueError("ChaCha20 key must be exactly 32 bytes (256 bits)")
        if len(nonce) != 12:
            raise ValueError("ChaCha20 nonce must be exactly 12 bytes (96 bits)")

        self.key = key
        self.nonce = nonce
        self.counter = counter & 0xFFFFFFFF

    def _block(self, counter: int) -> bytes:
        """Generates a single 64-byte keystream block."""
        # Constants "expand 32-byte k"
        c0, c1, c2, c3 = 0x61707865, 0x3320646e, 0x79622d32, 0x6b206574
        k = list(struct.unpack("<8I", self.key))
        n = list(struct.unpack("<3I", self.nonce))

        initial_state = [
            c0, c1, c2, c3,
            k[0], k[1], k[2], k[3],
            k[4], k[5], k[6], k[7],
            counter & 0xFFFFFFFF, n[0], n[1], n[2]
        ]

        state = list(initial_state)

        # 10 double-rounds = 20 rounds total
        for _ in range(10):
            # Column rounds
            quarter_round(state, 0, 4, 8, 12)
            quarter_round(state, 1, 5, 9, 13)
            quarter_round(state, 2, 6, 10, 14)
            quarter_round(state, 3, 7, 11, 15)
            # Diagonal rounds
            quarter_round(state, 0, 5, 10, 15)
            quarter_round(state, 1, 6, 11, 12)
            quarter_round(state, 2, 7, 8, 13)
            quarter_round(state, 3, 4, 9, 14)

        # Add initial state back into mixed state
        out_state = [(state[i] + initial_state[i]) & 0xFFFFFFFF for i in range(16)]
        return struct.pack("<16I", *out_state)

    def crypt(self, plaintext: bytes) -> bytes:
        """
        Encrypts or decrypts arbitrary-length data by XORing with the keystream.
        (Symmetric operation: crypt(crypt(m)) == m).
        """
        ciphertext = bytearray()
        counter = self.counter

        for i in range(0, len(plaintext), 64):
            block = self._block(counter)
            chunk = plaintext[i:i + 64]
            keystream = block[:len(chunk)]
            ciphertext.extend(b1 ^ b2 for b1, b2 in zip(chunk, keystream))
            counter = (counter + 1) & 0xFFFFFFFF

        return bytes(ciphertext)

    def encrypt(self, data: bytes) -> bytes:
        return self.crypt(data)

    def decrypt(self, data: bytes) -> bytes:
        return self.crypt(data)

if __name__ == "__main__":
    key = b"0123456789abcdef0123456789abcdef"
    nonce = b"abcdef123456"
    cipher = ChaCha20(key, nonce)
    secret = b"Sovereign Computing Zero-Bloat Operating System"
    encrypted = cipher.encrypt(secret)
    print(f"Encrypted ({len(encrypted)} bytes): {encrypted.hex()}")
    decipher = ChaCha20(key, nonce)
    decrypted = decipher.decrypt(encrypted)
    assert decrypted == secret
    print("ChaCha20 roundtrip encryption/decryption verified.")
