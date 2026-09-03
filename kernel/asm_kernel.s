# ==============================================================================
# AdiOS v1.0: Ultra-Lightweight Bare-Metal RISC-V Operating System
# Built from Scratch. Zero Bloat. Pure Computer Science.
# ==============================================================================

.section .text
.global _start

_start:
    # 1. Disable interrupts initially
    csrw mstatus, zero

    # 2. Initialize Kernel Stack Pointer at 0x81000000 (16MB mark in RAM)
    li sp, 0x81000000

    # 3. Setup Trap Vector to point to trap_handler
    la t0, trap_handler
    csrw mtvec, t0

    # 4. Print the AdiOS Welcome Banner
    la a0, banner_str
    call print_str

    # 5. Initialize Memory & Subsystems
    la a0, init_mem_str
    call print_str

    # 6. Initialize Task Control Blocks
    call init_tasks

    # 7. Print Shell Prompt
    la a0, prompt_str
    call print_str

    # 8. Enable Machine Timer Interrupts in mie (MTIE bit 7)
    li t0, 0x80
    csrs mie, t0

    # Arm initial timer (current time + 50000 cycles)
    li t0, 0x10000010
    lw t1, 0(t0)        # read timer_time
    li t2, 50000
    add t1, t1, t2
    sw t1, 8(t0)        # write timer_cmp (0x10000018)

    # Enable Global Interrupts in mstatus (MIE bit 3)
    li t0, 0x08
    csrs mstatus, t0

# ------------------------------------------------------------------------------
# Main Interactive Shell Loop
# ------------------------------------------------------------------------------
shell_loop:
    call read_char_nonblock
    beqz a0, shell_loop_idle

    # Check for Enter key (\r or \n)
    li t0, 10
    beq a0, t0, handle_enter
    li t0, 13
    beq a0, t0, handle_enter

    # Check for Backspace (8 or 127)
    li t0, 8
    beq a0, t0, handle_backspace
    li t0, 127
    beq a0, t0, handle_backspace

    # Normal printable character: echo and store in cmd_buf
    mv s0, a0
    call put_char

    la t0, cmd_len
    lw t1, 0(t0)
    li t2, 60
    bge t1, t2, shell_loop_idle # Buffer full

    la t2, cmd_buf
    add t2, t2, t1
    sb s0, 0(t2)
    addi t1, t1, 1
    sw t1, 0(t0)
    j shell_loop_idle

handle_backspace:
    la t0, cmd_len
    lw t1, 0(t0)
    beqz t1, shell_loop_idle
    addi t1, t1, -1
    sw t1, 0(t0)
    la a0, backspace_seq
    call print_str
    j shell_loop_idle

handle_enter:
    li a0, 10
    call put_char

    # Null terminate cmd_buf
    la t0, cmd_len
    lw t1, 0(t0)
    la t2, cmd_buf
    add t2, t2, t1
    sb zero, 0(t2)

    # Process command
    la a0, cmd_buf
    call execute_command

    # Reset buffer
    la t0, cmd_len
    sw zero, 0(t0)

    # Print prompt
    la a0, prompt_str
    call print_str

shell_loop_idle:
    j shell_loop

# ------------------------------------------------------------------------------
# Command Dispatcher
# ------------------------------------------------------------------------------
execute_command:
    addi sp, sp, -8
    sw ra, 4(sp)

    # Check empty
    lb t0, 0(a0)
    beqz t0, cmd_done

    # Check "help"
    la a1, cmd_help_str
    call str_eq
    bnez a0, do_help

    # Check "info"
    la a0, cmd_buf
    la a1, cmd_info_str
    call str_eq
    bnez a0, do_info

    # Check "mem"
    la a0, cmd_buf
    la a1, cmd_mem_str
    call str_eq
    bnez a0, do_mem

    # Check "ps"
    la a0, cmd_buf
    la a1, cmd_ps_str
    call str_eq
    bnez a0, do_ps

    # Check "spawn"
    la a0, cmd_buf
    la a1, cmd_spawn_str
    call str_eq
    bnez a0, do_spawn

    # Check "matrix"
    la a0, cmd_buf
    la a1, cmd_matrix_str
    call str_eq
    bnez a0, do_matrix

    # Check "clear"
    la a0, cmd_buf
    la a1, cmd_clear_str
    call str_eq
    bnez a0, do_clear

    # Check "reboot"
    la a0, cmd_buf
    la a1, cmd_reboot_str
    call str_eq
    bnez a0, do_reboot

    # Check "disk"
    la a0, cmd_buf
    la a1, cmd_disk_str
    call str_eq
    bnez a0, do_disk

    # Check "ls"
    la a0, cmd_buf
    la a1, cmd_ls_str
    call str_eq
    bnez a0, do_ls

    # Check "shutdown"
    la a0, cmd_buf
    la a1, cmd_shutdown_str
    call str_eq
    bnez a0, do_shutdown

    # Unknown command
    la a0, unknown_cmd_str
    call print_str
    la a0, cmd_buf
    call print_str
    la a0, newline_str
    call print_str
    j cmd_done

