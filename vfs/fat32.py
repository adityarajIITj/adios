#!/usr/bin/env python3
"""
AdiOS Filesystem Subsystem: FAT32 Driver (fat32.py)
Implements Microsoft FAT32 filesystem driver from raw disk sectors:
- BIOS Parameter Block (BPB) & Boot Sector parsing and initialization
- FSInfo sector management (free cluster count, next cluster hint)
- File Allocation Table (FAT) cluster chain traversal, allocation, and deallocation
- 32-byte Directory Entry decoding and encoding (8.3 filenames, size, cluster ptrs)
- Direct cluster sector read/write operations with multi-FAT mirroring
- Subdirectory navigation, file creation, truncation, writing, and deletion
- Synthetic FAT32 volume format generator (zero external dependencies)
"""

import struct
import time
from typing import List, Dict, Tuple, Optional, Any

FAT32_EOC = 0x0FFFFFF8          # End of cluster marker threshold
FAT32_EOC_VAL = 0x0FFFFFFF      # Canonical EOC pointer
FAT32_FREE = 0x00000000         # Free cluster marker
FAT32_BAD = 0x0FFFFFF7          # Bad cluster marker

ATTR_READ_ONLY = 0x01
ATTR_HIDDEN    = 0x02
ATTR_SYSTEM    = 0x04
ATTR_VOLUME_ID = 0x08
ATTR_DIRECTORY = 0x10
ATTR_ARCHIVE   = 0x20
ATTR_LFN       = 0x0F

class BPB:
    """BIOS Parameter Block."""
    def __init__(self, sector: bytes):
        self.oem_name = sector[3:11].decode("ascii", errors="replace").strip()
        self.bytes_per_sector = struct.unpack_from("<H", sector, 11)[0]
        self.sectors_per_cluster = sector[13]
        self.reserved_sectors = struct.unpack_from("<H", sector, 14)[0]
        self.num_fats = sector[16]
        self.root_entries_16 = struct.unpack_from("<H", sector, 17)[0]
        self.total_sectors_16 = struct.unpack_from("<H", sector, 19)[0]
        self.media_type = sector[21]
        self.fat_size_16 = struct.unpack_from("<H", sector, 22)[0]
        self.sectors_per_track = struct.unpack_from("<H", sector, 24)[0]
        self.num_heads = struct.unpack_from("<H", sector, 26)[0]
        self.hidden_sectors = struct.unpack_from("<I", sector, 28)[0]
        self.total_sectors = struct.unpack_from("<I", sector, 32)[0]
        if self.total_sectors == 0:
            self.total_sectors = self.total_sectors_16

        # FAT32 specific header
        self.sectors_per_fat = struct.unpack_from("<I", sector, 36)[0]
        self.ext_flags = struct.unpack_from("<H", sector, 40)[0]
        self.fs_version = struct.unpack_from("<H", sector, 42)[0]
        self.root_cluster = struct.unpack_from("<I", sector, 44)[0]
        self.fs_info_sector = struct.unpack_from("<H", sector, 48)[0]
        self.backup_boot_sector = struct.unpack_from("<H", sector, 50)[0]
        self.drive_number = sector[64]
        self.boot_sig = sector[66]
        self.volume_id = struct.unpack_from("<I", sector, 67)[0]
        self.volume_label = sector[71:82].decode("ascii", errors="replace").strip()
        self.fs_type = sector[82:90].decode("ascii", errors="replace").strip()


class FAT32Entry:
    """Represents a decoded FAT32 directory entry."""
    def __init__(self, name: str, is_dir: bool, size: int, first_cluster: int,
                 attributes: int = 0, dir_cluster: int = 0, entry_offset: int = 0):
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.first_cluster = first_cluster
        self.attributes = attributes
        self.dir_cluster = dir_cluster
        self.entry_offset = entry_offset

    def __repr__(self) -> str:
        kind = "DIR" if self.is_dir else "FILE"
        return f"<FAT32Entry {self.name} [{kind}] size={self.size} cluster={self.first_cluster}>"


