# ==============================================================================
# AdiOS Bare-Metal Kernel Block C Verification Harness
# Tests: Scheduler, Memory Manager (palloc), and Virtual Filesystem (VFS)
# ==============================================================================

.section .text
.global _start

_start:
    # 1. Setup Stack
    li sp, 0x81000000

    # 2. Test Scheduler
    call sched_init
    call get_task_count
    # Expected 2 tasks (Idle + Adam)
    li t0, 2
    bne a0, t0, test_failed

    # Spawn test task
    la a0, test_worker
    li a1, 0x81400000
    li a2, 1
    call task_create
    # Expected PID = 2
    li t0, 2
    bne a0, t0, test_failed

    call get_task_count
    li t0, 3
    bne a0, t0, test_failed

    # 3. Test Memory Manager (palloc)
    call palloc_init
    call page_count_free
    # Expected 15360 free pages (16384 - 1024)
    li t0, 15360
    bne a0, t0, test_failed

    # Allocate 1 page
    call page_alloc
    # Expected address: 0x80400000 (page 1024)
    li t0, 0x80400000
    bne a0, t0, test_failed

    # Write test pattern to allocated page
    li t1, 0xDEADBEEF
    sw t1, 0(a0)
    lw t2, 0(a0)
    bne t1, t2, test_failed

    # Free the page
    call page_free
    call page_count_free
    li t0, 15360
    bne a0, t0, test_failed

    # 4. Test VFS & AdiFS Mount
    call vfs_mount
    beqz a0, test_failed

    # Try finding test file "run_test.ap"
    la a0, test_filename
    call vfs_find_file
    # Start sector should be > 0
    blez a0, test_failed

    # Read the file to RAM
    la a0, test_filename
    li a1, 0x80600000
    call vfs_read_file
    blez a0, test_failed

    # All tests passed! Print success to UART
    la a0, success_msg
    call print_uart
    j halt

test_failed:
    la a0, fail_msg
    call print_uart

halt:
    wfi
    j halt

.include "sched.s"
.include "mem_manager.s"
.include "vfs.s"

test_worker:
    # Dummy worker task
    wfi
    j test_worker

print_uart:
    li t0, 0x10000000
pu_loop:
    lb t1, 0(a0)
    beqz t1, pu_done
    sw t1, 0(t0)
    addi a0, a0, 1
    j pu_loop
pu_done:
    ret

.section .data
test_filename:
    .string "run_test.ap"

success_msg:
    .string "[AdiOS Kernel Block C] ALL BARE-METAL KERNEL TESTS PASSED (100%)!\n"

fail_msg:
    .string "[AdiOS Kernel Block C] TEST FAILED!\n"
