#!/usr/bin/env python3
"""
AdiOS Hardware Driver Subsystem: VirtIO Standard Split Virtqueue (virtio_ring.py)
Implements OASIS VirtIO v1.0 standard Split Virtqueue data structures:
- VRingDesc: 16-byte buffer descriptors (address, length, flags, next)
- VRingAvail: Driver-to-Device available ring buffer
- VRingUsed: Device-to-Driver completed work ring buffer
Zero external dependencies.
"""

import struct
from typing import List, Optional, Tuple

# VirtIO Ring Flags
VRING_DESC_F_NEXT     = 1  # Buffer continues via the next field
VRING_DESC_F_WRITE    = 2  # Buffer is write-only for the device (read for driver)
VRING_DESC_F_INDIRECT = 4  # Buffer contains a list of buffer descriptors

class VRingDesc:
    """16-byte VirtIO Descriptor."""
    def __init__(self, addr: int = 0, length: int = 0, flags: int = 0, next_desc: int = 0):
        self.addr = addr
        self.length = length
        self.flags = flags
        self.next_desc = next_desc

    def pack(self) -> bytes:
        return struct.pack("<QIIH", self.addr, self.length, self.flags, self.next_desc)

    @classmethod
    def unpack(cls, data: bytes) -> 'VRingDesc':
        addr, length, flags, next_desc = struct.unpack("<QIIH", data[:16])
        return cls(addr, length, flags, next_desc)

class VRingAvail:
    """Available Ring: Driver passes buffers to device."""
    def __init__(self, size: int):
        self.size = size
        self.flags = 0
        self.idx = 0
        self.ring = [0] * size
        self.used_event = 0

class VRingUsedElem:
    """Completed descriptor in Used Ring."""
    def __init__(self, id_val: int = 0, length: int = 0):
        self.id = id_val
        self.len = length

    def pack(self) -> bytes:
        return struct.pack("<II", self.id, self.len)

class VRingUsed:
    """Used Ring: Device returns completed buffers to driver."""
    def __init__(self, size: int):
        self.size = size
        self.flags = 0
        self.idx = 0
        self.ring = [VRingUsedElem() for _ in range(size)]
        self.avail_event = 0

class Virtqueue:
    """
    Complete VirtIO Split Virtqueue controller managing descriptor table,
    available ring, and used ring.
    """
    def __init__(self, queue_size: int = 64, base_addr: int = 0x82000000):
        self.queue_size = queue_size
        self.base_addr = base_addr
        self.descriptors: List[VRingDesc] = [VRingDesc() for _ in range(queue_size)]
        self.avail = VRingAvail(queue_size)
        self.used = VRingUsed(queue_size)
        
        # Free list of descriptors
        self.free_head = 0
        for i in range(queue_size - 1):
            self.descriptors[i].next_desc = i + 1
        self.descriptors[queue_size - 1].next_desc = 0xFFFF # End of list
        self.num_free = queue_size
        self.last_used_idx = 0

    def alloc_desc(self) -> int:
        """Allocates a free descriptor index."""
        if self.num_free == 0 or self.free_head == 0xFFFF:
            raise IndexError("Virtqueue descriptor table full")
        idx = self.free_head
        self.free_head = self.descriptors[idx].next_desc
        self.num_free -= 1
        return idx

    def free_chain(self, head_idx: int):
        """Returns a descriptor chain back to the free list."""
        curr = head_idx
        while True:
            nxt = self.descriptors[curr].next_desc
            has_next = bool(self.descriptors[curr].flags & VRING_DESC_F_NEXT)
            self.descriptors[curr].next_desc = self.free_head
            self.free_head = curr
            self.num_free += 1
            if not has_next or nxt == 0xFFFF:
                break
            curr = nxt

    def add_buffer(self, buffers: List[Tuple[int, int, bool]]) -> int:
        """
        Adds a buffer chain to the virtqueue.
        buffers is a list of (addr, length, is_device_writable).
        Returns the head descriptor index.
        """
        if len(buffers) > self.num_free:
            raise IndexError("Not enough free descriptors for buffer chain")

        head_idx = self.alloc_desc()
        curr_idx = head_idx

        for i, (addr, length, is_write) in enumerate(buffers):
            desc = self.descriptors[curr_idx]
            desc.addr = addr
            desc.length = length
            desc.flags = VRING_DESC_F_WRITE if is_write else 0

            if i < len(buffers) - 1:
                next_idx = self.alloc_desc()
                desc.flags |= VRING_DESC_F_NEXT
                desc.next_desc = next_idx
                curr_idx = next_idx
            else:
                desc.next_desc = 0

        # Place head index into available ring
        ring_pos = self.avail.idx % self.queue_size
        self.avail.ring[ring_pos] = head_idx
        self.avail.idx = (self.avail.idx + 1) & 0xFFFF
        return head_idx

    def get_completed(self) -> Optional[Tuple[int, int]]:
        """
        Polls the used ring for completed buffers.
        Returns (head_desc_id, bytes_transferred) or None.
        """
        if self.last_used_idx == self.used.idx:
            return None

        ring_pos = self.last_used_idx % self.queue_size
        elem = self.used.ring[ring_pos]
        self.last_used_idx = (self.last_used_idx + 1) & 0xFFFF
        return (elem.id, elem.len)

    def device_complete(self, desc_id: int, written_len: int):
        """Simulates device hardware writing back completion to used ring."""
        ring_pos = self.used.idx % self.queue_size
        self.used.ring[ring_pos].id = desc_id
        self.used.ring[ring_pos].len = written_len
        self.used.idx = (self.used.idx + 1) & 0xFFFF

if __name__ == "__main__":
    vq = Virtqueue(queue_size=16)
    head = vq.add_buffer([(0x80001000, 512, False), (0x80002000, 1, True)])
    assert vq.avail.idx == 1
    assert vq.avail.ring[0] == head
    
    # Simulate device processing
    vq.device_complete(head, 513)
    completed = vq.get_completed()
    assert completed == (head, 513)
    vq.free_chain(head)
    assert vq.num_free == 16
    print("VirtIO Virtqueue split ring verified.")
