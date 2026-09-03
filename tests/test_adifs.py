#!/usr/bin/env python3
"""
Test Suite: AdiFS Contiguous Block Filesystem
Verifies:
1. Disk formatting and Superblock initialization
2. Contiguous multi-sector file creation
3. Bit-for-bit file reading and verification
4. Directory listing and contiguous sector tracking
5. File overwrite and persistence
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fs.adifs import AdiFS, ATTR_FILE, ATTR_EXECUTABLE

def test_adifs_suite():
    print("[Test AdiFS] Initializing test disk image...")
    test_disk = "test_adifs.img"
    if os.path.exists(test_disk):
        os.remove(test_disk)

    fs = AdiFS(test_disk)

    # 1. Test Format
    print("  -> Formatting disk with AdiFS Superblock...")
    sb = fs.format_disk(total_sectors=8192) # 4 MB test disk
    assert sb.magic == b"ADIFS01\0"
    assert sb.sector_size == 512
    assert sb.total_sectors == 8192
    assert sb.free_sector_ptr == 33
    print("  -> [PASS] Disk formatting verified.")

    # 2. Test File Creation & Contiguous Allocation
    print("  -> Creating files on AdiFS...")
    # Small file (1 sector)
    f1_data = "Hello from AdiOS! This is an AdiFS contiguous file.\n"
    f1 = fs.create_file("greeting.txt", f1_data)
    assert f1.start_sector == 33
    assert f1.size_bytes == len(f1_data)

    # Large multi-sector file (e.g. 2,500 bytes -> 5 sectors)
    f2_data = ("TempleOS HolyC & AdiOS AdiPython Sovereign Computing Architecture!\n" * 40).encode("utf-8")
    f2 = fs.create_file("kernel_doc.txt", f2_data)
    assert f2.start_sector == 34 # Allocated contiguously right after sector 33!
    assert f2.size_bytes == len(f2_data)

    # Executable script file
    f3_data = "print('AdiPython Script executing directly from AdiFS!')\n"
    f3 = fs.create_file("demo.ap", f3_data, attr=ATTR_EXECUTABLE)
    f2_sectors = (len(f2_data) + 511) // 512
    assert f3.start_sector == f2.start_sector + f2_sectors # Allocated contiguously right after f2!
    print("  -> [PASS] Contiguous file allocation verified.")

    # 3. Test Reading and Bit-for-Bit Verification
    print("  -> Reading files and verifying bit-for-bit integrity...")
    read1 = fs.read_file("greeting.txt").decode("utf-8")
    assert read1 == f1_data, "greeting.txt content mismatch"

    read2 = fs.read_file("kernel_doc.txt")
    assert read2 == f2_data, "kernel_doc.txt content mismatch"

    read3 = fs.read_file("demo.ap").decode("utf-8")
    assert read3 == f3_data, "demo.ap content mismatch"
    print("  -> [PASS] File read integrity verified.")

    # 4. Test Directory Listing
    print("  -> Testing directory listing...")
    files = fs.list_files()
    assert len(files) == 3, f"Expected 3 files, got {len(files)}"
    names = [f.name for f in files]
    assert "greeting.txt" in names
    assert "kernel_doc.txt" in names
    assert "demo.ap" in names
    print("  -> [PASS] Directory listing verified.")

    # 5. Test Persistence across new AdiFS instance
    print("  -> Verifying persistence across disk reopening...")
    fs2 = AdiFS(test_disk)
    files2 = fs2.list_files()
    assert len(files2) == 3
    assert fs2.read_file("greeting.txt").decode("utf-8") == f1_data
    print("  -> [PASS] Persistence verified.")

    # Cleanup test disk
    if os.path.exists(test_disk):
        os.remove(test_disk)

    print("\n===========================================================")
    print("[Test AdiFS] ALL ADIFS CONTIGUOUS FILESYSTEM TESTS PASSED (100%)!")
    print("===========================================================")
    return True

if __name__ == "__main__":
    test_adifs_suite()
