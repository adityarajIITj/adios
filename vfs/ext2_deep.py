#!/usr/bin/env python3
"""
AdiOS Filesystem Subsystem: Deep Ext2 Inode & Multi-Indirect Block Addressing Engine (vfs/ext2_deep.py)
Implements Linux Ext2 block mapping, indirect pointers, and hierarchical directory traversal:
- Direct block addressing: i_block[0..11] (up to 12KB with 1KB blocks)
- Single indirect addressing: i_block[12] -> pointers table (up to 256KB)
- Double indirect addressing: i_block[13] -> table of indirect tables (up to 64MB)
- Triple indirect addressing: i_block[14] -> 3-level tree (up to 16GB)
- Logical to physical block mapping function: bmap(inode, logical_block) -> physical_block
- Ext2 Directory Entry walker: parses linked list of variable-length ext2_dir_entry_2 records
- Path resolution: resolves hierarchical paths like '/usr/bin/sh' into target inode

Zero external dependencies. Pure RV32IM storage architecture.
STRICT ZERO EMOJI POLICY.
"""

import struct
from typing import Dict, List, Tuple, Optional, Any
from .ext2 import Ext2Superblock, Ext2Inode, EXT2_MAGIC, EXT2_ROOT_INO

# Ext2 File Types
EXT2_FT_UNKNOWN  = 0
EXT2_FT_REG_FILE = 1
EXT2_FT_DIR      = 2
EXT2_FT_CHRDEV   = 3
EXT2_FT_BLKDEV   = 4
EXT2_FT_FIFO     = 5
EXT2_FT_SOCK     = 6
EXT2_FT_SYMLINK  = 7

class Ext2DirEntry:
    def __init__(self, inode: int, rec_len: int, name_len: int, file_type: int, name: str):
        self.inode = inode
        self.rec_len = rec_len
        self.name_len = name_len
        self.file_type = file_type
        self.name = name

    def __repr__(self):
        return f"<Ext2DirEntry name='{self.name}' ino={self.inode} type={self.file_type}>"

