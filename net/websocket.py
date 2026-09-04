#!/usr/bin/env python3
"""
AdiOS Network Subsystem: WebSocket Protocol RFC 6455 (net/websocket.py)
Implements full duplex WebSocket framing and handshake server/client protocol:
- RFC 6455 Framing: FIN, RSV, Opcode (Text, Binary, Close, Ping, Pong)
- Extended payload length decoding (7-bit, 16-bit, 64-bit integer lengths)
- XOR 4-byte client-to-server payload masking and unmasking
- HTTP/1.1 Upgrade Handshake negotiation:
    - In-house pure SHA-1 digest algorithm (RFC 3174)
    - In-house pure Base64 encoder (RFC 4648)
    - Sec-WebSocket-Accept token derivation using standard GUID:
      "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

Zero external dependencies. Pure RV32IM network protocol engine.
STRICT ZERO EMOJI POLICY.
"""

import struct
from typing import Tuple, Optional, Dict, Any, List

# WebSocket Opcodes
OPCODE_CONTINUATION = 0x0
OPCODE_TEXT         = 0x1
OPCODE_BINARY       = 0x2
OPCODE_CLOSE        = 0x8
OPCODE_PING         = 0x9
OPCODE_PONG         = 0xA

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# --- In-house Pure SHA-1 (RFC 3174) ---

def sha1(data: bytes) -> bytes:
    """Computes 160-bit SHA-1 digest from raw bytes."""
    h0 = 0x67452301
    h1 = 0xEFCDAB89
    h2 = 0x98BADCFE
    h3 = 0x10325476
    h4 = 0xC3D2E1F0

    orig_len_bits = len(data) * 8
    # Pre-processing (Padding)
    data = bytearray(data)
    data.append(0x80)
    while (len(data) % 64) != 56:
        data.append(0x00)
    data.extend(orig_len_bits.to_bytes(8, "big"))

    # Process each 512-bit (64-byte) chunk
    for chunk_idx in range(0, len(data), 64):
        chunk = data[chunk_idx : chunk_idx + 64]
        w = [0] * 80
        for i in range(16):
            w[i] = int.from_bytes(chunk[i*4 : (i+1)*4], "big")
        for i in range(16, 80):
            val = w[i-3] ^ w[i-8] ^ w[i-14] ^ w[i-16]
            w[i] = ((val << 1) | (val >> 31)) & 0xFFFFFFFF

        a, b, c, d, e = h0, h1, h2, h3, h4

        for i in range(80):
            if 0 <= i <= 19:
                f = (b & c) | ((~b) & d)
                k = 0x5A827999
            elif 20 <= i <= 39:
                f = b ^ c ^ d
                k = 0x6ED9EBA1
            elif 40 <= i <= 59:
                f = (b & c) | (b & d) | (c & d)
                k = 0x8F1BBCDC
            else:
                f = b ^ c ^ d
                k = 0xCA62C1D6

            temp = (((a << 5) | (a >> 27)) + f + e + k + w[i]) & 0xFFFFFFFF
            e = d
            d = c
            c = ((b << 30) | (b >> 2)) & 0xFFFFFFFF
            b = a
            a = temp

        h0 = (h0 + a) & 0xFFFFFFFF
        h1 = (h1 + b) & 0xFFFFFFFF
        h2 = (h2 + c) & 0xFFFFFFFF
        h3 = (h3 + d) & 0xFFFFFFFF
        h4 = (h4 + e) & 0xFFFFFFFF

    return struct.pack(">5I", h0, h1, h2, h3, h4)

# --- In-house Pure Base64 (RFC 4648) ---

B64_CHARS = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def b64encode(data: bytes) -> str:
    """Encodes bytes to standard Base64 string."""
    out = []
    n = len(data)
    for i in range(0, n, 3):
        chunk = data[i:i+3]
        if len(chunk) == 3:
            val = (chunk[0] << 16) | (chunk[1] << 8) | chunk[2]
            out.append(chr(B64_CHARS[(val >> 18) & 0x3F]))
            out.append(chr(B64_CHARS[(val >> 12) & 0x3F]))
            out.append(chr(B64_CHARS[(val >> 6) & 0x3F]))
            out.append(chr(B64_CHARS[val & 0x3F]))
        elif len(chunk) == 2:
            val = (chunk[0] << 16) | (chunk[1] << 8)
            out.append(chr(B64_CHARS[(val >> 18) & 0x3F]))
            out.append(chr(B64_CHARS[(val >> 12) & 0x3F]))
            out.append(chr(B64_CHARS[(val >> 6) & 0x3F]))
            out.append("=")
        else:
            val = chunk[0] << 16
            out.append(chr(B64_CHARS[(val >> 18) & 0x3F]))
            out.append(chr(B64_CHARS[(val >> 12) & 0x3F]))
            out.append("==")
    return "".join(out)

