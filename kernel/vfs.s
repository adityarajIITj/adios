# ==============================================================================
# AdiOS Core Bare-Metal Kernel: Virtual Filesystem & AdiFS Driver (vfs.s)
# Direct Bare-Metal RISC-V Block Driver Interfacing with MMIO Disk (0x10001000)
# Zero-Fragmentation Contiguous Sector DMA Streaming
# ==============================================================================

.section .text
.global vfs_mount
.global vfs_find_file
.global vfs_read_file
.global disk_read_sector

# MMIO Disk Controller Registers
#define DISK_REG_SECTOR   0x10001000
#define DISK_REG_RAM_ADDR 0x10001004
#define DISK_REG_CMD      0x10001008
#define DISK_REG_STATUS   0x1000100C

# Disk Commands
#define DISK_CMD_READ     1
#define DISK_CMD_WRITE    2

# Scratch Buffer for Directory Parsing
#define VFS_SCRATCH_BUF   0x80500000

# ------------------------------------------------------------------------------
# disk_read_sector: Reads a 512-byte sector via MMIO DMA
# Args: a0 = sector_number, a1 = dest_ram_addr
# ------------------------------------------------------------------------------
disk_read_sector:
    li t0, 0x10001000           # DISK_REG_SECTOR
    sw a0, 0(t0)                # Set target sector
    sw a1, 4(t0)                # Set destination RAM address
    li t1, 1                    # DISK_CMD_READ
    sw t1, 8(t0)                # Trigger DMA READ command

wait_disk_ready:
    lw t1, 12(t0)               # Poll DISK_STATUS
    bnez t1, wait_disk_ready

    ret

# ------------------------------------------------------------------------------
# vfs_mount: Mounts AdiFS filesystem and verifies Superblock (Sector 0)
# Returns: a0 = 1 if successful, 0 if invalid magic
# ------------------------------------------------------------------------------
vfs_mount:
    addi sp, sp, -16
    sw ra, 12(sp)

    # Read Sector 0 (Superblock) into scratch buffer
    li a0, 0
    li a1, 0x80500000           # VFS_SCRATCH_BUF
    call disk_read_sector

    # Check Magic: "ADIFS01\0"
    # Word 0: 'A' | ('D'<<8) | ('I'<<16) | ('F'<<24) = 0x46494441
    # Word 1: 'S' | ('0'<<8) | ('1'<<16) | (0<<24)   = 0x00313053
    li t0, 0x80500000
    lw t1, 0(t0)
    li t2, 0x46494441
    bne t1, t2, mount_failed

    lw t1, 4(t0)
    li t2, 0x00313053
    bne t1, t2, mount_failed

    # Superblock verified!
    la t0, vfs_mounted_flag
    li t1, 1
    sw t1, 0(t0)

    li a0, 1
    j mount_done

mount_failed:
    li a0, 0

mount_done:
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# ------------------------------------------------------------------------------
# vfs_find_file: Searches directory for a given filename
# Args: a0 = filename_string_ptr
# Returns: a0 = start_sector, a1 = byte_size (or a0 = -1 if not found)
# ------------------------------------------------------------------------------
vfs_find_file:
    addi sp, sp, -40
    sw ra, 36(sp)
    sw s0, 32(sp)
    sw s1, 28(sp)
    sw s2, 24(sp)
    sw s3, 20(sp)
    sw s4, 16(sp)

    mv s0, a0                   # s0 = target filename ptr

    # Scan directory sectors 1..32 (256 entries total, 8 per sector)
    li s1, 1                    # s1 = current directory sector
    li s2, 33                   # end sector

dir_sector_loop:
    mv a0, s1
    li a1, 0x80500000           # VFS_SCRATCH_BUF
    call disk_read_sector

    # Scan 8 directory entries in this sector (64 bytes each)
    li s3, 0                    # entry index 0..7
entry_scan_loop:
    slli t1, s3, 6              # s3 * 64 bytes
    li s4, 0x80500000           # VFS_SCRATCH_BUF
    add s4, s4, t1              # s4 = entry pointer

    # Check if entry is valid (first char of name != 0)
    lb t3, 0(s4)
    beqz t3, next_entry

    # Compare filename (up to 32 chars)
    mv a0, s0
    mv a1, s4
    call vfs_strcmp
    beqz a0, file_match_found

next_entry:
    addi s3, s3, 1
    li t3, 8
    blt s3, t3, entry_scan_loop

    addi s1, s1, 1
    blt s1, s2, dir_sector_loop

    # Not found
    li a0, -1
    li a1, 0
    j find_file_done

file_match_found:
    # Entry matched!
    # Offset 32: start_sector (uint32)
    # Offset 36: byte_size    (uint32)
    lw a0, 32(s4)               # a0 = start_sector
    lw a1, 36(s4)               # a1 = byte_size

find_file_done:
    lw s4, 16(sp)
    lw s3, 20(sp)
    lw s2, 24(sp)
    lw s1, 28(sp)
    lw s0, 32(sp)
    lw ra, 36(sp)
    addi sp, sp, 40
    ret

# ------------------------------------------------------------------------------
# vfs_read_file: Reads entire file from AdiFS disk into RAM
# Args: a0 = filename_string_ptr, a1 = dest_ram_addr
# Returns: a0 = bytes_read (or -1 if file not found)
# ------------------------------------------------------------------------------
vfs_read_file:
    addi sp, sp, -36
    sw ra, 32(sp)
    sw s0, 28(sp)
    sw s1, 24(sp)
    sw s2, 20(sp)
    sw s3, 16(sp)

    mv s2, a1                   # dest RAM address

    call vfs_find_file
    li t0, -1
    beq a0, t0, read_file_failed

    mv s0, a0                   # start sector
    mv s1, a1                   # byte size

    # Number of sectors = (byte_size + 511) / 512
    addi s3, s1, 511
    srai s3, s3, 9              # sector count

read_sectors_loop:
    beqz s3, read_sectors_done
    mv a0, s0
    mv a1, s2
    call disk_read_sector

    addi s0, s0, 1              # next sector
    addi s2, s2, 512            # advance RAM pointer by 512 bytes
    addi s3, s3, -1
    j read_sectors_loop

read_sectors_done:
    mv a0, s1                   # Return total bytes read
    j read_file_done

read_file_failed:
    li a0, -1

read_file_done:
    lw s3, 16(sp)
    lw s2, 20(sp)
    lw s1, 24(sp)
    lw s0, 28(sp)
    lw ra, 32(sp)
    addi sp, sp, 36
    ret

# ------------------------------------------------------------------------------
# Helper: vfs_strcmp
# ------------------------------------------------------------------------------
vfs_strcmp:
    li t0, 0
strcmp_loop:
    add t1, a0, t0
    lb t1, 0(t1)
    add t2, a1, t0
    lb t2, 0(t2)
    bne t1, t2, strcmp_diff
    beqz t1, strcmp_same
    addi t0, t0, 1
    li t3, 32
    blt t0, t3, strcmp_loop
strcmp_same:
    li a0, 0
    ret
strcmp_diff:
    li a0, 1
    ret

# ------------------------------------------------------------------------------
# BSS
# ------------------------------------------------------------------------------
.section .bss
.align 4
vfs_mounted_flag: .word 0
