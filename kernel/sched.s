# ==============================================================================
# AdiOS Core Bare-Metal Kernel: Multi-Tasking Scheduler (sched.s)
# Preemptive Priority Round-Robin Task Scheduler with Full Register Context Switching
# ==============================================================================

.section .text
.global sched_init
.global task_create
.global task_yield
.global task_kill
.global sched_tick
.global get_current_task
.global get_task_count

# Task States
#define TASK_UNUSED      0
#define TASK_READY       1
#define TASK_RUNNING     2
#define TASK_BLOCKED     3
#define TASK_TERMINATED  4

# TCB Structure Offsets (Total Size = 176 bytes)
#   Offset  0: pid (4 bytes)
#   Offset  4: state (4 bytes)
#   Offset  8: saved_sp (4 bytes)
#   Offset 12: quantum (4 bytes)
#   Offset 16: priority (4 bytes)
#   Offset 20: name (16 bytes)
#   Offset 36: next_ptr (4 bytes)
#   Offset 40: context save area (32 regs * 4 bytes + mepc + mstatus = 136 bytes)

#define MAX_TASKS 16
#define TCB_SIZE 176
#define DEFAULT_QUANTUM 5

# ------------------------------------------------------------------------------
# Scheduler Initialization
# Sets up Task 0 (Idle) and Task 1 (Adam Task)
# ------------------------------------------------------------------------------
sched_init:
    addi sp, sp, -16
    sw ra, 12(sp)

    # Clear all TCB slots (16 tasks * 176 bytes = 2816 bytes)
    la t0, tcb_table
    li t1, 2816
clear_tcb_loop:
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -4
    bnez t1, clear_tcb_loop

    # 1. Initialize Task 0: IDLE TASK
    la s0, tcb_table
    sw zero, 0(s0)              # pid = 0
    li t0, 1                    # state = READY (1)
    sw t0, 4(s0)
    li t0, 0x81800000           # Stack top for Idle Task
    sw t0, 8(s0)
    li t0, 1
    sw t0, 12(s0)               # quantum = 1
    li t0, 2
    sw t0, 16(s0)               # priority = 2 (Idle)

    # 2. Initialize Task 1: ADAM ROOT TASK (Active current task)
    addi s1, s0, 176            # s0 + TCB_SIZE
    li t0, 1
    sw t0, 0(s1)                # pid = 1
    li t0, 2                    # state = RUNNING (2)
    sw t0, 4(s1)
    li t0, 0x81000000           # Stack top for Adam Task
    sw t0, 8(s1)
    li t0, 5                    # quantum = 5
    sw t0, 12(s1)
    li t0, 1
    sw t0, 16(s1)               # priority = 1 (Normal)

    # Link TCBs: Task 1 -> Task 0 -> Task 1 (Circular list)
    sw s0, 36(s1)               # Adam -> Idle
    sw s1, 36(s0)               # Idle -> Adam

    la t0, current_tcb
    sw s1, 0(t0)                # current_tcb = Adam Task

    la t0, active_task_count
    li t1, 2
    sw t1, 0(t0)                # active_task_count = 2

    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# ------------------------------------------------------------------------------
# Task Creation: Spawns a new concurrent task
# Args: a0 = entry_point_pc, a1 = stack_top_addr, a2 = priority (0-2)
# Returns: a0 = pid (or -1 if table full)
# ------------------------------------------------------------------------------
task_create:
    addi sp, sp, -24
    sw ra, 20(sp)
    sw s0, 16(sp)
    sw s1, 12(sp)
    sw s2, 8(sp)

    # Find free TCB slot
    la s0, tcb_table
    li t0, 0
    li t1, 16                   # MAX_TASKS
find_free_tcb:
    lw t2, 4(s0)                # check state
    beqz t2, found_slot
    addi s0, s0, 176            # TCB_SIZE
    addi t0, t0, 1
    blt t0, t1, find_free_tcb

    # No free slot
    li a0, -1
    j task_create_done