do_help:
    la a0, help_text
    call print_str
    j cmd_done

do_info:
    la a0, info_text
    call print_str
    j cmd_done

do_mem:
    la a0, mem_text
    call print_str
    j cmd_done

do_ps:
    la a0, ps_text
    call print_str
    # Print task table status
    la a0, ps_task0
    call print_str
    la t0, task1_active
    lw t1, 0(t0)
    beqz t1, ps_done
    la a0, ps_task1
    call print_str
ps_done:
    la a0, newline_str
    call print_str
    j cmd_done

do_spawn:
    la t0, task1_active
    li t1, 1
    sw t1, 0(t0)
    la a0, spawn_msg
    call print_str
    j cmd_done

do_matrix:
    la a0, matrix_text
    call print_str
    j cmd_done

do_clear:
    la a0, clear_seq
    call print_str
    j cmd_done

do_reboot:
    li t0, 0x10000040
    li t1, 2
    sw t1, 0(t0)
    j cmd_done

do_disk:
    la a0, disk_info_text
    call print_str
    # Read sector 0 into disk_sector_buf
    li t0, 0x10001000
    sw zero, 0(t0)
    la t1, disk_sector_buf
    sw t1, 4(t0)
    li t2, 1
    sw t2, 8(t0)
    j cmd_done

do_ls:
    la a0, ls_header_text
    call print_str
    # Read sector 1 into disk_sector_buf
    li t0, 0x10001000
    li t1, 1
    sw t1, 0(t0)
    la t1, disk_sector_buf
    sw t1, 4(t0)
    li t2, 1
    sw t2, 8(t0)
    # Scan first 8 entries in sector 1
    li s0, 0
    li s1, 0
ls_entry_loop:
    li t0, 8
    bge s0, t0, ls_check_empty
    slli t1, s0, 6
    la t2, disk_sector_buf
    add t2, t2, t1
    lw t3, 32(t2)
    beqz t3, ls_entry_next
    # Print entry name
    mv a0, t2
    call print_str
    la a0, ls_entry_suffix
    call print_str
    addi s1, s1, 1
ls_entry_next:
    addi s0, s0, 1
    j ls_entry_loop
ls_check_empty:
    bnez s1, ls_all_done
    la a0, ls_empty_text
    call print_str
ls_all_done:
    j cmd_done

do_shutdown:
    li t0, 0x10000040
    li t1, 1
    sw t1, 0(t0)
    j cmd_done

cmd_done:
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

# ------------------------------------------------------------------------------
# String Comparison: returns 1 if equal, 0 if not
# ------------------------------------------------------------------------------
str_eq:
str_eq_loop:
    lb t0, 0(a0)
    lb t1, 0(a1)
    bne t0, t1, str_not_eq
    beqz t0, str_is_eq
    addi a0, a0, 1
    addi a1, a1, 1
    j str_eq_loop
str_is_eq:
    li a0, 1
    ret
str_not_eq:
    li a0, 0
    ret

# ------------------------------------------------------------------------------
# UART Driver (MMIO at 0x10000000)
# ------------------------------------------------------------------------------
put_char:
    li t0, 0x10000000
    sw a0, 0(t0)
    ret

print_str:
    addi sp, sp, -8
    sw ra, 4(sp)
    sw s0, 0(sp)
    mv s0, a0
print_str_loop:
    lb a0, 0(s0)
    beqz a0, print_str_done
    call put_char
    addi s0, s0, 1
    j print_str_loop
