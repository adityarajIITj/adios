#!/usr/bin/env python3
"""
AdiOS Cryptographic Subsystem: SHA-256 & HMAC-SHA256 Engine (sha256.py)
Implements FIPS 180-4 Secure Hash Standard and RFC 2104 Keyed-Hashing from first principles.
Zero external dependencies.
"""

import struct

# Initial Hash Values (FIPS 180-4 Section 5.3.3)
H_INIT = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
]

# Round Constants (FIPS 180-4 Section 4.2.2)
K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]

def ror(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF

class SHA256:
    """
    FIPS 180-4 standard SHA-256 cryptographic hash engine.
    """
    def __init__(self, data: bytes = None):
        self.h = list(H_INIT)
        self.unprocessed = bytearray()
        self.byte_count = 0
        if data:
            self.update(data)

    def update(self, data: bytes):
        """Processes an arbitrary byte sequence."""
        self.unprocessed.extend(data)
        self.byte_count += len(data)

        while len(self.unprocessed) >= 64:
            chunk = bytes(self.unprocessed[:64])
            del self.unprocessed[:64]
            self._transform(chunk)

    def _transform(self, chunk: bytes):
        """Processes a single 512-bit (64-byte) block."""
        w = list(struct.unpack("!16I", chunk)) + [0] * 48

        for t in range(16, 64):
            s0 = ror(w[t - 15], 7) ^ ror(w[t - 15], 18) ^ (w[t - 15] >> 3)
            s1 = ror(w[t - 2], 17) ^ ror(w[t - 2], 19) ^ (w[t - 2] >> 10)
            w[t] = (w[t - 16] + s0 + w[t - 7] + s1) & 0xFFFFFFFF

        a, b, c, d, e, f, g, h = self.h

        for t in range(64):
            S1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25)
            ch = (e & f) ^ ((~e) & g)
            temp1 = (h + S1 + ch + K[t] + w[t]) & 0xFFFFFFFF
            S0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22)
            maj = (a & b) ^ (a & c) ^ (b & c)
            temp2 = (S0 + maj) & 0xFFFFFFFF

            h = g
            g = f
            f = e
            e = (d + temp1) & 0xFFFFFFFF
            d = c
            c = b
            b = a
            a = (temp1 + temp2) & 0xFFFFFFFF

        self.h[0] = (self.h[0] + a) & 0xFFFFFFFF
        self.h[1] = (self.h[1] + b) & 0xFFFFFFFF
        self.h[2] = (self.h[2] + c) & 0xFFFFFFFF
        self.h[3] = (self.h[3] + d) & 0xFFFFFFFF
        self.h[4] = (self.h[4] + e) & 0xFFFFFFFF
        self.h[5] = (self.h[5] + f) & 0xFFFFFFFF
        self.h[6] = (self.h[6] + g) & 0xFFFFFFFF
        self.h[7] = (self.h[7] + h) & 0xFFFFFFFF

    def digest(self) -> bytes:
        """Finalizes the hash and returns the 32-byte digest."""
        # Make a copy of state to allow continuous hashing
        h_copy = list(self.h)
        unprocessed_copy = bytearray(self.unprocessed)
        total_bits = self.byte_count * 8

        # Append '1' bit (0x80)
        unprocessed_copy.append(0x80)

        # Pad with zeros until length == 56 mod 64
        while len(unprocessed_copy) % 64 != 56:
            unprocessed_copy.append(0x00)

        # Append 64-bit big-endian bit length
        unprocessed_copy.extend(struct.pack("!Q", total_bits))

        for i in range(0, len(unprocessed_copy), 64):
            chunk = bytes(unprocessed_copy[i:i + 64])
            w = list(struct.unpack("!16I", chunk)) + [0] * 48

            for t in range(16, 64):
                s0 = ror(w[t - 15], 7) ^ ror(w[t - 15], 18) ^ (w[t - 15] >> 3)
                s1 = ror(w[t - 2], 17) ^ ror(w[t - 2], 19) ^ (w[t - 2] >> 10)
                w[t] = (w[t - 16] + s0 + w[t - 7] + s1) & 0xFFFFFFFF

            a, b, c, d, e, f, g, h = h_copy

            for t in range(64):
                S1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25)
                ch = (e & f) ^ ((~e) & g)
                temp1 = (h + S1 + ch + K[t] + w[t]) & 0xFFFFFFFF
                S0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22)
                maj = (a & b) ^ (a & c) ^ (b & c)
                temp2 = (S0 + maj) & 0xFFFFFFFF

                h = g
                g = f
                f = e
                e = (d + temp1) & 0xFFFFFFFF
                d = c
                c = b
                b = a
                a = (temp1 + temp2) & 0xFFFFFFFF

            h_copy[0] = (h_copy[0] + a) & 0xFFFFFFFF
            h_copy[1] = (h_copy[1] + b) & 0xFFFFFFFF
            h_copy[2] = (h_copy[2] + c) & 0xFFFFFFFF
            h_copy[3] = (h_copy[3] + d) & 0xFFFFFFFF
            h_copy[4] = (h_copy[4] + e) & 0xFFFFFFFF
            h_copy[5] = (h_copy[5] + f) & 0xFFFFFFFF
            h_copy[6] = (h_copy[6] + g) & 0xFFFFFFFF
            h_copy[7] = (h_copy[7] + h) & 0xFFFFFFFF

        return struct.pack("!8I", *h_copy)

    def hexdigest(self) -> str:
        """Returns the hex-encoded 64-character digest string."""
        return self.digest().hex()

def sha256_hash(data: bytes) -> bytes:
    return SHA256(data).digest()

def hmac_sha256(key: bytes, message: bytes) -> bytes:
    """
    RFC 2104 Keyed-Hashing for Message Authentication (HMAC-SHA256).
    """
    block_size = 64
    if len(key) > block_size:
        key = sha256_hash(key)
    if len(key) < block_size:
        key = key.ljust(block_size, b"\x00")

    o_key_pad = bytes(b ^ 0x5C for b in key)
    i_key_pad = bytes(b ^ 0x36 for b in key)

    inner = sha256_hash(i_key_pad + message)
    return sha256_hash(o_key_pad + inner)

if __name__ == "__main__":
    msg = b"AdiOS Sovereign Computing"
    h = SHA256(msg).hexdigest()
    print(f"SHA-256('{msg.decode()}'):\n  {h}")
    key = b"sovereign_secret_key"
    mac = hmac_sha256(key, msg).hex()
    print(f"HMAC-SHA256:\n  {mac}")