class DeepExt2Driver:
    """
    Ext2 Filesystem Driver with full indirect block addressing and directory traversal.
    """
    def __init__(self, disk: bytearray):
        self.disk = disk
        self.sb = Ext2Superblock(bytes(disk[1024 : 1024 + 84]))
        if self.sb.s_magic != EXT2_MAGIC:
            raise ValueError(f"Invalid Ext2 magic: expected 0x{EXT2_MAGIC:X}, got 0x{self.sb.s_magic:X}")

        self.block_size = self.sb.block_size
        self.ptrs_per_block = self.block_size // 4

        # Read Block Group 0 Descriptor
        bgd_block = 2 if self.block_size == 1024 else 1
        bgd_off = bgd_block * self.block_size
        self.bg_block_bitmap, self.bg_inode_bitmap, self.bg_inode_table = struct.unpack_from("<3I", disk, bgd_off)

    def read_block(self, block_num: int) -> bytes:
        if block_num == 0:
            return b"\x00" * self.block_size # Sparse block
        off = block_num * self.block_size
        if off + self.block_size > len(self.disk):
            raise ValueError(f"Block out of bounds: block={block_num}, disk_size={len(self.disk)}")
        return bytes(self.disk[off : off + self.block_size])

    def write_block(self, block_num: int, data: bytes):
        if block_num == 0:
            return
        off = block_num * self.block_size
        self.disk[off : off + len(data)] = data

    def read_inode(self, inode_num: int) -> Ext2Inode:
        """Reads 128-byte inode structure from disk."""
        if inode_num < 1:
            raise ValueError("Invalid inode number")
        inode_idx = inode_num - 1
        inode_off = self.bg_inode_table * self.block_size + inode_idx * 128
        raw_inode = bytes(self.disk[inode_off : inode_off + 128])
        return Ext2Inode(raw_inode)

    def bmap(self, inode: Ext2Inode, logical_block: int) -> int:
        """
        Maps a logical file block index to physical disk block number
        using direct, single, double, and triple indirect pointers.
        Returns 0 if block is sparse (hole).
        """
        # 1. Direct blocks: 0 to 11
        if logical_block < 12:
            return inode.i_block[logical_block]

        logical_block -= 12

        # 2. Single indirect: block 12
        if logical_block < self.ptrs_per_block:
            indirect_block = inode.i_block[12]
            if indirect_block == 0:
                return 0
            indirect_data = self.read_block(indirect_block)
            return struct.unpack_from("<I", indirect_data, logical_block * 4)[0]

        logical_block -= self.ptrs_per_block

        # 3. Double indirect: block 13
        double_indirect_capacity = self.ptrs_per_block * self.ptrs_per_block
        if logical_block < double_indirect_capacity:
            d_block = inode.i_block[13]
            if d_block == 0:
                return 0
            d_data = self.read_block(d_block)
            first_level_idx = logical_block // self.ptrs_per_block
            second_level_idx = logical_block % self.ptrs_per_block

            indirect_block = struct.unpack_from("<I", d_data, first_level_idx * 4)[0]
            if indirect_block == 0:
                return 0
            indirect_data = self.read_block(indirect_block)
            return struct.unpack_from("<I", indirect_data, second_level_idx * 4)[0]

        logical_block -= double_indirect_capacity

        # 4. Triple indirect: block 14
        t_block = inode.i_block[14]
        if t_block == 0:
            return 0
        t_data = self.read_block(t_block)
        l1_idx = logical_block // double_indirect_capacity
        rem = logical_block % double_indirect_capacity
        l2_idx = rem // self.ptrs_per_block
        l3_idx = rem % self.ptrs_per_block

        l1_block = struct.unpack_from("<I", t_data, l1_idx * 4)[0]
        if l1_block == 0: return 0
        l2_data = self.read_block(l1_block)
        l2_block = struct.unpack_from("<I", l2_data, l2_idx * 4)[0]
        if l2_block == 0: return 0
        l3_data = self.read_block(l2_block)
        return struct.unpack_from("<I", l3_data, l3_idx * 4)[0]

    def read_file_data(self, inode: Ext2Inode) -> bytes:
        """Reads complete file payload up to inode.i_size."""
        num_blocks = (inode.i_size + self.block_size - 1) // self.block_size
        out = bytearray()

        for l_blk in range(num_blocks):
            p_blk = self.bmap(inode, l_blk)
            blk_data = self.read_block(p_blk)
            bytes_left = inode.i_size - len(out)
            chunk = blk_data[:min(bytes_left, self.block_size)]
            out.extend(chunk)

        return bytes(out)

    def read_directory(self, dir_inode: Ext2Inode) -> List[Ext2DirEntry]:
        """Parses directory records from a directory inode."""
        dir_data = self.read_file_data(dir_inode)
        entries = []
        offset = 0

        while offset < len(dir_data):
            if offset + 8 > len(dir_data):
                break
            ino, rec_len, name_len, file_type = struct.unpack_from("<IHBB", dir_data, offset)
            if rec_len == 0:
                break
            name_bytes = dir_data[offset + 8 : offset + 8 + name_len]
            name = name_bytes.decode("utf-8", errors="replace")
            if ino != 0 and name:
                entries.append(Ext2DirEntry(ino, rec_len, name_len, file_type, name))
            offset += rec_len

        return entries

    def resolve_path(self, path: str) -> Optional[Ext2Inode]:
        """Resolves absolute path into its target Ext2Inode."""
        parts = [p for p in path.split("/") if p]
        curr_ino = EXT2_ROOT_INO
        curr_inode = self.read_inode(curr_ino)

        for part in parts:
            entries = self.read_directory(curr_inode)
            found = False
            for e in entries:
                if e.name == part:
                    curr_ino = e.inode
                    curr_inode = self.read_inode(curr_ino)
                    found = True
                    break
            if not found:
                return None

        return curr_inode