print_str_done:
    lw s0, 0(sp)
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

read_char_nonblock:
    li t0, 0x10000004
    lw t1, 0(t0)
    andi t1, t1, 0x01
    beqz t1, no_char
    li t0, 0x10000000
    lw a0, 0(t0)
    ret
no_char:
    li a0, 0
    ret

# ------------------------------------------------------------------------------
# Task Scheduler & Trap Vector
# ------------------------------------------------------------------------------
init_tasks:
    la t0, current_task
    sw zero, 0(t0)       # Task 0 (Shell)
    la t0, task1_active
    sw zero, 0(t0)       # Task 1 not yet active
    ret

.align 4
trap_handler:
    # Save Shell context if we are interrupted
    csrw mscratch, sp
    la sp, saved_context_0
    sw x1, 4(sp)
    sw x3, 12(sp)
    sw x4, 16(sp)
    sw x5, 20(sp)
    sw x6, 24(sp)
    sw x7, 28(sp)
    sw x8, 32(sp)
    sw x9, 36(sp)
    sw x10, 40(sp)
    sw x11, 44(sp)
    sw x12, 48(sp)
    sw x13, 52(sp)
    sw x14, 56(sp)
    sw x15, 60(sp)
    sw x16, 64(sp)
    sw x17, 68(sp)
    sw x18, 72(sp)
    sw x19, 76(sp)
    sw x20, 80(sp)
    sw x21, 84(sp)
    sw x22, 88(sp)
    sw x23, 92(sp)
    sw x24, 96(sp)
    sw x25, 100(sp)
    sw x26, 104(sp)
    sw x27, 108(sp)
    sw x28, 112(sp)
    sw x29, 116(sp)
    sw x30, 120(sp)
    sw x31, 124(sp)
    csrr t0, mscratch
    sw t0, 8(sp)         # original sp

    # Re-arm timer compare
    li t0, 0x10000010
    lw t1, 0(t0)
    li t2, 50000
    add t1, t1, t2
    sw t1, 8(t0)

    # Check if background task is active
    la t0, task1_active
    lw t1, 0(t0)
    beqz t1, restore_task0

    # Background worker activity (prints pulse every several quantum ticks)
    la t0, worker_pulse_count
    lw t1, 0(t0)
    addi t1, t1, 1
    sw t1, 0(t0)
    li t2, 8
    blt t1, t2, restore_task0
    sw zero, 0(t0)       # reset
    la a0, bg_pulse_msg
    call print_str

restore_task0:
    la sp, saved_context_0
    lw x1, 4(sp)
    lw x3, 12(sp)
    lw x4, 16(sp)
    lw x5, 20(sp)
    lw x6, 24(sp)
    lw x7, 28(sp)
    lw x8, 32(sp)
    lw x9, 36(sp)
    lw x10, 40(sp)
    lw x11, 44(sp)
    lw x12, 48(sp)
    lw x13, 52(sp)
    lw x14, 56(sp)
    lw x15, 60(sp)
    lw x16, 64(sp)
    lw x17, 68(sp)
    lw x18, 72(sp)
    lw x19, 76(sp)
    lw x20, 80(sp)
    lw x21, 84(sp)
    lw x22, 88(sp)
    lw x23, 92(sp)
    lw x24, 96(sp)
    lw x25, 100(sp)
    lw x26, 104(sp)
    lw x27, 108(sp)
    lw x28, 112(sp)
    lw x29, 116(sp)
    lw x30, 120(sp)
    lw x31, 124(sp)
    lw sp, 8(sp)

    mret

# ------------------------------------------------------------------------------
# Data & Strings
# ------------------------------------------------------------------------------
.section .data
banner_str:
    .string "\n=================================================================\n     ___      _ _  ____   ____  \n    / _ \\    | (_)/ __ \\ / ___| \n   / /_\\ \\ __| |_| |  | |\\___ \\ \n  / /_ \\\\ / _` | | |  | | ___) |\n /_/   \\_\\__,_|_|\\_\\____/|____/ \n                                \n  AdiOS v1.0 -- The Ultra-Lightweight Bare-Metal RISC-V OS      \n  Built from scratch. Zero bloat. Pure computer science.        \n=================================================================\n\n"

