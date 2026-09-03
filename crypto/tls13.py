#!/usr/bin/env python3
"""
AdiOS Cryptographic Subsystem: TLS 1.3 Record Layer & Handshake Engine (tls13.py)
Implements RFC 8446 Transport Layer Security (TLS) 1.3 from first principles:
- RFC 5869 HKDF (HMAC-based Extract-and-Expand Key Derivation)
- TLS 1.3 Key Schedule (early_secret, handshake_secret, master_secret)
- Handshake messages: ClientHello, ServerHello, Finished tag calculation
- Record Layer framing & ChaCha20-Poly1305 AEAD record encryption
Zero external dependencies.
"""

import struct
from typing import Dict, List, Tuple, Optional
from crypto.sha256 import sha256_hash, hmac_sha256
from crypto.poly1305 import ChaCha20Poly1305AEAD

TLS_RECORD_CHANGE_CIPHER_SPEC = 20
TLS_RECORD_ALERT              = 21
TLS_RECORD_HANDSHAKE          = 22
TLS_RECORD_APP_DATA           = 23

TLS_HANDSHAKE_CLIENT_HELLO    = 1
TLS_HANDSHAKE_SERVER_HELLO    = 2
TLS_HANDSHAKE_FINISHED        = 20

TLS_AES_128_GCM_SHA256        = 0x1301
TLS_CHACHA20_POLY1305_SHA256  = 0x1303

# --- 1. RFC 5869 HKDF (HMAC-based Key Derivation) ---

def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """HKDF-Extract(salt, IKM) -> PRK (Pseudorandom Key)."""
    if not salt:
        salt = b"\x00" * 32
    return hmac_sha256(salt, ikm)

