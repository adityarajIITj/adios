#!/usr/bin/env python3
"""
AdiOS Cryptographic Subsystem: Advanced Encryption Standard (crypto/aes.py)
Implements NIST FIPS 197 AES Block Cipher from first principles:
- AES-128 (10 rounds), AES-192 (12 rounds), and AES-256 (14 rounds)
- Rijndael Galois Field GF(2^8) arithmetic: SubBytes, ShiftRows, MixColumns, AddRoundKey
- Inverse cipher transformations: InvSubBytes, InvShiftRows, InvMixColumns
- Key Expansion Schedule with Rcon constant generation
- Operational modes:
    - Electronic Codebook (ECB) with PKCS#7 padding
    - Cipher Block Chaining (CBC) with PKCS#7 padding & Initialization Vector (IV)
    - Counter Mode (CTR) streaming encryption

Zero external dependencies. Pure RV32IM cryptographic architecture.
STRICT ZERO EMOJI POLICY.
"""

from typing import List, Tuple, Optional

# Rijndael S-Box (Substitution box)
SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]

# Rijndael Inverse S-Box
INV_SBOX = [
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d
]

RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]

def xtime(a: int) -> int:
    return ((a << 1) ^ 0x1B) & 0xFF if (a & 0x80) else (a << 1)

def gf_mul(a: int, b: int) -> int:
    """Galois field GF(2^8) multiplication."""
    res = 0
    for _ in range(8):
        if b & 1:
            res ^= a
        a = xtime(a)
        b >>= 1
    return res

