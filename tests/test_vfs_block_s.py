#!/usr/bin/env python3
"""
Test Suite: Block S Extensible Native Filesystem Architecture (Ext2 & FAT32)
Verifies:
1. vfs/fat32: BPB parsing, FAT cluster traversal, directory entry parsing, file read
2. vfs/ext2: Superblock magic (0xEF53), BGD, Inode table, directory parsing, file read
"""

import sys
import os
import struct

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vfs.fat32 import FAT32Driver, FAT32_EOC
from vfs.ext2 import Ext2Driver, EXT2_MAGIC, EXT2_ROOT_INO

def test_vfs_block_s_suite():
    print("[Test VFS Block S] Initializing Ext2 & FAT32 Storage Architecture Verification...")

    # 1. Test FAT32 Driver with Synthetic Disk Image
    print("  -> Testing Microsoft FAT32 Filesystem Driver...")
    # Create 128KB synthetic disk image
    disk_fat = bytearray(128 * 1024)

    # Populate Boot Sector (BPB) at sector 0
    # Bytes per sector: 512, Sectors per cluster: 1, Reserved sectors: 32, Num FATs: 2
    struct.pack_into("<H", disk_fat, 11, 512)
    disk_fat[13] = 1 # 1 sector per cluster (512B)
    struct.pack_into("<H", disk_fat, 14, 32)
    disk_fat[16] = 2 # 2 FATs
    struct.pack_into("<I", disk_fat, 32, 256) # 256 total sectors
    struct.pack_into("<I", disk_fat, 36, 16)  # 16 sectors per FAT
    struct.pack_into("<I", disk_fat, 44, 2)   # Root cluster = 2

    fat_start = 32 * 512
    data_start = (32 + 2 * 16) * 512 # Sector 64 * 512 = 32768

    # FAT table: Root cluster (2) is EOF
    struct.pack_into("<I", disk_fat, fat_start + 2 * 4, 0x0FFFFFFF)
    # File clusters: Cluster 3 -> Cluster 4 -> EOF
    struct.pack_into("<I", disk_fat, fat_start + 3 * 4, 4)
    struct.pack_into("<I", disk_fat, fat_start + 4 * 4, 0x0FFFFFFF)

    # Root Directory at Cluster 2:
    # Directory entry for "README  TXT"
    root_offset = data_start # Cluster 2 offset
    # 8.3 filename: "README  TXT"
    disk_fat[root_offset:root_offset + 11] = b"README  TXT"
    disk_fat[root_offset + 11] = 0x20 # Archive attribute
    struct.pack_into("<H", disk_fat, root_offset + 20, 0) # High cluster
    struct.pack_into("<H", disk_fat, root_offset + 26, 3) # Low cluster = 3
    struct.pack_into("<I", disk_fat, root_offset + 28, 600) # Size = 600 bytes

    # File data at Cluster 3 (512B) and Cluster 4 (88B)
    c3_offset = data_start + (3 - 2) * 512
    c4_offset = data_start + (4 - 2) * 512
    disk_fat[c3_offset:c3_offset + 512] = b"A" * 512
    disk_fat[c4_offset:c4_offset + 88] = b"B" * 88

    driver_fat = FAT32Driver(disk_fat)
    entries = driver_fat.list_root_directory()
    assert len(entries) == 1
    assert entries[0].name == "README.TXT"
    assert entries[0].size == 600

    content = driver_fat.read_file("README.TXT")
    assert len(content) == 600
    assert content[:512] == b"A" * 512
    assert content[512:] == b"B" * 88
    print("  -> [PASS] FAT32 cluster chain & file read verified.")

    # 2. Test Linux Ext2 Driver with Synthetic Disk Image
    print("  -> Testing Linux Ext2 Filesystem Driver...")
    disk_ext2 = bytearray(128 * 1024)

    # Populate Ext2 Superblock at offset 1024 (Block size = 1024, s_log_block_size = 0)
    sb_bytes = struct.pack(
        "<13I3H",
        32,      # s_inodes_count
        128,     # s_blocks_count
        0,       # s_r_blocks_count
        100,     # s_free_blocks_count
        20,      # s_free_inodes_count
        1,       # s_first_data_block (1 for 1024B blocks)
        0,       # s_log_block_size (0 -> 1024)
        0,       # s_log_frag_size
        128,     # s_blocks_per_group
        128,     # s_frags_per_group
        32,      # s_inodes_per_group
        0,       # s_mtime
        0,       # s_wtime
        1,       # s_mnt_count
        100,     # s_max_mnt_count
        EXT2_MAGIC # 0xEF53
    )
    disk_ext2[1024:1024 + len(sb_bytes)] = sb_bytes

    # Block Group Descriptor at Block 2 (offset 2048)
    # bg_inode_table at Block 5
    struct.pack_into("<I", disk_ext2, 2048 + 8, 5)

    inode_table_offset = 5 * 1024

    # Root directory Inode 2: offset = inode_table_offset + (2 - 1) * 128
    root_ino_offset = inode_table_offset + 128
    # Mode = 0x41ED (Directory), size = 1024, direct block 0 = Block 10
    struct.pack_into("<HHI", disk_ext2, root_ino_offset, 0x41ED, 0, 1024)
    struct.pack_into("<I", disk_ext2, root_ino_offset + 40, 10) # Block 10

    # Root directory contents at Block 10 (offset 10 * 1024):
    # Entry 1: Inode 11, rec_len 1024, name_len 9, type 1 (REG_FILE), name "hello.txt"
    blk10_offset = 10 * 1024
    struct.pack_into("<IHBB", disk_ext2, blk10_offset, 11, 1024, 9, 1)
    disk_ext2[blk10_offset + 8:blk10_offset + 8 + 9] = b"hello.txt"

    # Inode 11: offset = inode_table_offset + (11 - 1) * 128
    ino11_offset = inode_table_offset + 10 * 128
    test_message = b"Sovereign AdiOS Kernel Operating System"
    struct.pack_into("<HHI", disk_ext2, ino11_offset, 0x81A4, 0, len(test_message))
    struct.pack_into("<I", disk_ext2, ino11_offset + 40, 12) # Block 12

    # Data at Block 12
    blk12_offset = 12 * 1024
    disk_ext2[blk12_offset:blk12_offset + len(test_message)] = test_message

    driver_ext2 = Ext2Driver(disk_ext2)
    assert driver_ext2.sb.s_magic == EXT2_MAGIC

    root_files = driver_ext2.list_root()
    assert len(root_files) == 1
    assert root_files[0] == (11, "hello.txt")

    file_inode = driver_ext2.read_inode(11)
    read_data = driver_ext2.read_file_data(file_inode)
    assert read_data == test_message
    print("  -> [PASS] Ext2 superblock, inodes & file reading verified.")

    print("\n[Test VFS Block S] ALL BLOCK S EXT2 & FAT32 TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_vfs_block_s_suite()