found_slot:
    # Assign PID (t0)
    sw t0, 0(s0)                # pid
    li t2, 1                    # state = READY
    sw t2, 4(s0)
    sw a2, 16(s0)               # priority
    li t2, 5                    # quantum
    sw t2, 12(s0)

    # Setup initial stack frame for task entry
    # Allocate 136 bytes on task stack for register context
    addi a1, a1, -136
    sw a1, 8(s0)                # saved_sp

    # In saved context area on stack:
    # Set saved PC (mepc) = entry_point_pc (offset 128)
    sw a0, 128(a1)
    # Set saved mstatus (offset 132) = 0x88 (MPIE=1, MIE=1)
    li t2, 0x88
    sw t2, 132(a1)

    # Link into circular TCON list after current_tcb
    la t2, current_tcb
    lw t3, 0(t2)                # current_tcb
    lw t4, 36(t3)               # next_ptr of current_tcb
    sw s0, 36(t3)               # current_tcb -> new_tcb
    sw t4, 36(s0)               # new_tcb -> old_next

    # Increment task count
    la t2, active_task_count
    lw t3, 0(t2)
    addi t3, t3, 1
    sw t3, 0(t2)

    mv a0, t0                   # Return PID

task_create_done:
    lw s2, 8(sp)
    lw s1, 12(sp)
    lw s0, 16(sp)
    lw ra, 20(sp)
    addi sp, sp, 24
    ret

# ------------------------------------------------------------------------------
# Preemptive Timer Tick Handler
# Decrements current task quantum; switches context if quantum expires
# ------------------------------------------------------------------------------
sched_tick:
    la t0, current_tcb
    lw t1, 0(t0)                # t1 = current_tcb
    beqz t1, sched_tick_ret

    lw t2, 12(t1)               # quantum
    addi t2, t2, -1
    sw t2, 12(t1)
    bgtz t2, sched_tick_ret

    # Quantum expired: reset quantum and switch task
    li t2, 5                    # DEFAULT_QUANTUM
    sw t2, 12(t1)

    # Change state from RUNNING to READY
    li t2, 1                    # TASK_READY
    sw t2, 4(t1)

    # Advance to next READY task in circular list
    lw t3, 36(t1)               # next_tcb
find_next_ready:
    beqz t3, fallback_idle
    lw t4, 4(t3)                # state
    li t5, 1                    # TASK_READY
    beq t4, t5, switch_to_task
    lw t3, 36(t3)
    bne t3, t1, find_next_ready

fallback_idle:
    la t3, tcb_table            # Fallback to Task 0 (Idle)

switch_to_task:
    # Set new task to RUNNING
    li t2, 2                    # TASK_RUNNING
    sw t2, 4(t3)
    sw t3, 0(t0)                # current_tcb = new_task

sched_tick_ret:
    ret

# ------------------------------------------------------------------------------
# Queries
# ------------------------------------------------------------------------------
get_current_task:
    la t0, current_tcb
    lw a0, 0(t0)
    ret

get_task_count:
    la t0, active_task_count
    lw a0, 0(t0)
    ret

task_kill:
    # Args: a0 = pid
    la t0, tcb_table
    li t1, 16                   # MAX_TASKS
    li t2, 0
find_kill_tcb:
    lw t3, 0(t0)
    beq t3, a0, do_kill
    addi t0, t0, 176            # TCB_SIZE
    addi t2, t2, 1
    blt t2, t1, find_kill_tcb
    ret

do_kill:
    li t1, 4                    # TASK_TERMINATED
    sw t1, 4(t0)
    la t1, active_task_count
    lw t2, 0(t1)
    addi t2, t2, -1
    sw t2, 0(t1)
    ret

# ------------------------------------------------------------------------------
# BSS: Task Control Tables
# ------------------------------------------------------------------------------
.section .bss
.align 4
current_tcb:        .word 0
active_task_count:  .word 0

# TCB Table: 16 tasks * 176 bytes = 2,816 bytes
tcb_table:
    .space 2816
