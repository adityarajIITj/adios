# AdiOS Bare-Metal Kernel: System Call Trap Entry & Signal Trampoline (syscall_entry.s)
# Handles RISC-V ecall instructions and sigreturn userland return frames.

.global syscall_trap_handler
.global sigreturn_trampoline
.global test_user_process

.section .text

# -----------------------------------------------------------------------------
# System Call Trap Handler
# Called when an ecall instruction is executed in User Mode (U-Mode) or Machine Mode (M-Mode)
# Input:
#   a7 = Syscall Number
#   a0 - a5 = Arguments
# Output:
#   a0 = Return code
# -----------------------------------------------------------------------------
syscall_trap_handler:
    # Save caller-saved registers on stack frame
    addi sp, sp, -64
    sw   ra, 0(sp)
    sw   t0, 4(sp)
    sw   t1, 8(sp)
    sw   t2, 12(sp)
    sw   t3, 16(sp)
    sw   t4, 20(sp)
    sw   t5, 24(sp)
    sw   t6, 28(sp)
    sw   a1, 32(sp)
    sw   a2, 36(sp)
    sw   a3, 40(sp)
    sw   a4, 44(sp)
    sw   a5, 48(sp)

    # Check if syscall number is SYS_GETPID (20)
    li   t0, 20
    beq  a7, t0, handle_sys_getpid

    # Check if syscall number is SYS_YIELD (124)
    li   t0, 124
    beq  a7, t0, handle_sys_yield

    # Check if syscall number is SYS_EXIT (1)
    li   t0, 1
    beq  a7, t0, handle_sys_exit

    # Default: Unknown syscall returns -22 (-EINVAL)
    li   a0, -22
    j    syscall_return

handle_sys_getpid:
    # Return simulated PID 100
    li   a0, 100
    j    syscall_return

handle_sys_yield:
    li   a0, 0
    j    syscall_return

handle_sys_exit:
    # Exit returns status in a0
    j    syscall_return

syscall_return:
    # Restore caller-saved registers
    lw   ra, 0(sp)
    lw   t0, 4(sp)
    lw   t1, 8(sp)
    lw   t2, 12(sp)
    lw   t3, 16(sp)
    lw   t4, 20(sp)
    lw   t5, 24(sp)
    lw   t6, 28(sp)
    lw   a1, 32(sp)
    lw   a2, 36(sp)
    lw   a3, 40(sp)
    lw   a4, 44(sp)
    lw   a5, 48(sp)
    addi sp, sp, 64
    ret

# -----------------------------------------------------------------------------
# Signal Return Trampoline (sigreturn_trampoline)
# Positioned in user address space so user signal handlers return here.
# Invokes SYS_SIGRETURN (119) via ecall.
# -----------------------------------------------------------------------------
sigreturn_trampoline:
    li   a7, 119       # SYS_SIGRETURN
    ecall
sigreturn_loop:
    j    sigreturn_loop

# -----------------------------------------------------------------------------
# Test Userland Process executing ecall syscalls
# -----------------------------------------------------------------------------
test_user_process:
    addi sp, sp, -16
    sw   ra, 0(sp)

    # 1. Call SYS_GETPID (20)
    li   a7, 20
    call syscall_trap_handler
    # Verify return PID == 100
    li   t0, 100
    bne  a0, t0, test_fail

    # 2. Call SYS_YIELD (124)
    li   a7, 124
    call syscall_trap_handler
    bnez a0, test_fail

    # 3. Call SYS_EXIT (1) with exit code 0
    li   a7, 1
    li   a0, 0
    call syscall_trap_handler
    bnez a0, test_fail

    # Success: return 1 in a0
    li   a0, 1
    lw   ra, 0(sp)
    addi sp, sp, 16
    ret

test_fail:
    li   a0, 0
    lw   ra, 0(sp)
    addi sp, sp, 16
    ret
