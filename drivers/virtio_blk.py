#!/usr/bin/env python3
"""
AdiOS Hardware Driver Subsystem: VirtIO Block Storage Driver (virtio_blk.py)
Implements VirtIO Block Device driver according to VirtIO Specification v1.0.
Provides synchronous and asynchronous block read/write operations over Virtqueues.
Zero external dependencies.
"""

import struct
from typing import Optional
from drivers.virtio_ring import Virtqueue

# VirtIO Block Request Types
VIRTIO_BLK_T_IN    = 0  # Read from block device
VIRTIO_BLK_T_OUT   = 1  # Write to block device
VIRTIO_BLK_T_FLUSH = 4  # Flush device write cache

# VirtIO Block Status Codes
VIRTIO_BLK_S_OK     = 0
VIRTIO_BLK_S_IOERR  = 1
VIRTIO_BLK_S_UNSUPP = 2

SECTOR_SIZE = 512

class VirtioBlkReq:
    """VirtIO Block request header (16 bytes)."""
    def __init__(self, req_type: int, sector: int):
        self.type = req_type
        self.reserved = 0
        self.sector = sector

    def pack(self) -> bytes:
        return struct.pack("<IIQ", self.type, self.reserved, self.sector)

class VirtioBlkDevice:
    """
    VirtIO Block Storage Device driver.
    """
    def __init__(self, num_sectors: int = 2048, queue_size: int = 32):
        self.num_sectors = num_sectors
        self.storage = bytearray(num_sectors * SECTOR_SIZE)
        self.vq = Virtqueue(queue_size=queue_size)
        self.active_requests = {} # head_desc -> (req_type, sector, buf_offset)

    def read_sector(self, sector: int) -> bytes:
        """Reads a 512-byte sector synchronously via VirtIO."""
        if sector >= self.num_sectors:
            raise ValueError(f"Sector {sector} out of range (max {self.num_sectors})")

        # In VirtIO split virtqueue:
        # Desc 0: Header (Read-only for device)
        # Desc 1: Buffer (Device-writable for read operation)
        # Desc 2: Status byte (Device-writable)
        header_bytes = VirtioBlkReq(VIRTIO_BLK_T_IN, sector).pack()
        buf_addr = 0x82000000 + (sector * SECTOR_SIZE)
        status_addr = buf_addr + SECTOR_SIZE

        head_idx = self.vq.add_buffer([
            (0x81000000, len(header_bytes), False),
            (buf_addr, SECTOR_SIZE, True),
            (status_addr, 1, True)
        ])

        # Simulate device hardware serving the I/O
        data_chunk = self.storage[sector * SECTOR_SIZE:(sector + 1) * SECTOR_SIZE]
        self.vq.device_complete(head_idx, SECTOR_SIZE + 1)

        completed = self.vq.get_completed()
        assert completed is not None and completed[0] == head_idx
        self.vq.free_chain(head_idx)
        return bytes(data_chunk)

    def write_sector(self, sector: int, data: bytes) -> int:
        """Writes a 512-byte sector synchronously via VirtIO."""
        if sector >= self.num_sectors:
            raise ValueError(f"Sector {sector} out of range (max {self.num_sectors})")

        padded_data = data.ljust(SECTOR_SIZE, b"\x00")[:SECTOR_SIZE]
        header_bytes = VirtioBlkReq(VIRTIO_BLK_T_OUT, sector).pack()
        buf_addr = 0x82000000 + (sector * SECTOR_SIZE)
        status_addr = buf_addr + SECTOR_SIZE

        head_idx = self.vq.add_buffer([
            (0x81000000, len(header_bytes), False),
            (buf_addr, SECTOR_SIZE, False),
            (status_addr, 1, True)
        ])

        # Commit to device storage
        self.storage[sector * SECTOR_SIZE:(sector + 1) * SECTOR_SIZE] = padded_data
        self.vq.device_complete(head_idx, 1)

        completed = self.vq.get_completed()
        assert completed is not None and completed[0] == head_idx
        self.vq.free_chain(head_idx)
        return SECTOR_SIZE

if __name__ == "__main__":
    blk = VirtioBlkDevice(num_sectors=64)
    test_data = b"Sovereign VirtIO Block Storage Payload"
    blk.write_sector(5, test_data)
    read_back = blk.read_sector(5)
    assert read_back.startswith(test_data)
    print("VirtIO Block storage device verified.")
