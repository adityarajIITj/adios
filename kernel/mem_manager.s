# ==============================================================================
# AdiOS Core Bare-Metal Kernel: Memory Manager (mem_manager.s)
# Dual-Heap Architecture: Physical Page Frame Allocator & Kernel Slab Cache
# Manages 64 MB RAM (16,384 physical 4KB pages)
# ==============================================================================

.section .text
.global palloc_init
.global page_alloc
.global page_free
.global page_count_free
.global kmalloc
.global kfree

# Constants
#define RAM_BASE       0x80000000
#define PAGE_SIZE      4096
#define TOTAL_PAGES    16384     # 64 MB / 4 KB = 16,384 pages
#define BITMAP_WORDS   512       # 16,384 bits / 32 bits per word = 512 words
#define RESERVED_PAGES 1024      # First 4 MB reserved for Kernel & MMIO

# ------------------------------------------------------------------------------
# Page Allocator Initialization
# Reserves first 1024 pages (4 MB), marks pages 1024..16383 as FREE
# ------------------------------------------------------------------------------
palloc_init:
    la t0, page_bitmap

    # Mark first 1024 pages (32 words) as ALLOCATED (0xFFFFFFFF)
    li t1, 32
mark_reserved_loop:
    li t2, 0xFFFFFFFF
    sw t2, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, mark_reserved_loop

    # Mark remaining 480 words as FREE (0x00000000)
    li t1, 480
mark_free_loop:
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, mark_free_loop

    # Initialize kernel heap bump pointer at 0x82000000 (32 MB mark)
    la t0, kheap_ptr
    li t1, 0x82000000
    sw t1, 0(t0)

    ret

# ------------------------------------------------------------------------------
# page_alloc: Allocates one 4KB page frame
# Returns: a0 = physical address (or 0 if out of memory)
# ------------------------------------------------------------------------------
page_alloc:
    la t0, page_bitmap
    li t1, 32                   # Start scanning from word 32 (page 1024)
    li t2, 512                  # BITMAP_WORDS

scan_words_loop:
    slli t3, t1, 2
    add t4, t0, t3              # address of bitmap word
    lw t5, 0(t4)
    li t6, 0xFFFFFFFF
    bne t5, t6, found_free_word
    addi t1, t1, 1
    blt t1, t2, scan_words_loop

    # Out of memory
    li a0, 0
    ret

found_free_word:
    # Scan individual bits 0..31 in word t5 for first 0 bit
    li a1, 0                    # bit index
bit_scan_loop:
    srl a2, t5, a1
    andi a2, a2, 1
    beqz a2, found_free_bit
    addi a1, a1, 1
    li a3, 32
    blt a1, a3, bit_scan_loop

    # Should not reach here
    li a0, 0
    ret

found_free_bit:
    # Set bit a1 in word t4
    li a2, 1
    sll a2, a2, a1
    or t5, t5, a2
    sw t5, 0(t4)                # update bitmap word

    # Compute page index = t1 * 32 + a1
    slli a3, t1, 5
    add a3, a3, a1              # page index (1024..16383)

    # Compute physical address = RAM_BASE + page_index * 4096
    slli a0, a3, 12             # page_index * 4096
    li a4, 0x80000000           # RAM_BASE
    add a0, a0, a4              # a0 = physical address
    ret

# ------------------------------------------------------------------------------
# page_free: Frees a 4KB page frame
# Args: a0 = physical address
# ------------------------------------------------------------------------------
page_free:
    li t0, 0x80000000           # RAM_BASE
    sub a1, a0, t0              # offset from RAM_BASE
    srai a1, a1, 12             # page index = offset / 4096

    # Don't free reserved pages (< 1024)
    li t0, 1024                 # RESERVED_PAGES
    blt a1, t0, page_free_done

    li t0, 16384                # TOTAL_PAGES
    bge a1, t0, page_free_done

    # word index = page index / 32, bit index = page index % 32
    srai t1, a1, 5              # word index
    andi t2, a1, 31             # bit index

    la t3, page_bitmap
    slli t4, t1, 2
    add t4, t3, t4              # word address
    lw t5, 0(t4)

    # Clear bit t2
    li t6, 1
    sll t6, t6, t2
    not t6, t6
    and t5, t5, t6
    sw t5, 0(t4)

page_free_done:
    ret

# ------------------------------------------------------------------------------
# page_count_free: Counts total free 4KB pages
# Returns: a0 = free page count
# ------------------------------------------------------------------------------
page_count_free:
    la t0, page_bitmap
    li t1, 32                   # start word
    li t2, 512                  # BITMAP_WORDS
    li a0, 0                    # count

count_words_loop:
    slli t3, t1, 2
    add t4, t0, t3
    lw t5, 0(t4)

    # Count 0 bits in word t5
    li a1, 0
count_bits_loop:
    srl a2, t5, a1
    andi a2, a2, 1
    bnez a2, skip_zero_bit
    addi a0, a0, 1
skip_zero_bit:
    addi a1, a1, 1
    li a3, 32
    blt a1, a3, count_bits_loop

    addi t1, t1, 1
    blt t1, t2, count_words_loop
    ret

# ------------------------------------------------------------------------------
# Kernel Bump Heap Allocator (kmalloc / kfree)
# ------------------------------------------------------------------------------
kmalloc:
    # Args: a0 = size_bytes
    # Align size to 8 bytes
    addi a0, a0, 7
    andi a0, a0, -8

    la t0, kheap_ptr
    lw a1, 0(t0)                # current heap ptr
    add t1, a1, a0              # new heap ptr
    sw t1, 0(t0)
    mv a0, a1                   # Return allocated buffer address
    ret

kfree:
    # Bump allocator does not free individual slices
    ret

# ------------------------------------------------------------------------------
# BSS: Memory Management Tables
# ------------------------------------------------------------------------------
.section .bss
.align 4
kheap_ptr:      .word 0

# Page Bitmap: 512 words = 2,048 bytes
page_bitmap:
    .space 2048
