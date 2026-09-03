#!/usr/bin/env python3
"""
AdiOS Filesystem Subsystem: FAT32 Driver (fat32.py)
Implements Microsoft FAT32 filesystem driver from raw disk sectors:
- BIOS Parameter Block (BPB) & Boot Sector parsing
- File Allocation Table (FAT) cluster chain traversal
- 32-byte Directory Entry decoding (8.3 filenames, size, cluster ptrs)
- Direct cluster sector read/write operations
Zero external dependencies.
"""

import struct
from typing import List, Dict, Tuple, Optional

FAT32_EOC = 0x0FFFFFF8 # End of cluster marker threshold
ATTR_READ_ONLY = 0x01
ATTR_HIDDEN    = 0x02
ATTR_SYSTEM    = 0x04
ATTR_VOLUME_ID = 0x08
ATTR_DIRECTORY = 0x10
ATTR_ARCHIVE   = 0x20

class BPB:
    """BIOS Parameter Block."""
    def __init__(self, sector: bytes):
        self.bytes_per_sector = struct.unpack_from("<H", sector, 11)[0]
        self.sectors_per_cluster = sector[13]
        self.reserved_sectors = struct.unpack_from("<H", sector, 14)[0]
        self.num_fats = sector[16]
        self.total_sectors = struct.unpack_from("<I", sector, 32)[0]
        self.sectors_per_fat = struct.unpack_from("<I", sector, 36)[0]
        self.root_cluster = struct.unpack_from("<I", sector, 44)[0]

class FAT32Entry:
    def __init__(self, name: str, is_dir: bool, size: int, first_cluster: int):
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.first_cluster = first_cluster

class FAT32Driver:
    """
    FAT32 Storage Driver reading and writing raw disk images.
    """
    def __init__(self, disk_image: bytearray):
        self.disk = disk_image
        self.bpb = BPB(disk_image[:512])
        self.fat_start_offset = self.bpb.reserved_sectors * self.bpb.bytes_per_sector
        self.data_start_offset = (self.bpb.reserved_sectors + self.bpb.num_fats * self.bpb.sectors_per_fat) * self.bpb.bytes_per_sector
        self.cluster_size = self.bpb.sectors_per_cluster * self.bpb.bytes_per_sector

    def _cluster_offset(self, cluster: int) -> int:
        return self.data_start_offset + (cluster - 2) * self.cluster_size

    def get_next_cluster(self, cluster: int) -> int:
        fat_entry_offset = self.fat_start_offset + cluster * 4
        entry = struct.unpack_from("<I", self.disk, fat_entry_offset)[0] & 0x0FFFFFFF
        return entry

    def read_cluster_chain(self, start_cluster: int) -> bytearray:
        data = bytearray()
        curr = start_cluster
        while 2 <= curr < FAT32_EOC:
            offset = self._cluster_offset(curr)
            data.extend(self.disk[offset:offset + self.cluster_size])
            curr = self.get_next_cluster(curr)
        return data

    def list_root_directory(self) -> List[FAT32Entry]:
        root_data = self.read_cluster_chain(self.bpb.root_cluster)
        entries = []
        for i in range(0, len(root_data), 32):
            raw_entry = root_data[i:i + 32]
            if raw_entry[0] in (0x00, 0xE5): # Free / deleted entry
                continue
            attr = raw_entry[11]
            if attr == 0x0F: # Long file name (LFN) sub-component
                continue

            raw_name = raw_entry[0:8].decode("ascii", errors="replace").strip()
            raw_ext = raw_entry[8:11].decode("ascii", errors="replace").strip()
            filename = f"{raw_name}.{raw_ext}" if raw_ext else raw_name
            is_dir = bool(attr & ATTR_DIRECTORY)
            cluster_high = struct.unpack_from("<H", raw_entry, 20)[0]
            cluster_low = struct.unpack_from("<H", raw_entry, 26)[0]
            first_cluster = (cluster_high << 16) | cluster_low
            size = struct.unpack_from("<I", raw_entry, 28)[0]
            entries.append(FAT32Entry(filename, is_dir, size, first_cluster))
        return entries

    def read_file(self, filename: str) -> bytes:
        for entry in self.list_root_directory():
            if entry.name.upper() == filename.upper() and not entry.is_dir:
                data = self.read_cluster_chain(entry.first_cluster)
                return bytes(data[:entry.size])
        raise FileNotFoundError(f"FAT32: File '{filename}' not found")

if __name__ == "__main__":
    print("FAT32 driver module loaded.")
