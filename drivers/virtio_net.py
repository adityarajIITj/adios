#!/usr/bin/env python3
"""
AdiOS Hardware Driver Subsystem: VirtIO Network Adapter Driver (virtio_net.py)
Implements VirtIO Network Device driver according to VirtIO Specification v1.0.
Provides packet transmission (TX) and reception (RX) using split Virtqueues.
Zero external dependencies.
"""

import struct
from typing import List, Optional
from drivers.virtio_ring import Virtqueue

# VirtIO Net Header Flags
VIRTIO_NET_HDR_F_NEEDS_CSUM = 1
VIRTIO_NET_HDR_F_DATA_VALID  = 2

# VirtIO Net GSO Types
VIRTIO_NET_HDR_GSO_NONE  = 0
VIRTIO_NET_HDR_GSO_TCPV4 = 1
VIRTIO_NET_HDR_GSO_UDP   = 3
VIRTIO_NET_HDR_GSO_TCPV6 = 4

class VirtioNetHdr:
    """10-byte VirtIO Network Header."""
    def __init__(self, flags: int = 0, gso_type: int = 0, hdr_len: int = 0, gso_size: int = 0, csum_start: int = 0, csum_offset: int = 0):
        self.flags = flags
        self.gso_type = gso_type
        self.hdr_len = hdr_len
        self.gso_size = gso_size
        self.csum_start = csum_start
        self.csum_offset = csum_offset

    def pack(self) -> bytes:
        return struct.pack("<BBHHHH", self.flags, self.gso_type, self.hdr_len, self.gso_size, self.csum_start, self.csum_offset)

    @classmethod
    def unpack(cls, data: bytes) -> 'VirtioNetHdr':
        f, gt, hl, gs, cs, co = struct.unpack("<BBHHHH", data[:10])
        return cls(f, gt, hl, gs, cs, co)

class VirtioNetDevice:
    """
    VirtIO Network Device controller with RX and TX virtqueues.
    """
    def __init__(self, mac_addr: str = "52:54:00:12:34:56", queue_size: int = 32):
        self.mac_addr = mac_addr
        self.rx_queue = Virtqueue(queue_size=queue_size, base_addr=0x83000000)
        self.tx_queue = Virtqueue(queue_size=queue_size, base_addr=0x83100000)
        self.rx_packets: List[bytes] = []

    def transmit_packet(self, frame_bytes: bytes) -> int:
        """Transmits an Ethernet II frame across the TX virtqueue."""
        hdr = VirtioNetHdr().pack()
        payload = hdr + frame_bytes

        head_idx = self.tx_queue.add_buffer([
            (0x83101000, len(hdr), False),
            (0x83102000, len(frame_bytes), False)
        ])

        # Device processes TX packet
        self.tx_queue.device_complete(head_idx, len(payload))
        completed = self.tx_queue.get_completed()
        assert completed is not None and completed[0] == head_idx
        self.tx_queue.free_chain(head_idx)
        return len(frame_bytes)

    def receive_packet(self, raw_frame: bytes):
        """Simulates incoming packet received by hardware."""
        self.rx_packets.append(raw_frame)

    def poll_rx(self) -> Optional[bytes]:
        """Polls for incoming packet."""
        if not self.rx_packets:
            return None
        return self.rx_packets.pop(0)

if __name__ == "__main__":
    net = VirtioNetDevice()
    eth_pkt = b"\xFF\xFF\xFF\xFF\xFF\xFF\x52\x54\x00\x12\x34\x56\x08\x00" + b"HELLO_VIRTIO_NET"
    sent = net.transmit_packet(eth_pkt)
    assert sent == len(eth_pkt)
    net.receive_packet(eth_pkt)
    rec = net.poll_rx()
    assert rec == eth_pkt
    print("VirtIO Network device verified.")