class FAT32Driver:
    """
    Complete FAT32 Storage Driver reading, modifying, and formatting raw disk images.
    Provides cluster allocation, directory traversal, file read/write, and cluster chain management.
    """
    def __init__(self, disk_image: bytearray):
        self.disk = disk_image
        self.bpb = BPB(disk_image[:512])
        self.fat_start_offset = self.bpb.reserved_sectors * self.bpb.bytes_per_sector
        self.data_start_offset = (self.bpb.reserved_sectors + self.bpb.num_fats * self.bpb.sectors_per_fat) * self.bpb.bytes_per_sector
        self.cluster_size = self.bpb.sectors_per_cluster * self.bpb.bytes_per_sector
        self.total_clusters = (len(disk_image) - self.data_start_offset) // self.cluster_size + 2

    def _cluster_offset(self, cluster: int) -> int:
        if cluster < 2:
            raise ValueError(f"Invalid cluster number: {cluster} (clusters start at 2)")
        return self.data_start_offset + (cluster - 2) * self.cluster_size

    def get_next_cluster(self, cluster: int) -> int:
        fat_entry_offset = self.fat_start_offset + cluster * 4
        if fat_entry_offset + 4 > len(self.disk):
            return FAT32_EOC_VAL
        entry = struct.unpack_from("<I", self.disk, fat_entry_offset)[0] & 0x0FFFFFFF
        return entry

    def set_fat_entry(self, cluster: int, next_val: int):
        """Sets next cluster pointer in all mirrored FAT tables."""
        val_bytes = struct.pack("<I", next_val & 0x0FFFFFFF)
        fat_size_bytes = self.bpb.sectors_per_fat * self.bpb.bytes_per_sector
        for fat_idx in range(self.bpb.num_fats):
            fat_offset = self.fat_start_offset + (fat_idx * fat_size_bytes) + (cluster * 4)
            if fat_offset + 4 <= len(self.disk):
                self.disk[fat_offset:fat_offset + 4] = val_bytes

    def allocate_cluster(self, prev_cluster: Optional[int] = None) -> int:
        """Finds the first free cluster, marks it as EOC, links from prev_cluster, and returns index."""
        start_cluster = 2
        for c in range(start_cluster, self.total_clusters):
            curr = self.get_next_cluster(c)
            if curr == FAT32_FREE:
                self.set_fat_entry(c, FAT32_EOC_VAL)
                # Zero out the newly allocated cluster block
                c_off = self._cluster_offset(c)
                self.disk[c_off:c_off + self.cluster_size] = b"\x00" * self.cluster_size

                if prev_cluster is not None and prev_cluster >= 2:
                    self.set_fat_entry(prev_cluster, c)
                return c

        raise IOError("FAT32: Disk full - no free clusters available")

    def free_cluster_chain(self, start_cluster: int):
        """Traverses cluster chain and resets all entries to FAT32_FREE."""
        curr = start_cluster
        while 2 <= curr < FAT32_EOC:
            next_c = self.get_next_cluster(curr)
            self.set_fat_entry(curr, FAT32_FREE)
            curr = next_c

    def read_cluster_chain(self, start_cluster: int) -> bytearray:
        """Reads all cluster data linked from start_cluster."""
        data = bytearray()
        curr = start_cluster
        visited = set()
        while 2 <= curr < FAT32_EOC:
            if curr in visited:
                break # Avoid infinite loop on circular corrupted chains
            visited.add(curr)
            offset = self._cluster_offset(curr)
            if offset + self.cluster_size <= len(self.disk):
                data.extend(self.disk[offset:offset + self.cluster_size])
            curr = self.get_next_cluster(curr)
        return data

    def write_cluster_chain(self, start_cluster: Optional[int], data: bytes) -> int:
        """
        Writes data across a cluster chain, allocating additional clusters or freeing excess clusters.
        Returns the first cluster of the chain.
        """
        if not data:
            if start_cluster is not None and start_cluster >= 2:
                self.free_cluster_chain(start_cluster)
            return 0

        chunks = [data[i:i + self.cluster_size] for i in range(0, len(data), self.cluster_size)]
        needed = len(chunks)

        # Collect existing cluster chain
        existing_chain = []
        curr = start_cluster if start_cluster is not None else 0
        while 2 <= curr < FAT32_EOC:
            existing_chain.append(curr)
            curr = self.get_next_cluster(curr)

        # Allocate more or free excess
        chain = []
        if len(existing_chain) >= needed:
            chain = existing_chain[:needed]
            if len(existing_chain) > needed:
                # Free excess
                excess_start = existing_chain[needed]
                self.free_cluster_chain(excess_start)
                self.set_fat_entry(chain[-1], FAT32_EOC_VAL)
        else:
            chain = list(existing_chain)
            last_c = chain[-1] if chain else None
            while len(chain) < needed:
                new_c = self.allocate_cluster(last_c)
                chain.append(new_c)
                last_c = new_c

        # Write data into clusters
        for i, chunk in enumerate(chunks):
            c = chain[i]
            c_off = self._cluster_offset(c)
            padded = chunk.ljust(self.cluster_size, b"\x00")
            self.disk[c_off:c_off + self.cluster_size] = padded

        return chain[0] if chain else 0

    def _decode_83_name(self, raw_entry: bytes) -> str:
        name_part = raw_entry[0:8].decode("ascii", errors="replace").rstrip()
        ext_part = raw_entry[8:11].decode("ascii", errors="replace").rstrip()
        if ext_part:
            return f"{name_part}.{ext_part}"
        return name_part

    def _encode_83_name(self, filename: str) -> bytes:
        filename = filename.strip()
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
        else:
            name, ext = filename, ""
        name = name.replace(" ", "").upper()[:8].ljust(8, " ")
        ext = ext.replace(" ", "").upper()[:3].ljust(3, " ")
        return (name + ext).encode("ascii")

    def list_directory(self, dir_cluster: int) -> List[FAT32Entry]:
        """Lists directory entries stored starting at dir_cluster."""
        dir_data = self.read_cluster_chain(dir_cluster)
        entries = []
        for i in range(0, len(dir_data), 32):
            raw_entry = dir_data[i:i + 32]
            if len(raw_entry) < 32:
                break
            first_byte = raw_entry[0]
            if first_byte == 0x00:
                break # Free and no subsequent entries
            if first_byte == 0xE5:
                continue # Deleted entry

            attr = raw_entry[11]
            if attr == ATTR_LFN:
                continue # Skip LFN entries for raw 8.3 driver

            filename = self._decode_83_name(raw_entry)
            is_dir = bool(attr & ATTR_DIRECTORY)
            cluster_high = struct.unpack_from("<H", raw_entry, 20)[0]
            cluster_low = struct.unpack_from("<H", raw_entry, 26)[0]
            first_cluster = (cluster_high << 16) | cluster_low
            size = struct.unpack_from("<I", raw_entry, 28)[0]

            entries.append(FAT32Entry(
                name=filename,
                is_dir=is_dir,
                size=size,
                first_cluster=first_cluster,
                attributes=attr,
                dir_cluster=dir_cluster,
                entry_offset=i
            ))
        return entries

    def list_root_directory(self) -> List[FAT32Entry]:
        return self.list_directory(self.bpb.root_cluster)

    def read_file(self, filename: str, dir_cluster: Optional[int] = None) -> bytes:
        target_dir = dir_cluster if dir_cluster is not None else self.bpb.root_cluster
        entries = self.list_directory(target_dir)
        for entry in entries:
            if entry.name.upper() == filename.upper() and not entry.is_dir:
                data = self.read_cluster_chain(entry.first_cluster)
                return bytes(data[:entry.size])
        raise FileNotFoundError(f"FAT32: File '{filename}' not found in directory")

    def _find_dir_slot(self, dir_cluster: int) -> Tuple[int, int]:
        """Finds a free 32-byte slot in a directory (offset within chain, and cluster)."""
        curr = dir_cluster
        while 2 <= curr < FAT32_EOC:
            c_off = self._cluster_offset(curr)
            for i in range(0, self.cluster_size, 32):
                slot = self.disk[c_off + i:c_off + i + 32]
                if slot[0] in (0x00, 0xE5):
                    return (curr, c_off + i)
            next_c = self.get_next_cluster(curr)
            if next_c >= FAT32_EOC:
                # Directory needs expansion
                new_c = self.allocate_cluster(curr)
                new_off = self._cluster_offset(new_c)
                return (new_c, new_off)
            curr = next_c
        raise IOError("FAT32: Unable to locate directory slot")

    def write_file(self, filename: str, data: bytes, dir_cluster: Optional[int] = None):
        """Creates or updates a file in the directory with provided data."""
        target_dir = dir_cluster if dir_cluster is not None else self.bpb.root_cluster
        entries = self.list_directory(target_dir)
        target_entry = None
        for entry in entries:
            if entry.name.upper() == filename.upper() and not entry.is_dir:
                target_entry = entry
                break

        if target_entry:
            # Overwrite existing file
            first_c = self.write_cluster_chain(target_entry.first_cluster, data)
            # Update directory entry size and cluster pointers
            dir_c = target_entry.dir_cluster
            # Calculate physical disk offset of directory entry
            # Walk directory cluster chain to entry_offset
            c_idx = target_entry.entry_offset // self.cluster_size
            curr = dir_c
            for _ in range(c_idx):
                curr = self.get_next_cluster(curr)
            phys_off = self._cluster_offset(curr) + (target_entry.entry_offset % self.cluster_size)

            struct.pack_into("<H", self.disk, phys_off + 20, (first_c >> 16) & 0xFFFF)
            struct.pack_into("<H", self.disk, phys_off + 26, first_c & 0xFFFF)
            struct.pack_into("<I", self.disk, phys_off + 28, len(data))
        else:
            # Create new file
            first_c = self.write_cluster_chain(None, data)
            _, slot_phys_off = self._find_dir_slot(target_dir)

            enc_name = self._encode_83_name(filename)
            entry_bytes = bytearray(32)
            entry_bytes[0:11] = enc_name
            entry_bytes[11] = ATTR_ARCHIVE
            # DOS timestamp: standard epoch placeholder
            struct.pack_into("<H", entry_bytes, 14, 0x5420) # Time
            struct.pack_into("<H", entry_bytes, 16, 0x5420) # Date
            struct.pack_into("<H", entry_bytes, 20, (first_c >> 16) & 0xFFFF)
            struct.pack_into("<H", entry_bytes, 26, first_c & 0xFFFF)
            struct.pack_into("<I", entry_bytes, 28, len(data))

            self.disk[slot_phys_off:slot_phys_off + 32] = entry_bytes

    def delete_file(self, filename: str, dir_cluster: Optional[int] = None):
        """Deletes a file, freeing its cluster chain and marking entry as 0xE5."""
        target_dir = dir_cluster if dir_cluster is not None else self.bpb.root_cluster
        entries = self.list_directory(target_dir)
        for entry in entries:
            if entry.name.upper() == filename.upper() and not entry.is_dir:
                if entry.first_cluster >= 2:
                    self.free_cluster_chain(entry.first_cluster)
                # Find physical entry
                c_idx = entry.entry_offset // self.cluster_size
                curr = target_dir
                for _ in range(c_idx):
                    curr = self.get_next_cluster(curr)
                phys_off = self._cluster_offset(curr) + (entry.entry_offset % self.cluster_size)
                self.disk[phys_off] = 0xE5 # Mark deleted
                return
        raise FileNotFoundError(f"FAT32: File '{filename}' not found for deletion")

    def mkdir(self, dirname: str, dir_cluster: Optional[int] = None) -> int:
        """Creates a subdirectory, initializing '.' and '..' entries."""
        target_dir = dir_cluster if dir_cluster is not None else self.bpb.root_cluster
        new_c = self.allocate_cluster(None)
        new_c_off = self._cluster_offset(new_c)

        # Create '.' entry pointing to new_c
        dot_entry = bytearray(32)
        dot_entry[0:11] = b".          "
        dot_entry[11] = ATTR_DIRECTORY
        struct.pack_into("<H", dot_entry, 20, (new_c >> 16) & 0xFFFF)
        struct.pack_into("<H", dot_entry, 26, new_c & 0xFFFF)

        # Create '..' entry pointing to target_dir (or 0 if root)
        parent_ptr = target_dir if target_dir != self.bpb.root_cluster else 0
        dotdot_entry = bytearray(32)
        dotdot_entry[0:11] = b"..         "
        dotdot_entry[11] = ATTR_DIRECTORY
        struct.pack_into("<H", dotdot_entry, 20, (parent_ptr >> 16) & 0xFFFF)
        struct.pack_into("<H", dotdot_entry, 26, parent_ptr & 0xFFFF)

        self.disk[new_c_off:new_c_off + 32] = dot_entry
        self.disk[new_c_off + 32:new_c_off + 64] = dotdot_entry

        # Add entry into parent directory
        _, slot_phys_off = self._find_dir_slot(target_dir)
        enc_name = self._encode_83_name(dirname)
        entry_bytes = bytearray(32)
        entry_bytes[0:11] = enc_name
        entry_bytes[11] = ATTR_DIRECTORY
        struct.pack_into("<H", entry_bytes, 20, (new_c >> 16) & 0xFFFF)
        struct.pack_into("<H", entry_bytes, 26, new_c & 0xFFFF)
        struct.pack_into("<I", entry_bytes, 28, 0)
        self.disk[slot_phys_off:slot_phys_off + 32] = entry_bytes

        return new_c

    @classmethod
    def create_formatted_disk(cls, size_mb: int = 8, volume_label: str = "ADIOS_FAT") -> "FAT32Driver":
        """
        Synthesizes a raw, fully formatted FAT32 filesystem in memory.
        Calculates BPB parameters, initializes boot record, FSInfo, dual FATs, and root directory.
        """
        total_sectors = (size_mb * 1024 * 1024) // 512
        sectors_per_cluster = 8 # 4KB clusters
        reserved_sectors = 32
        num_fats = 2

        # Estimate sectors per FAT: total_sectors / sectors_per_cluster entries * 4 bytes / 512
        est_clusters = total_sectors // sectors_per_cluster
        sectors_per_fat = ((est_clusters * 4) + 511) // 512 + 8

        disk_size = total_sectors * 512
        disk = bytearray(disk_size)

        # Build BPB Boot Sector (Sector 0)
        boot_sector = bytearray(512)
        boot_sector[0:3] = b"\xEB\x58\x90" # JMP short
        boot_sector[3:11] = b"MSWIN4.1"   # OEM ID
        struct.pack_into("<H", boot_sector, 11, 512)                  # Bytes per sector
        boot_sector[13] = sectors_per_cluster                         # Sectors per cluster
        struct.pack_into("<H", boot_sector, 14, reserved_sectors)    # Reserved sectors
        boot_sector[16] = num_fats                                    # Number of FATs
        struct.pack_into("<H", boot_sector, 17, 0)                    # Root entries (0 for FAT32)
        struct.pack_into("<H", boot_sector, 19, 0)                    # 16-bit total sectors
        boot_sector[21] = 0xF8                                        # Media descriptor (fixed disk)
        struct.pack_into("<H", boot_sector, 22, 0)                    # FAT size 16 (0 for FAT32)
        struct.pack_into("<H", boot_sector, 24, 63)                   # Sectors per track
        struct.pack_into("<H", boot_sector, 26, 255)                  # Number of heads
        struct.pack_into("<I", boot_sector, 28, 0)                    # Hidden sectors
        struct.pack_into("<I", boot_sector, 32, total_sectors)        # Total sectors 32-bit

        # FAT32 Extended Header
        struct.pack_into("<I", boot_sector, 36, sectors_per_fat)      # Sectors per FAT
        struct.pack_into("<H", boot_sector, 40, 0)                    # Extended flags
        struct.pack_into("<H", boot_sector, 42, 0)                    # FS Version
        struct.pack_into("<I", boot_sector, 44, 2)                    # Root cluster (Cluster 2)
        struct.pack_into("<H", boot_sector, 48, 1)                    # FSInfo sector
        struct.pack_into("<H", boot_sector, 50, 6)                    # Backup boot sector
        boot_sector[64] = 0x80                                        # Drive number
        boot_sector[66] = 0x29                                        # Boot signature
        struct.pack_into("<I", boot_sector, 67, 0x19980808)           # Volume ID
        boot_sector[71:82] = volume_label.ljust(11, " ").encode("ascii")[:11]
        boot_sector[82:90] = b"FAT32   "
        boot_sector[510:512] = b"\x55\xAA"                            # MBR Boot Signature
        disk[0:512] = boot_sector

        # Build FSInfo Sector (Sector 1)
        fsinfo = bytearray(512)
        fsinfo[0:4] = b"RRaA"                                         # Lead signature
        fsinfo[484:488] = b"rrAa"                                     # Struct signature
        struct.pack_into("<I", fsinfo, 488, est_clusters - 1)         # Free clusters
        struct.pack_into("<I", fsinfo, 492, 3)                        # Next free cluster hint
        fsinfo[510:512] = b"\x55\xAA"
        disk[512:1024] = fsinfo

        # Initialize FAT entries for Cluster 0 (media type), Cluster 1 (clean shutdown/EOC), Cluster 2 (root dir EOC)
        fat_start = reserved_sectors * 512
        fat_size = sectors_per_fat * 512
        for fat_i in range(num_fats):
            f_offset = fat_start + fat_i * fat_size
            struct.pack_into("<I", disk, f_offset + 0, 0x0FFFFFF8)     # Cluster 0
            struct.pack_into("<I", disk, f_offset + 4, 0x0FFFFFFF)     # Cluster 1
            struct.pack_into("<I", disk, f_offset + 8, 0x0FFFFFFF)     # Cluster 2 (Root directory end)

        return cls(disk)


if __name__ == "__main__":
    driver = FAT32Driver.create_formatted_disk(size_mb=4, volume_label="TEST_OS")
    driver.write_file("TEST.TXT", b"Hello FAT32 sovereign world!")
    content = driver.read_file("TEST.TXT")
    assert content == b"Hello FAT32 sovereign world!"
    print("FAT32 format, write, and read verified successfully.")
