#!/usr/bin/env python3
"""
AdiFS: The Contiguous Block Filesystem of AdiOS
Inspired by Terry A. Davis's RedSea filesystem in TempleOS.
Features:
- Pure 512-byte sector architecture with zero cluster fragmentation
- 100% Contiguous file allocation (files occupy contiguous sector ranges)
- Single-transfer DMA reads directly into RAM
- Superblock + Contiguous Directory Entry table
- Full read/write/list/format API compatible with AdiOS Virtual Disk MMIO
"""

import struct
import time
import os

SECTOR_SIZE       = 512
ADIFS_MAGIC       = b"ADIFS01\0"
ROOT_DIR_SECTOR   = 1
ROOT_DIR_SECTORS  = 32     # 32 sectors * 512 = 16 KB (256 directory entries)
DATA_START_SECTOR = 33
ENTRY_SIZE        = 64     # 64 bytes per directory entry (8 entries per sector)
MAX_ENTRIES       = (ROOT_DIR_SECTORS * SECTOR_SIZE) // ENTRY_SIZE # 256 entries

# File Attributes
ATTR_FREE       = 0x00
ATTR_FILE       = 0x01
ATTR_DIR        = 0x02
ATTR_EXECUTABLE = 0x04

class Superblock:
    def __init__(self, total_sectors=16384):
        self.magic = ADIFS_MAGIC
        self.sector_size = SECTOR_SIZE
        self.total_sectors = total_sectors
        self.root_dir_sector = ROOT_DIR_SECTOR
        self.root_dir_sectors = ROOT_DIR_SECTORS
        self.data_start_sector = DATA_START_SECTOR
        self.free_sector_ptr = DATA_START_SECTOR

    def pack(self):
        # Format: 8s (magic) + 6 * uint32 + padding to 512 bytes
        buf = struct.pack(
            "<8sIIIIII",
            self.magic,
            self.sector_size,
            self.total_sectors,
            self.root_dir_sector,
            self.root_dir_sectors,
            self.data_start_sector,
            self.free_sector_ptr
        )
        return buf.ljust(SECTOR_SIZE, b"\0")

    @classmethod
    def unpack(cls, buf):
        magic, s_size, t_sec, rd_sec, rd_secs, d_sec, f_ptr = struct.unpack_from("<8sIIIIII", buf, 0)
        if magic != ADIFS_MAGIC:
            raise ValueError(f"Invalid AdiFS magic: {magic}")
        sb = cls(t_sec)
        sb.sector_size = s_size
        sb.root_dir_sector = rd_sec
        sb.root_dir_sectors = rd_secs
        sb.data_start_sector = d_sec
        sb.free_sector_ptr = f_ptr
        return sb

class DirEntry:
    def __init__(self, name="", start_sector=0, size_bytes=0, attr=ATTR_FILE, timestamp=None):
        self.name = name[:31]
        self.start_sector = start_sector
        self.size_bytes = size_bytes
        self.attr = attr
        self.timestamp = int(timestamp or time.time())

    def pack(self):
        name_bytes = self.name.encode("utf-8")[:31].ljust(32, b"\0")
        buf = struct.pack(
            "<32sIIII12s",
            name_bytes,
            self.start_sector,
            self.size_bytes,
            self.attr,
            self.timestamp,
            b"\0" * 12
        )
        return buf

    @classmethod
    def unpack(cls, buf):
        name_raw, start, size, attr, ts, _ = struct.unpack_from("<32sIIII12s", buf, 0)
        name = name_raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
        return cls(name, start, size, attr, ts)

class AdiFS:
    def __init__(self, disk_path="disk.img"):
        self.disk_path = disk_path

    def format_disk(self, total_sectors=16384):
        """Formats the virtual disk with fresh AdiFS superblock and empty root directory."""
        sb = Superblock(total_sectors)
        with open(self.disk_path, "wb") as f:
            # Write Superblock (Sector 0)
            f.write(sb.pack())
            # Write Empty Root Directory (Sectors 1..32)
            empty_dir = b"\0" * (ROOT_DIR_SECTORS * SECTOR_SIZE)
            f.write(empty_dir)
            # Pad disk to full size
            f.seek(total_sectors * SECTOR_SIZE - 1)
            f.write(b"\0")
        return sb

    def get_superblock(self):
        with open(self.disk_path, "rb") as f:
            f.seek(0)
            buf = f.read(SECTOR_SIZE)
        return Superblock.unpack(buf)

    def write_superblock(self, sb):
        with open(self.disk_path, "r+b") as f:
            f.seek(0)
            f.write(sb.pack())

    def list_files(self):
        """Returns a list of active DirEntry objects in the root directory."""
        sb = self.get_superblock()
        entries = []
        with open(self.disk_path, "rb") as f:
            f.seek(sb.root_dir_sector * SECTOR_SIZE)
            raw_dir = f.read(sb.root_dir_sectors * SECTOR_SIZE)

        for i in range(MAX_ENTRIES):
            off = i * ENTRY_SIZE
            entry_buf = raw_dir[off : off + ENTRY_SIZE]
            if entry_buf[32] != 0: # Check if attr != ATTR_FREE
                entry = DirEntry.unpack(entry_buf)
                if entry.name:
                    entries.append(entry)
        return entries

    def create_file(self, name, data, attr=ATTR_FILE):
        """Writes a file contiguously to the virtual disk."""
        if isinstance(data, str):
            data = data.encode("utf-8")

        sb = self.get_superblock()
        size_bytes = len(data)
        sectors_needed = (size_bytes + SECTOR_SIZE - 1) // SECTOR_SIZE
        if sectors_needed == 0:
            sectors_needed = 1

        start_sector = sb.free_sector_ptr
        if start_sector + sectors_needed > sb.total_sectors:
            raise IOError("AdiFS: Out of disk space")

        # 1. Write Contiguous File Data
        with open(self.disk_path, "r+b") as f:
            f.seek(start_sector * SECTOR_SIZE)
            # Pad file data to full sector boundary
            padded_data = data.ljust(sectors_needed * SECTOR_SIZE, b"\0")
            f.write(padded_data)

            # 2. Add Directory Entry
            f.seek(sb.root_dir_sector * SECTOR_SIZE)
            raw_dir = bytearray(f.read(sb.root_dir_sectors * SECTOR_SIZE))

            slot_found = False
            for i in range(MAX_ENTRIES):
                off = i * ENTRY_SIZE
                if raw_dir[off + 32] == 0 or raw_dir[off : off + 32].split(b"\0", 1)[0].decode("utf-8", errors="ignore") == name:
                    entry = DirEntry(name, start_sector, size_bytes, attr)
                    raw_dir[off : off + ENTRY_SIZE] = entry.pack()
                    slot_found = True
                    break

            if not slot_found:
                raise IOError("AdiFS: Root directory table full")

            f.seek(sb.root_dir_sector * SECTOR_SIZE)
            f.write(raw_dir)

        # 3. Update Superblock
        sb.free_sector_ptr += sectors_needed
        self.write_superblock(sb)
        return entry

    def read_file(self, name):
        """Reads a file contiguously from the virtual disk into bytes."""
        files = self.list_files()
        target = None
        for f in files:
            if f.name == name:
                target = f
                break
        if not target:
            raise FileNotFoundError(f"AdiFS: File '{name}' not found on disk")

        with open(self.disk_path, "rb") as f:
            f.seek(target.start_sector * SECTOR_SIZE)
            raw = f.read(target.size_bytes)
        return raw

    def exists(self, name):
        for f in self.list_files():
            if f.name == name:
                return True
        return False