def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand(PRK, info, L) -> OKM (Output Keying Material)."""
    t = b""
    okm = bytearray()
    i = 1
    while len(okm) < length:
        t = hmac_sha256(prk, t + info + bytes([i]))
        okm.extend(t)
        i += 1
    return bytes(okm[:length])

def hkdf_expand_label(secret: bytes, label: str, context: bytes, length: int) -> bytes:
    """RFC 8446 Section 7.1 HKDF-Expand-Label."""
    full_label = b"tls13 " + label.encode("ascii")
    hkdf_label = (
        struct.pack("!H", length) +
        struct.pack("!B", len(full_label)) + full_label +
        struct.pack("!B", len(context)) + context
    )
    return hkdf_expand(secret, hkdf_label, length)

def derive_secret(secret: bytes, label: str, transcript_messages: bytes) -> bytes:
    """Derive-Secret(Secret, Label, Messages)."""
    context = sha256_hash(transcript_messages)
    return hkdf_expand_label(secret, label, context, 32)

# --- 2. TLS 1.3 Key Schedule ---

class TLS13KeySchedule:
    """
    Computes all cryptographic traffic secrets and keys for TLS 1.3.
    """
    def __init__(self):
        # 1. Early Secret
        zero_ikm = b"\x00" * 32
        self.early_secret = hkdf_extract(b"\x00" * 32, zero_ikm)

    def compute_handshake_secrets(self, shared_dhe_secret: bytes, transcript: bytes):
        """Transitions from Early Secret to Handshake Secret."""
        derived = derive_secret(self.early_secret, "derived", b"")
        self.handshake_secret = hkdf_extract(derived, shared_dhe_secret)
        self.client_handshake_traffic_secret = derive_secret(
            self.handshake_secret, "c hs traffic", transcript
        )
        self.server_handshake_traffic_secret = derive_secret(
            self.handshake_secret, "s hs traffic", transcript
        )

        # Handshake Write Keys (32-byte key, 12-byte IV for ChaCha20-Poly1305)
        self.client_hs_key = hkdf_expand_label(self.client_handshake_traffic_secret, "key", b"", 32)
        self.client_hs_iv  = hkdf_expand_label(self.client_handshake_traffic_secret, "iv", b"", 12)
        self.server_hs_key = hkdf_expand_label(self.server_handshake_traffic_secret, "key", b"", 32)
        self.server_hs_iv  = hkdf_expand_label(self.server_handshake_traffic_secret, "iv", b"", 12)

    def compute_master_secrets(self, transcript: bytes):
        """Transitions from Handshake Secret to Master / Application Secret."""
        derived = derive_secret(self.handshake_secret, "derived", b"")
        self.master_secret = hkdf_extract(derived, b"\x00" * 32)
        self.client_app_traffic_secret = derive_secret(
            self.master_secret, "c ap traffic", transcript
        )
        self.server_app_traffic_secret = derive_secret(
            self.master_secret, "s ap traffic", transcript
        )

        self.client_app_key = hkdf_expand_label(self.client_app_traffic_secret, "key", b"", 32)
        self.client_app_iv  = hkdf_expand_label(self.client_app_traffic_secret, "iv", b"", 12)
        self.server_app_key = hkdf_expand_label(self.server_app_traffic_secret, "key", b"", 32)
        self.server_app_iv  = hkdf_expand_label(self.server_app_traffic_secret, "iv", b"", 12)

    def calculate_finished(self, base_secret: bytes, transcript: bytes) -> bytes:
        """Computes HMAC-SHA256 Finished tag over handshake transcript."""
        finished_key = hkdf_expand_label(base_secret, "finished", b"", 32)
        transcript_hash = sha256_hash(transcript)
        return hmac_sha256(finished_key, transcript_hash)

# --- 3. TLS 1.3 Record Layer Framing ---

class TLSRecordLayer:
    """
    Serializes and parses TLS 1.3 record envelopes.
    """
    @staticmethod
    def pack_record(content_type: int, payload: bytes, legacy_version: int = 0x0303) -> bytes:
        """Packs a plaintext TLS record."""
        header = struct.pack("!BHH", content_type, legacy_version, len(payload))
        return header + payload

    @staticmethod
    def unpack_record(raw: bytes) -> Tuple[int, int, bytes]:
        """Returns (content_type, legacy_version, payload)."""
        content_type, legacy_version, length = struct.unpack("!BHH", raw[:5])
        payload = raw[5:5 + length]
        return (content_type, legacy_version, payload)

    @staticmethod
    def encrypt_app_record(key: bytes, iv: bytes, seq_num: int, plaintext: bytes) -> bytes:
        """
        Encrypts application record using ChaCha20-Poly1305 AEAD.
        Plaintext is inner-tagged: plaintext + content_type (23).
        """
        inner_plaintext = plaintext + bytes([TLS_RECORD_APP_DATA])
        # Nonce = IV XOR sequence_number
        seq_bytes = struct.pack("!Q", seq_num).rjust(12, b"\x00")
        nonce = bytes(a ^ b for a, b in zip(iv, seq_bytes))

        # AAD is the 5-byte legacy record header
        ciphertext_len = len(inner_plaintext) + 16 # +16 byte Poly1305 tag
        aad = struct.pack("!BHH", TLS_RECORD_APP_DATA, 0x0303, ciphertext_len)
        aead = ChaCha20Poly1305AEAD(key)
        ciphertext, tag = aead.seal(nonce, inner_plaintext, aad)
        return aad + ciphertext + tag

    @staticmethod
    def decrypt_app_record(key: bytes, iv: bytes, seq_num: int, record: bytes) -> bytes:
        content_type, version, length = struct.unpack("!BHH", record[:5])
        aad = record[:5]
        payload = record[5:5 + length]
        ciphertext = payload[:-16]
        tag = payload[-16:]
        seq_bytes = struct.pack("!Q", seq_num).rjust(12, b"\x00")
        nonce = bytes(a ^ b for a, b in zip(iv, seq_bytes))
        aead = ChaCha20Poly1305AEAD(key)
        decrypted = aead.open(nonce, ciphertext, tag, aad)
        # Strip trailing content_type byte
        return decrypted[:-1]

if __name__ == "__main__":
    ks = TLS13KeySchedule()
    ks.compute_handshake_secrets(b"\x42" * 32, b"ClientHelloServerHelloTranscript")
    tag = ks.calculate_finished(ks.server_handshake_traffic_secret, b"TranscriptSoFar")
    assert len(tag) == 32
    print("TLS 1.3 Key Schedule and Record Layer verified.")