class WebSocketFrame:
    """
    Decoded WebSocket Frame.
    """
    def __init__(self, opcode: int, payload: bytes, fin: bool = True, masked: bool = False):
        self.opcode = opcode
        self.payload = payload
        self.fin = fin
        self.masked = masked

    @property
    def is_text(self) -> bool:
        return self.opcode == OPCODE_TEXT

    @property
    def is_binary(self) -> bool:
        return self.opcode == OPCODE_BINARY

    @property
    def is_close(self) -> bool:
        return self.opcode == OPCODE_CLOSE

    def text(self) -> str:
        return self.payload.decode("utf-8", errors="replace")

class WebSocketEngine:
    """
    Handles RFC 6455 WebSocket Handshake and Frame serialization.
    """
    @staticmethod
    def generate_accept_token(client_key: str) -> str:
        """Derives Sec-WebSocket-Accept token from Sec-WebSocket-Key."""
        concat = (client_key.strip() + WS_GUID).encode("ascii")
        digest = sha1(concat)
        return b64encode(digest)

    @staticmethod
    def create_server_handshake_response(client_key: str) -> str:
        accept_token = WebSocketEngine.generate_accept_token(client_key)
        return (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_token}\r\n\r\n"
        )

    @staticmethod
    def pack_frame(payload: bytes, opcode: int = OPCODE_TEXT, fin: bool = True, mask_key: Optional[bytes] = None) -> bytes:
        """Serializes payload into a binary WebSocket frame."""
        header = bytearray()
        b0 = (0x80 if fin else 0) | (opcode & 0x0F)
        header.append(b0)

        length = len(payload)
        is_masked = mask_key is not None
        b1 = 0x80 if is_masked else 0x00

        if length <= 125:
            header.append(b1 | length)
        elif length <= 65535:
            header.append(b1 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(b1 | 127)
            header.extend(struct.pack("!Q", length))

        if is_masked:
            if len(mask_key) != 4:
                raise ValueError("Mask key must be 4 bytes")
            header.extend(mask_key)
            masked_payload = bytes(payload[i] ^ mask_key[i % 4] for i in range(length))
            return bytes(header) + masked_payload
        else:
            return bytes(header) + payload

    @staticmethod
    def unpack_frame(raw: bytes) -> Tuple[WebSocketFrame, int]:
        """
        Unpacks a single WebSocket frame from raw stream.
        Returns (frame, bytes_consumed).
        """
        if len(raw) < 2:
            raise ValueError("Buffer too short for WebSocket header")

        b0 = raw[0]
        b1 = raw[1]

        fin = bool(b0 & 0x80)
        opcode = b0 & 0x0F
        masked = bool(b1 & 0x80)
        payload_len = b1 & 0x7F

        offset = 2
        if payload_len == 126:
            if len(raw) < offset + 2:
                raise ValueError("Incomplete 16-bit extended length")
            payload_len = struct.unpack_from("!H", raw, offset)[0]
            offset += 2
        elif payload_len == 127:
            if len(raw) < offset + 8:
                raise ValueError("Incomplete 64-bit extended length")
            payload_len = struct.unpack_from("!Q", raw, offset)[0]
            offset += 8

        mask_key = None
        if masked:
            if len(raw) < offset + 4:
                raise ValueError("Incomplete mask key")
            mask_key = raw[offset : offset + 4]
            offset += 4

        if len(raw) < offset + payload_len:
            raise ValueError(f"Incomplete payload: expected {payload_len}, got {len(raw) - offset}")

        raw_payload = raw[offset : offset + payload_len]
        if masked and mask_key:
            payload = bytes(raw_payload[i] ^ mask_key[i % 4] for i in range(payload_len))
        else:
            payload = raw_payload

        frame = WebSocketFrame(opcode=opcode, payload=payload, fin=fin, masked=masked)
        return frame, offset + payload_len
