#include "kernel.h"

void handle_trap(trap_frame_t *tf) {
    uint32_t mcause;
    asm volatile("csrr %0, mcause" : "=r"(mcause));

    if (mcause == 0x80000007) { // Machine Timer Interrupt
        schedule(tf);
    } else if (mcause == 11) { // Machine ECALL (Syscall)
        tf->pc += 4; // Advance past ecall instruction
        // Syscall dispatching if needed
    } else {
        printf("\n[KERNEL PANIC] Unhandled trap! mcause: 0x%08X, mepc: 0x%08X\n", mcause, tf->pc);
        while (1) {
            // Halt on crash
        }
    }
}

void kmain(void) {
    printf("\n");
    printf("=================================================================\n");
    printf("     ___      _ _  ____   ____  \n");
    printf("    / _ \\    | (_)/ __ \\ / ___| \n");
    printf("   / /_\\ \\ __| |_| |  | |\\___ \\ \n");
    printf("  / /_ \\\\ / _` | | |  | | ___) |\n");
    printf(" /_/   \\_\\__,_|_|\\_\\____/|____/ \n");
    printf("                                \n");
    printf("  AdiOS v1.0 -- The Ultra-Lightweight Bare-Metal RISC-V OS      \n");
    printf("  Built from scratch. Zero bloat. Pure computer science.        \n");
    printf("=================================================================\n\n");

    printf("[BOOT] Initializing AdiOS Kernel Subsystems...\n");

    // 1. Initialize Memory Manager
    mem_init();

    // 2. Initialize Scheduler
    sched_init();

    // 3. Initialize Interactive Shell
    printf("[BOOT] Starting User Shell...\n");
    shell_init();

    // 4. Enable Global Interrupts in mstatus (MIE bit 3)
    uint32_t mstatus;
    asm volatile("csrr %0, mstatus" : "=r"(mstatus));
    mstatus |= (1 << 3); // MIE
    asm volatile("csrw mstatus, %0" :: "r"(mstatus));

    printf("\n[BOOT] System ready. Type 'help' to view available commands.\n\n");

    // 5. Main Shell Loop
    while (1) {
        shell_step();
    }
}
