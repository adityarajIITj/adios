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

    @property
    def is_control(self) -> bool:
        return self.opcode in (OPCODE_CLOSE, OPCODE_PING, OPCODE_PONG)

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

WebSocketFrame.pack_frame = staticmethod(lambda opcode, payload, fin=True, is_masked=False, mask_key=None: WebSocketEngine.pack_frame(payload, opcode=opcode, fin=fin, mask_key=mask_key if is_masked else None))
WebSocketFrame.unpack_frame = staticmethod(WebSocketEngine.unpack_frame)

# =============================================================================
# Message Reassembly & Stateful Connection Engine
# =============================================================================

class WebSocketMessageReassembler:
    """Reassembles fragmented multi-frame messages according to RFC 6455."""
    def __init__(self):
        self.active_opcode: Optional[int] = None
        self.fragments: List[bytes] = []

    def feed_frame(self, frame: WebSocketFrame) -> Optional[Tuple[int, bytes]]:
        """Processes a frame, returning (opcode, complete_payload) when fully reassembled."""
        # Control frames can be interleaved between message fragments
        if frame.is_control:
            return (frame.opcode, frame.payload)

        if frame.opcode != OPCODE_CONTINUATION:
            # Initial fragment
            self.active_opcode = frame.opcode
            self.fragments = [frame.payload]
        else:
            # Continuation fragment
            if self.active_opcode is None:
                raise ValueError("Received continuation frame without initial frame")
            self.fragments.append(frame.payload)

        if frame.fin:
            complete_payload = b"".join(self.fragments)
            opcode = self.active_opcode
            self.active_opcode = None
            self.fragments = []
            return (opcode, complete_payload)

        return None


class WebSocketState:
    CONNECTING = 0
    OPEN = 1
    CLOSING = 2
    CLOSED = 3


class WebSocketConnection:
    """Stateful RFC 6455 WebSocket Connection endpoint with stream buffer."""
    def __init__(self, is_client: bool = False):
        self.is_client = is_client
        self.state = WebSocketState.OPEN
        self.rx_buffer = bytearray()
        self.reassembler = WebSocketMessageReassembler()
        self.close_code: Optional[int] = None
        self.close_reason: str = ""

    def feed_bytes(self, data: bytes) -> List[Tuple[int, Union[str, bytes]]]:
        """Processes incoming byte stream and returns complete messages."""
        self.rx_buffer.extend(data)
        messages = []

        while len(self.rx_buffer) >= 2:
            try:
                frame, consumed = WebSocketFrame.unpack_frame(bytes(self.rx_buffer))
                del self.rx_buffer[:consumed]
            except ValueError:
                # Need more bytes
                break

            result = self.reassembler.feed_frame(frame)
            if result is not None:
                op, pld = result
                if op == OPCODE_TEXT:
                    messages.append((op, pld.decode("utf-8", errors="replace")))
                elif op == OPCODE_BINARY:
                    messages.append((op, pld))
                elif op == OPCODE_CLOSE:
                    self.state = WebSocketState.CLOSED
                    if len(pld) >= 2:
                        self.close_code = struct.unpack("!H", pld[:2])[0]
                        self.close_reason = pld[2:].decode("utf-8", errors="replace")
                    messages.append((op, pld))
                elif op in (OPCODE_PING, OPCODE_PONG):
                    messages.append((op, pld))

        return messages

    def send_text(self, text: str) -> bytes:
        mask_key = b"\x12\x34\x56\x78" if self.is_client else None
        return WebSocketFrame.pack_frame(
            opcode=OPCODE_TEXT,
            payload=text.encode("utf-8"),
            fin=True,
            is_masked=self.is_client,
            mask_key=mask_key
        )

    def send_binary(self, data: bytes) -> bytes:
        mask_key = b"\x12\x34\x56\x78" if self.is_client else None
        return WebSocketFrame.pack_frame(
            opcode=OPCODE_BINARY,
            payload=data,
            fin=True,
            is_masked=self.is_client,
            mask_key=mask_key
        )

    def send_ping(self, payload: bytes = b"") -> bytes:
        return WebSocketFrame.pack_frame(
            opcode=OPCODE_PING,
            payload=payload,
            fin=True,
            is_masked=self.is_client,
            mask_key=b"\x01\x02\x03\x04" if self.is_client else None
        )

    def send_pong(self, payload: bytes = b"") -> bytes:
        return WebSocketFrame.pack_frame(
            opcode=OPCODE_PONG,
            payload=payload,
            fin=True,
            is_masked=self.is_client,
            mask_key=b"\x01\x02\x03\x04" if self.is_client else None
        )

    def send_close(self, code: int = 1000, reason: str = "") -> bytes:
        self.state = WebSocketState.CLOSING
        pld = struct.pack("!H", code) + reason.encode("utf-8")
        return WebSocketFrame.pack_frame(
            opcode=OPCODE_CLOSE,
            payload=pld,
            fin=True,
            is_masked=self.is_client,
            mask_key=b"\x01\x02\x03\x04" if self.is_client else None
        )


generate_accept_token = WebSocketEngine.generate_accept_token

if __name__ == "__main__":
    # Test WebSocket handshake key generation
    client_key = "dGhlIHNhbXBsZSBub25jZQ=="
    accept = generate_accept_token(client_key)
    assert accept == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="

    # Test Frame packing and unpacking
    raw_frame = WebSocketFrame.pack_frame(OPCODE_TEXT, b"Hello Sovereign WebSocket", fin=True, is_masked=False)
    frame, consumed = WebSocketFrame.unpack_frame(raw_frame)
    assert frame.payload == b"Hello Sovereign WebSocket"
    assert frame.opcode == OPCODE_TEXT
    assert consumed == len(raw_frame)

    # Test Fragmented reassembly
    f1 = WebSocketFrame.pack_frame(OPCODE_TEXT, b"Part 1 - ", fin=False)
    f2 = WebSocketFrame.pack_frame(OPCODE_CONTINUATION, b"Part 2", fin=True)
    conn = WebSocketConnection(is_client=False)
    msgs = conn.feed_bytes(f1 + f2)
    assert len(msgs) == 1
    assert msgs[0][1] == "Part 1 - Part 2"

    print("WebSocket protocol engine & reassembler verified.")
