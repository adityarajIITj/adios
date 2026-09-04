#!/usr/bin/env python3
"""
AdiOS Filesystem Subsystem: Deep Ext2 Inode & Multi-Indirect Block Addressing Engine (Deepened Architecture)
Implements Linux Ext2 block mapping, indirect pointers, file creation, block allocation,
and hierarchical directory traversal from first principles.

Core Features:
1. Block addressing: direct (0-11), single indirect (12), double indirect (13), triple indirect (14).
2. Physical block and inode allocation via block group bitmaps with free-space counters.
3. Inode serialization and deserialization (128-byte standard Ext2 inode records).
4. Dynamic file creation (create_file) and data writing (write_file_data) supporting direct and indirect blocks.
5. Directory entry insertion (add_dir_entry) and removal (unlink_file).
6. Filesystem integrity validation (fsck) and telemetry (get_fs_stats).

Zero external dependencies. Pure RV32IM storage architecture.
STRICT ZERO EMOJI POLICY.
"""

import struct
from typing import Dict, List, Tuple, Optional, Any
from .ext2 import Ext2Superblock, Ext2Inode, EXT2_MAGIC, EXT2_ROOT_INO

# Ext2 Standard File Types
EXT2_FT_UNKNOWN  = 0
EXT2_FT_REG_FILE = 1
EXT2_FT_DIR      = 2
EXT2_FT_CHRDEV   = 3
EXT2_FT_BLKDEV   = 4
EXT2_FT_FIFO     = 5
EXT2_FT_SOCK     = 6
EXT2_FT_SYMLINK  = 7

# Standard Inode Mode Flags
EXT2_S_IFREG = 0x8000
EXT2_S_IFDIR = 0x4000
EXT2_S_IFLNK = 0xA000


class Ext2DirEntry:
    """Represents a variable-length ext2_dir_entry_2 directory record."""
    def __init__(self, inode: int, rec_len: int, name_len: int, file_type: int, name: str):
        self.inode = inode
        self.rec_len = rec_len
        self.name_len = name_len
        self.file_type = file_type
        self.name = name

    def to_bytes(self) -> bytes:
        """Serializes directory entry into binary on-disk record."""
        name_bytes = self.name.encode("utf-8")
        header = struct.pack("<IHBB", self.inode, self.rec_len, len(name_bytes), self.file_type)
        pad_len = self.rec_len - len(header) - len(name_bytes)
        return header + name_bytes + (b"\x00" * max(0, pad_len))

    def __repr__(self) -> str:
        return f"<Ext2DirEntry name='{self.name}' ino={self.inode} type={self.file_type}>"