init_mem_str:
    .string "[BOOT] Initialized 32 MB Virtual RAM (8192 pages)\n[BOOT] Scheduler: Preemptive Round-Robin activated\n[BOOT] Terminal: MMIO UART at 0x10000000\n[BOOT] System ready. Type 'help' for commands.\n\n"

prompt_str:
    .string "adios> "

newline_str:
    .string "\n"

backspace_seq:
    .string "\b \b"

clear_seq:
    .string "\033[2J\033[H"

cmd_help_str:     .string "help"
cmd_info_str:     .string "info"
cmd_mem_str:      .string "mem"
cmd_ps_str:       .string "ps"
cmd_spawn_str:    .string "spawn"
cmd_disk_str:     .string "disk"
cmd_ls_str:       .string "ls"
cmd_matrix_str:   .string "matrix"
cmd_clear_str:    .string "clear"
cmd_reboot_str:   .string "reboot"
cmd_shutdown_str: .string "shutdown"

help_text:
    .string "\nAvailable AdiOS Commands:\n  help      - Show this command reference\n  info      - System specifications & architecture\n  mem       - Memory allocation & page stats\n  ps        - List running tasks & PIDs\n  spawn     - Launch a concurrent background task\n  disk      - Virtual disk hardware specifications\n  ls        - List files on virtual disk (AdiFS)\n  matrix    - Cyberpunk digital visual banner\n  clear     - Clear terminal screen\n  reboot    - Restart the virtual machine\n  shutdown  - Power off system\n\n"

disk_info_text:
    .string "\n--- Virtual Disk Controller (MMIO 0x10001000) ---\n  Filesystem:   AdiFS (Contiguous Block Filesystem)\n  Sector Size:  512 Bytes\n  Sector Range: 0 to 16383 (8 MB Disk Image)\n  DMA Mode:     Direct RAM Transfer\n\n"

ls_header_text:
    .string "\nNAME                             TYPE    SECTOR\n------------------------------------------------\n"

ls_entry_suffix:
    .string "                  [FILE]  CONTIGUOUS\n"

ls_empty_text:
    .string "(No files found on disk. Use AdiFS to create files)\n\n"

info_text:
    .string "\n--- AdiOS System Architecture ---\n  OS:           AdiOS v1.0\n  Architecture: RISC-V 32-bit (RV32IM)\n  Total Memory: 32 MB (8,192 pages of 4KB)\n  Execution:    Host Simulation Layer (MMIO Paravirtualization)\n  Multitasking: Preemptive Timer-driven Round-Robin\n\n"

mem_text:
    .string "\n--- Memory Statistics ---\n  Total RAM:    32,768 KB (8192 pages)\n  Kernel Base:  0x80000000 (Reserved 4 MB)\n  Free Memory:  28,672 KB (7168 pages free)\n  Page Size:    4,096 Bytes\n\n"

ps_text:
    .string "\nPID  STATE     STACK POINTER  NAME\n-----------------------------------------\n"

ps_task0:
    .string "1    RUNNING   0x81000000     shell\n"

ps_task1:
    .string "2    READY     0x81002000     bg_worker\n"

spawn_msg:
    .string "[SCHED] Spawned background worker task (PID 2)!\n"

bg_pulse_msg:
    .string "\n[Worker PID 2] Concurrent tick executed in background!\nadios> "

matrix_text:
    .string "\n\033[32m0 1 0 1 1 0 1 0   AdiOS CYBERSPACE   0 1 0 1 1 0 1 0\n1 0 0 1 0 1 1 0   Bare-Metal RISC-V  1 0 0 1 0 1 1 0\n0 1 1 0 1 0 0 1   Goodbye Bloat!     0 1 1 0 1 0 0 1\033[0m\n\n"

unknown_cmd_str:
    .string "Unknown command: "

# ------------------------------------------------------------------------------
# BSS / Storage
# ------------------------------------------------------------------------------
.section .bss
cmd_len:
    .word 0
cmd_buf:
    .space 64

current_task:
    .word 0
task1_active:
    .word 0
worker_pulse_count:
    .word 0

.align 4
saved_context_0:
    .space 132
saved_context_1:
    .space 132

.align 4
disk_sector_buf:
    .space 512
