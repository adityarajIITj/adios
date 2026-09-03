#!/usr/bin/env python3
"""
AdiOS Filesystem Subsystem: Linux Ext2 Driver (ext2.py)
Implements Linux Second Extended Filesystem (Ext2) from raw disk blocks:
- Superblock verification (Magic 0xEF53)
- Block Group Descriptors (BGD)
- Inode table traversal (Direct blocks i_block[0..11])
- Directory entries (ext2_dir_entry_2)
Zero external dependencies.
"""

import struct
from typing import List, Dict, Tuple, Optional

EXT2_MAGIC = 0xEF53
EXT2_ROOT_INO = 2

class Ext2Superblock:
    """Ext2 Superblock (located at 1024 bytes offset from disk start)."""
    def __init__(self, raw: bytes):
        (
            self.s_inodes_count,
            self.s_blocks_count,
            self.s_r_blocks_count,
            self.s_free_blocks_count,
            self.s_free_inodes_count,
            self.s_first_data_block,
            self.s_log_block_size,
            self.s_log_frag_size,
            self.s_blocks_per_group,
            self.s_frags_per_group,
            self.s_inodes_per_group,
            self.s_mtime,
            self.s_wtime,
            self.s_mnt_count,
            self.s_max_mnt_count,
            self.s_magic
        ) = struct.unpack_from("<13I3H", raw, 0)
        self.block_size = 1024 << self.s_log_block_size

class Ext2Inode:
    """128-byte Ext2 Inode structure."""
    def __init__(self, raw: bytes):
        self.i_mode, self.i_uid, self.i_size = struct.unpack_from("<HHI", raw, 0)
        self.i_blocks = struct.unpack_from("<I", raw, 28)[0]
        # 12 Direct blocks + 1 Single indirect + 1 Double indirect + 1 Triple indirect
        self.i_block = list(struct.unpack_from("<15I", raw, 40))

class Ext2Driver:
    """
    Ext2 Filesystem Driver.
    """
    def __init__(self, disk_image: bytearray):
        self.disk = disk_image
        self.sb = Ext2Superblock(bytes(disk_image[1024:1024 + 84]))
        if self.sb.s_magic != EXT2_MAGIC:
            raise ValueError(f"Invalid Ext2 magic: expected 0x{EXT2_MAGIC:X}, got 0x{self.sb.s_magic:X}")

        # Block Group Descriptors follow superblock (Block 1 or Block 2 depending on block size)
        bgd_block = 2 if self.sb.block_size == 1024 else 1
        bgd_offset = bgd_block * self.sb.block_size
        self.bg_inode_table = struct.unpack_from("<I", self.disk, bgd_offset + 8)[0]

    def read_block(self, block_num: int) -> bytes:
        offset = block_num * self.sb.block_size
        return bytes(self.disk[offset:offset + self.sb.block_size])

    def read_inode(self, inode_num: int) -> Ext2Inode:
        # 1-indexed inode
        idx = inode_num - 1
        table_offset = self.bg_inode_table * self.sb.block_size
        inode_offset = table_offset + idx * 128
        raw_inode = bytes(self.disk[inode_offset:inode_offset + 128])
        return Ext2Inode(raw_inode)

    def read_file_data(self, inode: Ext2Inode) -> bytes:
        data = bytearray()
        bytes_left = inode.i_size
        for blk in inode.i_block[:12]:
            if blk == 0 or bytes_left <= 0: break
            chunk = self.read_block(blk)
            take = min(bytes_left, len(chunk))
            data.extend(chunk[:take])
            bytes_left -= take
        return bytes(data)

    def list_root(self) -> List[Tuple[int, str]]:
        root_inode = self.read_inode(EXT2_ROOT_INO)
        dir_bytes = self.read_file_data(root_inode)
        entries = []
        pos = 0
        while pos < len(dir_bytes):
            ino, rec_len, name_len, file_type = struct.unpack_from("<IHBB", dir_bytes, pos)
            if rec_len == 0: break
            name = dir_bytes[pos + 8:pos + 8 + name_len].decode("ascii", errors="replace")
            if ino != 0 and name not in (".", ".."):
                entries.append((ino, name))
            pos += rec_len
        return entries

if __name__ == "__main__":
    print("Ext2 driver module loaded.")
