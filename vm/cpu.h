#ifndef ADIOS_CPU_H
#define ADIOS_CPU_H

#include <stdint.h>
#include <stdbool.h>

#define RAM_SIZE (32 * 1024 * 1024) // 32 MB
#define RAM_BASE 0x80000000

// MMIO Addresses
#define UART_BASE   0x10000000
#define UART_DATA   0x10000000
#define UART_STATUS 0x10000004

#define TIMER_BASE  0x10000010
#define TIMER_TIME  0x10000010
#define TIMER_TIMECMP 0x10000018

#define POWER_BASE  0x10000040

// Machine-mode CSRs
#define CSR_MSTATUS 0x300
#define CSR_MIE     0x304
#define CSR_MTVEC   0x305
#define CSR_MEPC    0x341
#define CSR_MCAUSE  0x342
#define CSR_MIP     0x344

// Causes
#define CAUSE_TIMER_INT   0x80000007
#define CAUSE_USER_ECALL  8
#define CAUSE_MACH_ECALL  11

typedef struct {
    uint32_t regs[32];
    uint32_t pc;
    
    // CSRs
    uint32_t mstatus;
    uint32_t mtvec;
    uint32_t mepc;
    uint32_t mcause;
    uint32_t mie;
    uint32_t mip;

    uint8_t *ram;
    uint64_t timer_time;
    uint64_t timer_cmp;
    
    bool running;
    bool timer_irq_pending;
} CPU;

void cpu_init(CPU *cpu, uint8_t *ram);
bool cpu_step(CPU *cpu);
void cpu_raise_trap(CPU *cpu, uint32_t cause, uint32_t epc);
void cpu_check_interrupts(CPU *cpu);

#endif
