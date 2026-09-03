#!/usr/bin/env python3
"""
AdiOS Networking Subsystem: Serial Line Internet Protocol (SLIP) Driver (slip.py)
Implements RFC 1055 standard packet framing over serial MMIO UART (0x10000000).
Features:
- Standard SLIP framing with END (0xC0) and ESC (0xDB) byte stuffing
- Continuous stream decoder with state-machine packet extraction
- Full bidirectional packet encapsulation and decapsulation
"""

SLIP_END     = 0xC0
SLIP_ESC     = 0xDB
SLIP_ESC_END = 0xDC
SLIP_ESC_ESC = 0xDD

class SLIPDriver:
    """
    RFC 1055 SLIP packet encoder and stateful stream decoder.
    """
    def __init__(self):
        self.rx_buffer = bytearray()
        self.in_escape = False

    @staticmethod
    def encode_packet(packet_bytes: bytes) -> bytes:
        """
        Encapsulates raw IP/Ethernet packet bytes into a SLIP-framed byte sequence.
        """
        out = bytearray([SLIP_END])
        for b in packet_bytes:
            if b == SLIP_END:
                out.append(SLIP_ESC)
                out.append(SLIP_ESC_END)
            elif b == SLIP_ESC:
                out.append(SLIP_ESC)
                out.append(SLIP_ESC_ESC)
            else:
                out.append(b)
        out.append(SLIP_END)
        return bytes(out)

    def feed_byte(self, b: int) -> bytes:
        """
        Feeds a single byte from the serial stream into the decoder.
        Returns complete packet bytes when an unescaped SLIP_END delimiter is encountered,
        or None if more bytes are needed.
        """
        b &= 0xFF
        if self.in_escape:
            self.in_escape = False
            if b == SLIP_ESC_END:
                self.rx_buffer.append(SLIP_END)
            elif b == SLIP_ESC_ESC:
                self.rx_buffer.append(SLIP_ESC)
            else:
                # Protocol violation: append raw byte
                self.rx_buffer.append(b)
            return None

        if b == SLIP_ESC:
            self.in_escape = True
            return None
        elif b == SLIP_END:
            if len(self.rx_buffer) > 0:
                pkt = bytes(self.rx_buffer)
                self.rx_buffer.clear()
                return pkt
            return None
        else:
            self.rx_buffer.append(b)
            return None

    def feed_stream(self, data: bytes) -> list:
        """
        Processes a block of bytes and returns all complete extracted packets.
        """
        packets = []
        for b in data:
            pkt = self.feed_byte(b)
            if pkt is not None:
                packets.append(pkt)
        return packets

if __name__ == "__main__":
    driver = SLIPDriver()
    payload = b"GET /matrix HTTP/1.0\r\n\xC0\xDB"
    framed = SLIPDriver.encode_packet(payload)
    print(f"Original: {len(payload)} bytes -> Framed: {len(framed)} bytes")
    recovered = driver.feed_stream(framed)
    assert len(recovered) == 1
    assert recovered[0] == payload
    print("SLIP framing verification successful.")