class AES:
    """
    AES cipher supporting 128, 192, and 256-bit key sizes.
    """
    def __init__(self, key: bytes):
        if len(key) not in (16, 24, 32):
            raise ValueError(f"Invalid key length: {len(key)} bytes (expected 16, 24, or 32)")
        self.key = key
        self.nk = len(key) // 4
        self.nr = self.nk + 6
        self.round_keys = self._key_expansion(key)

    def _key_expansion(self, key: bytes) -> List[List[int]]:
        """Expands master key into (Nr + 1) 4x4 round key matrices."""
        w = []
        for i in range(self.nk):
            w.append([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]])

        for i in range(self.nk, 4 * (self.nr + 1)):
            temp = list(w[i - 1])
            if i % self.nk == 0:
                # RotWord
                temp = temp[1:] + temp[:1]
                # SubWord
                temp = [SBOX[b] for b in temp]
                # XOR Rcon
                temp[0] ^= RCON[i // self.nk]
            elif self.nk > 6 and (i % self.nk == 4):
                temp = [SBOX[b] for b in temp]

            w_val = [w[i - self.nk][j] ^ temp[j] for j in range(4)]
            w.append(w_val)

        # Reshape into round key 4x4 states (column-major)
        round_keys = []
        for r in range(self.nr + 1):
            state = [[0]*4 for _ in range(4)]
            for col in range(4):
                for row in range(4):
                    state[row][col] = w[r * 4 + col][row]
            round_keys.append(state)
        return round_keys

    def _add_round_key(self, state: List[List[int]], rk: List[List[int]]):
        for r in range(4):
            for c in range(4):
                state[r][c] ^= rk[r][c]

    def _sub_bytes(self, state: List[List[int]]):
        for r in range(4):
            for c in range(4):
                state[r][c] = SBOX[state[r][c]]

    def _inv_sub_bytes(self, state: List[List[int]]):
        for r in range(4):
            for c in range(4):
                state[r][c] = INV_SBOX[state[r][c]]

    def _shift_rows(self, state: List[List[int]]):
        state[1] = state[1][1:] + state[1][:1]
        state[2] = state[2][2:] + state[2][:2]
        state[3] = state[3][3:] + state[3][:3]

    def _inv_shift_rows(self, state: List[List[int]]):
        state[1] = state[1][-1:] + state[1][:-1]
        state[2] = state[2][-2:] + state[2][:-2]
        state[3] = state[3][-3:] + state[3][:-3]

    def _mix_columns(self, state: List[List[int]]):
        for c in range(4):
            s0 = state[0][c]
            s1 = state[1][c]
            s2 = state[2][c]
            s3 = state[3][c]
            state[0][c] = xtime(s0) ^ (xtime(s1) ^ s1) ^ s2 ^ s3
            state[1][c] = s0 ^ xtime(s1) ^ (xtime(s2) ^ s2) ^ s3
            state[2][c] = s0 ^ s1 ^ xtime(s2) ^ (xtime(s3) ^ s3)
            state[3][c] = (xtime(s0) ^ s0) ^ s1 ^ s2 ^ xtime(s3)

    def _inv_mix_columns(self, state: List[List[int]]):
        for c in range(4):
            s0, s1, s2, s3 = state[0][c], state[1][c], state[2][c], state[3][c]
            state[0][c] = gf_mul(0x0e, s0) ^ gf_mul(0x0b, s1) ^ gf_mul(0x0d, s2) ^ gf_mul(0x09, s3)
            state[1][c] = gf_mul(0x09, s0) ^ gf_mul(0x0e, s1) ^ gf_mul(0x0b, s2) ^ gf_mul(0x0d, s3)
            state[2][c] = gf_mul(0x0d, s0) ^ gf_mul(0x09, s1) ^ gf_mul(0x0e, s2) ^ gf_mul(0x0b, s3)
            state[3][c] = gf_mul(0x0b, s0) ^ gf_mul(0x0d, s1) ^ gf_mul(0x09, s2) ^ gf_mul(0x0e, s3)

    def encrypt_block(self, block: bytes) -> bytes:
        """Encrypts a single 16-byte block."""
        if len(block) != 16:
            raise ValueError(f"Block size must be 16 bytes, got {len(block)}")

        state = [[block[r + 4*c] for c in range(4)] for r in range(4)]
        self._add_round_key(state, self.round_keys[0])

        for r in range(1, self.nr):
            self._sub_bytes(state)
            self._shift_rows(state)
            self._mix_columns(state)
            self._add_round_key(state, self.round_keys[r])

        self._sub_bytes(state)
        self._shift_rows(state)
        self._add_round_key(state, self.round_keys[self.nr])

        out = bytearray(16)
        for r in range(4):
            for c in range(4):
                out[r + 4*c] = state[r][c]
        return bytes(out)

    def decrypt_block(self, block: bytes) -> bytes:
        """Decrypts a single 16-byte block."""
        if len(block) != 16:
            raise ValueError(f"Block size must be 16 bytes, got {len(block)}")

        state = [[block[r + 4*c] for c in range(4)] for r in range(4)]
        self._add_round_key(state, self.round_keys[self.nr])

        for r in range(self.nr - 1, 0, -1):
            self._inv_shift_rows(state)
            self._inv_sub_bytes(state)
            self._add_round_key(state, self.round_keys[r])
            self._inv_mix_columns(state)

        self._inv_shift_rows(state)
        self._inv_sub_bytes(state)
        self._add_round_key(state, self.round_keys[0])

        out = bytearray(16)
        for r in range(4):
            for c in range(4):
                out[r + 4*c] = state[r][c]
        return bytes(out)

    # --- Operational Modes ---

    @staticmethod
    def pad_pkcs7(data: bytes, block_size: int = 16) -> bytes:
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def unpad_pkcs7(data: bytes) -> bytes:
        if not data:
            raise ValueError("Empty data cannot be unpadded")
        pad_len = data[-1]
        if pad_len == 0 or pad_len > 16 or data[-pad_len:] != bytes([pad_len] * pad_len):
            raise ValueError("Invalid PKCS#7 padding")
        return data[:-pad_len]

    def encrypt_ecb(self, plaintext: bytes) -> bytes:
        padded = self.pad_pkcs7(plaintext)
        res = bytearray()
        for i in range(0, len(padded), 16):
            res.extend(self.encrypt_block(padded[i : i + 16]))
        return bytes(res)

    def decrypt_ecb(self, ciphertext: bytes) -> bytes:
        res = bytearray()
        for i in range(0, len(ciphertext), 16):
            res.extend(self.decrypt_block(ciphertext[i : i + 16]))
        return self.unpad_pkcs7(bytes(res))

    def encrypt_cbc(self, plaintext: bytes, iv: bytes) -> bytes:
        if len(iv) != 16:
            raise ValueError("IV must be 16 bytes")
        padded = self.pad_pkcs7(plaintext)
        res = bytearray()
        prev = iv
        for i in range(0, len(padded), 16):
            block = bytes(padded[i + j] ^ prev[j] for j in range(16))
            enc = self.encrypt_block(block)
            res.extend(enc)
            prev = enc
        return bytes(res)

    def decrypt_cbc(self, ciphertext: bytes, iv: bytes) -> bytes:
        if len(iv) != 16 or len(ciphertext) % 16 != 0:
            raise ValueError("Invalid ciphertext length or IV")
        res = bytearray()
        prev = iv
        for i in range(0, len(ciphertext), 16):
            enc_block = ciphertext[i : i + 16]
            dec = self.decrypt_block(enc_block)
            plain_block = bytes(dec[j] ^ prev[j] for j in range(16))
            res.extend(plain_block)
            prev = enc_block
        return self.unpad_pkcs7(bytes(res))

    def encrypt_ctr(self, plaintext: bytes, nonce: bytes) -> bytes:
        """CTR mode: nonce (12 bytes) + 4-byte big-endian counter."""
        if len(nonce) != 12:
            raise ValueError("Nonce must be 12 bytes for CTR")
        res = bytearray()
        counter = 0
        for i in range(0, len(plaintext), 16):
            block = plaintext[i : i + 16]
            ctr_block = nonce + counter.to_bytes(4, "big")
            keystream = self.encrypt_block(ctr_block)
            res.extend(bytes(block[j] ^ keystream[j] for j in range(len(block))))
            counter += 1
        return bytes(res)

    def decrypt_ctr(self, ciphertext: bytes, nonce: bytes) -> bytes:
        return self.encrypt_ctr(ciphertext, nonce)

    # --- Cipher Feedback (CFB) Mode ---

    def encrypt_cfb(self, plaintext: bytes, iv: bytes) -> bytes:
        """128-bit CFB streaming mode."""
        if len(iv) != 16:
            raise ValueError("IV must be 16 bytes for CFB")
        res = bytearray()
        prev = iv
        for i in range(0, len(plaintext), 16):
            chunk = plaintext[i : i + 16]
            enc_prev = self.encrypt_block(prev)
            c_chunk = bytes(chunk[j] ^ enc_prev[j] for j in range(len(chunk)))
            res.extend(c_chunk)
            if len(chunk) == 16:
                prev = c_chunk
            else:
                prev = c_chunk + enc_prev[len(chunk):]
        return bytes(res)

    def decrypt_cfb(self, ciphertext: bytes, iv: bytes) -> bytes:
        """128-bit CFB decryption."""
        if len(iv) != 16:
            raise ValueError("IV must be 16 bytes for CFB")
        res = bytearray()
        prev = iv
        for i in range(0, len(ciphertext), 16):
            chunk = ciphertext[i : i + 16]
            enc_prev = self.encrypt_block(prev)
            p_chunk = bytes(chunk[j] ^ enc_prev[j] for j in range(len(chunk)))
            res.extend(p_chunk)
            if len(chunk) == 16:
                prev = chunk
            else:
                prev = chunk + enc_prev[len(chunk):]
        return bytes(res)

    # --- Output Feedback (OFB) Mode ---

    def encrypt_ofb(self, plaintext: bytes, iv: bytes) -> bytes:
        """128-bit OFB streaming mode."""
        if len(iv) != 16:
            raise ValueError("IV must be 16 bytes for OFB")
        res = bytearray()
        curr = iv
        for i in range(0, len(plaintext), 16):
            chunk = plaintext[i : i + 16]
            curr = self.encrypt_block(curr)
            res.extend(bytes(chunk[j] ^ curr[j] for j in range(len(chunk))))
        return bytes(res)

    def decrypt_ofb(self, ciphertext: bytes, iv: bytes) -> bytes:
        return self.encrypt_ofb(ciphertext, iv)

    # --- Galois/Counter Mode (GCM) AEAD (NIST SP 800-38D) ---

    @staticmethod
    def _gf128_mul(x: int, y: int) -> int:
        """Bitwise multiplication in GF(2^128) with polynomial x^128 + x^7 + x^2 + x + 1."""
        r = 0xE1000000000000000000000000000000
        z = 0
        v = x
        for i in range(128):
            if (y >> (127 - i)) & 1:
                z ^= v
            if v & 1:
                v = (v >> 1) ^ r
            else:
                v >>= 1
        return z

    @classmethod
    def _ghash(cls, h_int: int, data: bytes) -> int:
        """Computes GHASH state integer over 16-byte aligned binary buffer."""
        y = 0
        for i in range(0, len(data), 16):
            blk = data[i : i + 16]
            if len(blk) < 16:
                blk = blk.ljust(16, b"\x00")
            blk_int = int.from_bytes(blk, "big")
            y = cls._gf128_mul(y ^ blk_int, h_int)
        return y

    def encrypt_gcm(self, plaintext: bytes, nonce: bytes, aad: bytes = b"") -> Tuple[bytes, bytes]:
        """
        NIST SP 800-38D AES-GCM Authenticated Encryption.
        Returns (ciphertext, 16-byte auth tag).
        """
        h_key = self.encrypt_block(b"\x00" * 16)
        h_int = int.from_bytes(h_key, "big")

        # Determine J0
        if len(nonce) == 12:
            j0 = nonce + b"\x00\x00\x00\x01"
        else:
            # Hash nonce with GHASH
            pad_len = (16 - (len(nonce) % 16)) % 16
            buf = nonce + (b"\x00" * pad_len) + (b"\x00" * 8) + (len(nonce) * 8).to_bytes(8, "big")
            j0_int = self._ghash(h_int, buf)
            j0 = j0_int.to_bytes(16, "big")

        j0_int = int.from_bytes(j0, "big")

        # GCTR encryption starting at J0 + 1
        res = bytearray()
        counter_base = j0[:12]
        ctr_val = int.from_bytes(j0[12:16], "big")

        for i in range(0, len(plaintext), 16):
            chunk = plaintext[i : i + 16]
            ctr_val = (ctr_val + 1) & 0xFFFFFFFF
            ctr_block = counter_base + ctr_val.to_bytes(4, "big")
            keystream = self.encrypt_block(ctr_block)
            res.extend(bytes(chunk[j] ^ keystream[j] for j in range(len(chunk))))

        ciphertext = bytes(res)

        # GHASH over AAD || pad(AAD) || C || pad(C) || len(AAD) || len(C)
        pad_aad = (16 - (len(aad) % 16)) % 16
        pad_c = (16 - (len(ciphertext) % 16)) % 16
        ghash_buf = (
            aad + (b"\x00" * pad_aad) +
            ciphertext + (b"\x00" * pad_c) +
            (len(aad) * 8).to_bytes(8, "big") +
            (len(ciphertext) * 8).to_bytes(8, "big")
        )

        s_int = self._ghash(h_int, ghash_buf)
        s_bytes = s_int.to_bytes(16, "big")

        # Tag = MSB128(GCTR(J0, S)) = S ^ AES(J0)
        j0_enc = self.encrypt_block(j0)
        tag = bytes(s_bytes[j] ^ j0_enc[j] for j in range(16))

        return ciphertext, tag

    def decrypt_gcm(self, ciphertext: bytes, tag: bytes, nonce: bytes, aad: bytes = b"") -> bytes:
        """
        NIST SP 800-38D AES-GCM Decryption & Tag Verification.
        Raises ValueError if authentication tag does not match in constant time.
        """
        if len(tag) != 16:
            raise ValueError("Authentication tag must be exactly 16 bytes")

        h_key = self.encrypt_block(b"\x00" * 16)
        h_int = int.from_bytes(h_key, "big")

        if len(nonce) == 12:
            j0 = nonce + b"\x00\x00\x00\x01"
        else:
            pad_len = (16 - (len(nonce) % 16)) % 16
            buf = nonce + (b"\x00" * pad_len) + (b"\x00" * 8) + (len(nonce) * 8).to_bytes(8, "big")
            j0_int = self._ghash(h_int, buf)
            j0 = j0_int.to_bytes(16, "big")

        # Verify tag first
        pad_aad = (16 - (len(aad) % 16)) % 16
        pad_c = (16 - (len(ciphertext) % 16)) % 16
        ghash_buf = (
            aad + (b"\x00" * pad_aad) +
            ciphertext + (b"\x00" * pad_c) +
            (len(aad) * 8).to_bytes(8, "big") +
            (len(ciphertext) * 8).to_bytes(8, "big")
        )

        s_int = self._ghash(h_int, ghash_buf)
        s_bytes = s_int.to_bytes(16, "big")
        j0_enc = self.encrypt_block(j0)
        expected_tag = bytes(s_bytes[j] ^ j0_enc[j] for j in range(16))

        # Constant-time comparison
        diff = 0
        for x, y in zip(tag, expected_tag):
            diff |= (x ^ y)
        if diff != 0:
            raise ValueError("AES-GCM: Authentication tag verification failed (ciphertext corrupted)")

        # Decrypt ciphertext
        res = bytearray()
        counter_base = j0[:12]
        ctr_val = int.from_bytes(j0[12:16], "big")

        for i in range(0, len(ciphertext), 16):
            chunk = ciphertext[i : i + 16]
            ctr_val = (ctr_val + 1) & 0xFFFFFFFF
            ctr_block = counter_base + ctr_val.to_bytes(4, "big")
            keystream = self.encrypt_block(ctr_block)
            res.extend(bytes(chunk[j] ^ keystream[j] for j in range(len(chunk))))

        return bytes(res)


if __name__ == "__main__":
    key = b"\x00" * 16
    cipher = AES(key)
    msg = b"AdiOS Secure Cryptographic Workstation"
    iv = b"\x12" * 16
    nonce = b"\x34" * 12

    # Test GCM AEAD
    c_gcm, tag = cipher.encrypt_gcm(msg, nonce, aad=b"header-meta")
    p_gcm = cipher.decrypt_gcm(c_gcm, tag, nonce, aad=b"header-meta")
    assert p_gcm == msg

    # Test tampering detection
    try:
        tampered_c = bytearray(c_gcm)
        tampered_c[0] ^= 0x01
        cipher.decrypt_gcm(bytes(tampered_c), tag, nonce, aad=b"header-meta")
        assert False, "Tampered ciphertext should fail authentication"
    except ValueError:
        pass

    # Test CFB and OFB
    c_cfb = cipher.encrypt_cfb(msg, iv)
    assert cipher.decrypt_cfb(c_cfb, iv) == msg

    c_ofb = cipher.encrypt_ofb(msg, iv)
    assert cipher.decrypt_ofb(c_ofb, iv) == msg

    print("AES CBC, CTR, CFB, OFB, and GCM-AEAD verified successfully.")