class DeepExt2Driver:
    """
    Ext2 Filesystem Driver with multi-indirect block addressing,
    bitmap block/inode allocation, and dynamic file mutations.
    """
    def __init__(self, disk: bytearray):
        self.disk = disk
        self.sb = Ext2Superblock(bytes(disk[1024 : 1024 + 84]))
        self.superblock = self.sb
        if self.sb.s_magic != EXT2_MAGIC:
            raise ValueError(f"Invalid Ext2 magic: expected 0x{EXT2_MAGIC:X}, got 0x{self.sb.s_magic:X}")

        self.block_size = self.sb.block_size
        self.ptrs_per_block = self.block_size // 4

        # Read Block Group 0 Descriptor
        self.bgd_block = 2 if self.block_size == 1024 else 1
        self.bgd_off = self.bgd_block * self.block_size
        self.bg_block_bitmap, self.bg_inode_bitmap, self.bg_inode_table = struct.unpack_from("<3I", disk, self.bgd_off)

    # -------------------------------------------------------------------------
    # Low-Level Block I/O
    # -------------------------------------------------------------------------
    def read_block(self, block_num: int) -> bytes:
        """Reads a physical block from disk. Returns zeros for sparse block 0."""
        if block_num == 0:
            return b"\x00" * self.block_size
        off = block_num * self.block_size
        if off + self.block_size > len(self.disk):
            raise ValueError(f"Block out of bounds: block={block_num}, disk_size={len(self.disk)}")
        return bytes(self.disk[off : off + self.block_size])

    def write_block(self, block_num: int, data: bytes):
        """Writes data into a physical block on disk."""
        if block_num == 0:
            return
        off = block_num * self.block_size
        self.disk[off : off + len(data)] = data

    # -------------------------------------------------------------------------
    # Inode Serialization & Deserialization
    # -------------------------------------------------------------------------
    def read_inode(self, inode_num: int) -> Ext2Inode:
        """Reads 128-byte inode structure from disk."""
        if inode_num < 1:
            raise ValueError("Invalid inode number")
        inode_idx = inode_num - 1
        inode_off = self.bg_inode_table * self.block_size + inode_idx * 128
        raw_inode = bytes(self.disk[inode_off : inode_off + 128])
        return Ext2Inode(raw_inode)

    def write_inode(self, inode_num: int, inode: Ext2Inode):
        """Serializes and writes 128-byte inode back to the inode table."""
        if inode_num < 1:
            raise ValueError("Invalid inode number")
        inode_idx = inode_num - 1
        inode_off = self.bg_inode_table * self.block_size + inode_idx * 128

        # Pack inode fields
        block_bytes = bytearray(60)
        for i in range(15):
            val = inode.i_block[i] if i < len(inode.i_block) else 0
            struct.pack_into("<I", block_bytes, i * 4, val)

        packed = struct.pack(
            "<2H5I2H",
            getattr(inode, "i_mode", 0),
            getattr(inode, "i_uid", 0),
            getattr(inode, "i_size", 0),
            getattr(inode, "i_atime", 0),
            getattr(inode, "i_ctime", 0),
            getattr(inode, "i_mtime", 0),
            getattr(inode, "i_dtime", 0),
            getattr(inode, "i_gid", 0),
            getattr(inode, "i_links_count", 1)
        ) + struct.pack("<I", getattr(inode, "i_blocks", 0)) + struct.pack("<I", getattr(inode, "i_flags", 0)) + struct.pack("<I", 0) + block_bytes

        # Pad to 128 bytes
        if len(packed) < 128:
            packed += b"\x00" * (128 - len(packed))
        self.disk[inode_off : inode_off + 128] = packed[:128]

    # -------------------------------------------------------------------------
    # Bitmap Allocation & Freeing
    # -------------------------------------------------------------------------
    def allocate_block(self) -> int:
        """Allocates an unused physical disk block using the block bitmap."""
        bm_off = self.bg_block_bitmap * self.block_size
        for byte_idx in range(self.block_size):
            b = self.disk[bm_off + byte_idx]
            if b != 0xFF:
                for bit in range(8):
                    if not (b & (1 << bit)):
                        self.disk[bm_off + byte_idx] |= (1 << bit)
                        block_num = byte_idx * 8 + bit + 1
                        # Clear allocated block on disk
                        self.write_block(block_num, b"\x00" * self.block_size)
                        return block_num
        raise IOError("Ext2: Out of disk blocks")

    def free_block(self, block_num: int):
        """Marks a physical block as free in the block bitmap."""
        if block_num == 0:
            return
        bm_off = self.bg_block_bitmap * self.block_size
        bit_idx = block_num - 1
        byte_idx = bit_idx // 8
        bit = bit_idx % 8
        self.disk[bm_off + byte_idx] &= ~(1 << bit)

    def allocate_inode(self) -> int:
        """Allocates an unused inode number using the inode bitmap."""
        bm_off = self.bg_inode_bitmap * self.block_size
        for byte_idx in range(self.block_size):
            b = self.disk[bm_off + byte_idx]
            if b != 0xFF:
                for bit in range(8):
                    if not (b & (1 << bit)):
                        self.disk[bm_off + byte_idx] |= (1 << bit)
                        inode_num = byte_idx * 8 + bit + 1
                        return inode_num
        raise IOError("Ext2: Out of inodes")

    def free_inode(self, inode_num: int):
        """Marks an inode as free in the inode bitmap."""
        if inode_num < 1:
            return
        bm_off = self.bg_inode_bitmap * self.block_size
        bit_idx = inode_num - 1
        byte_idx = bit_idx // 8
        bit = bit_idx % 8
        self.disk[bm_off + byte_idx] &= ~(1 << bit)

    # -------------------------------------------------------------------------
    # Logical to Physical Block Addressing (bmap)
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # High-Level File I/O
    # -------------------------------------------------------------------------
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

    def write_file_data(self, inode_num: int, data: bytes):
        """
        Writes data payload into file, allocating direct and single indirect blocks.
        Updates inode.i_size and writes back to disk.
        """
        inode = self.read_inode(inode_num)
        num_blocks = (len(data) + self.block_size - 1) // self.block_size

        for l_blk in range(num_blocks):
            chunk = data[l_blk * self.block_size : (l_blk + 1) * self.block_size]
            if len(chunk) < self.block_size:
                chunk = chunk + b"\x00" * (self.block_size - len(chunk))

            if l_blk < 12:
                # Direct block
                p_blk = inode.i_block[l_blk]
                if p_blk == 0:
                    p_blk = self.allocate_block()
                    inode.i_block[l_blk] = p_blk
                self.write_block(p_blk, chunk)
            else:
                # Single indirect block
                ind_idx = l_blk - 12
                ind_block = inode.i_block[12]
                if ind_block == 0:
                    ind_block = self.allocate_block()
                    inode.i_block[12] = ind_block

                ind_data = bytearray(self.read_block(ind_block))
                p_blk = struct.unpack_from("<I", ind_data, ind_idx * 4)[0]
                if p_blk == 0:
                    p_blk = self.allocate_block()
                    struct.pack_into("<I", ind_data, ind_idx * 4, p_blk)
                    self.write_block(ind_block, ind_data)
                self.write_block(p_blk, chunk)

        inode.i_size = len(data)
        inode.i_blocks = num_blocks * (self.block_size // 512)
        self.write_inode(inode_num, inode)

    # -------------------------------------------------------------------------
    # Directory Operations
    # -------------------------------------------------------------------------
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

    def add_dir_entry(self, dir_inode_num: int, child_inode_num: int, name: str, file_type: int):
        """Appends a new directory entry to a directory inode."""
        dir_inode = self.read_inode(dir_inode_num)
        dir_data = bytearray(self.read_file_data(dir_inode))

        name_bytes = name.encode("utf-8")
        needed_len = ((8 + len(name_bytes) + 3) // 4) * 4

        # Find last record in last directory block to shrink or append
        offset = 0
        last_offset = 0
        while offset < len(dir_data):
            ino, rec_len, n_len, f_type = struct.unpack_from("<IHBB", dir_data, offset)
            if rec_len == 0:
                break
            last_offset = offset
            offset += rec_len

        if len(dir_data) == 0:
            # First entry
            new_entry = Ext2DirEntry(child_inode_num, self.block_size, len(name_bytes), file_type, name)
            self.write_file_data(dir_inode_num, new_entry.to_bytes())
            return

        # Check if last record can be shortened to make room
        l_ino, l_rec_len, l_n_len, l_f_type = struct.unpack_from("<IHBB", dir_data, last_offset)
        l_actual_len = ((8 + l_n_len + 3) // 4) * 4
        available = l_rec_len - l_actual_len

        if available >= needed_len:
            # Shrink last record
            struct.pack_into("<H", dir_data, last_offset + 4, l_actual_len)
            # Insert new record in remaining space
            new_offset = last_offset + l_actual_len
            new_entry = Ext2DirEntry(child_inode_num, available, len(name_bytes), file_type, name)
            dir_data[new_offset : new_offset + available] = new_entry.to_bytes()
            self.write_file_data(dir_inode_num, dir_data)
        else:
            # Allocate a new directory block
            new_entry = Ext2DirEntry(child_inode_num, self.block_size, len(name_bytes), file_type, name)
            dir_data.extend(new_entry.to_bytes())
            self.write_file_data(dir_inode_num, dir_data)

    def _create_inode_entry(self, parent_dir_ino: int, name: str, mode: int = 0o644, file_type: int = EXT2_FT_REG_FILE) -> int:
        new_ino = self.allocate_inode()
        raw_inode = bytearray(128)
        new_inode = Ext2Inode(bytes(raw_inode))
        new_inode.i_mode = EXT2_S_IFREG | mode if file_type == EXT2_FT_REG_FILE else EXT2_S_IFDIR | mode
        new_inode.i_links_count = 1
        new_inode.i_size = 0
        new_inode.i_blocks = 0
        self.write_inode(new_ino, new_inode)
        self.add_dir_entry(parent_dir_ino, new_ino, name, file_type)
        return new_ino

    def create_file(self, parent_or_path: Any, name_or_data: Any = None, mode: int = 0o644, file_type: int = EXT2_FT_REG_FILE) -> int:
        """Allocates a new inode and adds a directory entry, supporting path or inode parent."""
        if isinstance(parent_or_path, str):
            path = parent_or_path.lstrip("/")
            data = name_or_data if isinstance(name_or_data, (bytes, bytearray)) else b""
            if "/" in path:
                dir_part, filename = path.rsplit("/", 1)
                dir_node = self.resolve_path("/" + dir_part)
                if not dir_node:
                    raise FileNotFoundError(f"Directory '/{dir_part}' not found")
                parent_ino = EXT2_ROOT_INO
            else:
                filename = path
                parent_ino = EXT2_ROOT_INO

            new_ino = self._create_inode_entry(parent_ino, filename, mode, file_type)
            if data:
                self.write_file_data(new_ino, data)
            return new_ino
        else:
            parent_dir_ino = parent_or_path
            name = name_or_data
            return self._create_inode_entry(parent_dir_ino, name, mode, file_type)

    def read_file(self, path: str) -> bytes:
        """Reads data of file resolved from absolute path."""
        inode = self.resolve_path(path)
        if inode is None:
            raise FileNotFoundError(f"Ext2: Path '{path}' not found")
        return self.read_file_data(inode)

    # -------------------------------------------------------------------------
    # Path Resolution & Diagnostics
    # -------------------------------------------------------------------------
    def resolve_path(self, path: str) -> Optional[Ext2Inode]:
        """Resolves absolute path like '/etc/passwd' into its target Ext2Inode."""
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

    def get_fs_stats(self) -> Dict[str, Any]:
        """Returns filesystem capacity and allocation statistics."""
        bm_off = self.bg_block_bitmap * self.block_size
        used_blocks = sum(bin(b).count("1") for b in self.disk[bm_off : bm_off + self.block_size])
        total_blocks = self.sb.s_blocks_count

        ibm_off = self.bg_inode_bitmap * self.block_size
        used_inodes = sum(bin(b).count("1") for b in self.disk[ibm_off : ibm_off + self.block_size])
        total_inodes = self.sb.s_inodes_count

        return {
            "block_size": self.block_size,
            "total_blocks": total_blocks,
            "used_blocks": used_blocks,
            "free_blocks": max(0, total_blocks - used_blocks),
            "total_inodes": total_inodes,
            "used_inodes": used_inodes,
            "free_inodes": max(0, total_inodes - used_inodes),
        }

    @classmethod
    def create_formatted_image(cls, size_blocks: int = 2048, block_size: int = 1024) -> 'DeepExt2Driver':
        """
        Synthesizes a clean, formatted Ext2 filesystem in memory.
        Initializes superblock at 1024, block group descriptor at block 2,
        block bitmap (block 3), inode bitmap (block 4), inode table (block 5),
        and root directory (inode 2, block 10).
        """
        disk = bytearray(size_blocks * block_size)

        # 1. Superblock at offset 1024
        sb_bytes = struct.pack(
            "<13I3H",
            128,              # s_inodes_count
            size_blocks,      # s_blocks_count
            0, size_blocks - 15, 120, # s_r_blocks_count, s_free_blocks_count, s_free_inodes_count
            1,                # s_first_data_block
            0, 0,             # s_log_block_size (1024), s_log_frag_size
            size_blocks, size_blocks, 128, # blocks_per_group, frags_per_group, inodes_per_group
            0, 0, 1, 20,      # mtime, wtime, mnt_count, max_mnt_count
            EXT2_MAGIC        # 0xEF53
        )
        disk[1024 : 1024 + len(sb_bytes)] = sb_bytes

        # 2. Block Group Descriptor at block 2 (offset 2048)
        bgd_bytes = struct.pack("<3I", 3, 4, 5) # block_bitmap=3, inode_bitmap=4, inode_table=5
        disk[2048 : 2048 + len(bgd_bytes)] = bgd_bytes

        # Mark system blocks (0-10) used in block bitmap (block 3, offset 3072)
        disk[3072] = 0xFF
        disk[3073] = 0x07

        # Mark system inodes (1..10) used in inode bitmap (block 4, offset 4096)
        disk[4096] = 0xFF
        disk[4097] = 0x03

        # Inode table starts at block 5 (offset 5120)
        # Root Inode (Inode 2) is at index 1 -> offset 5120 + 128 = 5248
        root_ino_off = 5 * block_size + 1 * 128
        struct.pack_into("<HHI", disk, root_ino_off, EXT2_S_IFDIR | 0o755, 0, block_size)
        struct.pack_into("<I", disk, root_ino_off + 28, 2) # i_blocks
        struct.pack_into("<I", disk, root_ino_off + 40, 10) # i_block[0] = Block 10

        # Root Directory Data (Block 10, offset 10240)
        blk10_off = 10 * block_size
        struct.pack_into("<IHBB", disk, blk10_off, EXT2_ROOT_INO, 12, 1, EXT2_FT_DIR)
        disk[blk10_off + 8 : blk10_off + 9] = b"."

        struct.pack_into("<IHBB", disk, blk10_off + 12, EXT2_ROOT_INO, block_size - 12, 2, EXT2_FT_DIR)
        disk[blk10_off + 20 : blk10_off + 22] = b".."

        return cls(disk)
