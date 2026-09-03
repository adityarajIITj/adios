#include "bus.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define UART_BUF_SIZE 256
static uint8_t uart_rx_buf[UART_BUF_SIZE];
static int uart_rx_head = 0;
static int uart_rx_tail = 0;

void uart_push_input(uint8_t c) {
    int next = (uart_rx_head + 1) % UART_BUF_SIZE;
    if (next != uart_rx_tail) {
        uart_rx_buf[uart_rx_head] = c;
        uart_rx_head = next;
    }
}

bool uart_has_input(void) {
    return uart_rx_head != uart_rx_tail;
}

uint8_t uart_pop_input(void) {
    if (uart_rx_head == uart_rx_tail) return 0;
    uint8_t c = uart_rx_buf[uart_rx_tail];
    uart_rx_tail = (uart_rx_tail + 1) % UART_BUF_SIZE;
    return c;
}

uint32_t bus_read8(CPU *cpu, uint32_t addr) {
    if (addr >= RAM_BASE && addr < RAM_BASE + RAM_SIZE) {
        return cpu->ram[addr - RAM_BASE];
    }
    if (addr == UART_DATA) {
        return uart_pop_input();
    }
    if (addr == UART_STATUS) {
        uint32_t status = 0x02; // Tx always ready
        if (uart_has_input()) status |= 0x01; // Rx ready
        return status;
    }
    return 0;
}

uint32_t bus_read16(CPU *cpu, uint32_t addr) {
    uint32_t b0 = bus_read8(cpu, addr);
    uint32_t b1 = bus_read8(cpu, addr + 1);
    return b0 | (b1 << 8);
}

uint32_t bus_read32(CPU *cpu, uint32_t addr) {
    if (addr >= RAM_BASE && addr + 3 < RAM_BASE + RAM_SIZE) {
        uint8_t *p = &cpu->ram[addr - RAM_BASE];
        return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    }
    if (addr == UART_DATA) {
        return uart_pop_input();
    }
    if (addr == UART_STATUS) {
        uint32_t status = 0x02;
        if (uart_has_input()) status |= 0x01;
        return status;
    }
    if (addr == TIMER_TIME) {
        return (uint32_t)(cpu->timer_time & 0xFFFFFFFF);
    }
    if (addr == TIMER_TIME + 4) {
        return (uint32_t)(cpu->timer_time >> 32);
    }
    if (addr == TIMER_TIMECMP) {
        return (uint32_t)(cpu->timer_cmp & 0xFFFFFFFF);
    }
    if (addr == TIMER_TIMECMP + 4) {
        return (uint32_t)(cpu->timer_cmp >> 32);
    }
    return 0;
}

void bus_write8(CPU *cpu, uint32_t addr, uint32_t val) {
    if (addr >= RAM_BASE && addr < RAM_BASE + RAM_SIZE) {
        cpu->ram[addr - RAM_BASE] = (uint8_t)val;
        return;
    }
    if (addr == UART_DATA) {
        putchar((char)val);
        fflush(stdout);
        return;
    }
    if (addr == POWER_BASE) {
        if (val == 1) { // Poweroff
            printf("\n[AdiOS VM] Poweroff signal received. Shutting down.\n");
            cpu->running = false;
        } else if (val == 2) { // Reboot
            printf("\n[AdiOS VM] Rebooting...\n");
            cpu->pc = RAM_BASE;
        }
        return;
    }
}

void bus_write16(CPU *cpu, uint32_t addr, uint32_t val) {
    bus_write8(cpu, addr, val & 0xFF);
    bus_write8(cpu, addr + 1, (val >> 8) & 0xFF);
}

void bus_write32(CPU *cpu, uint32_t addr, uint32_t val) {
    if (addr >= RAM_BASE && addr + 3 < RAM_BASE + RAM_SIZE) {
        uint8_t *p = &cpu->ram[addr - RAM_BASE];
        p[0] = (uint8_t)(val & 0xFF);
        p[1] = (uint8_t)((val >> 8) & 0xFF);
        p[2] = (uint8_t)((val >> 16) & 0xFF);
        p[3] = (uint8_t)((val >> 24) & 0xFF);
        return;
    }
    if (addr == UART_DATA) {
        putchar((char)(val & 0xFF));
        fflush(stdout);
        return;
    }
    if (addr == TIMER_TIME) {
        cpu->timer_time = (cpu->timer_time & 0xFFFFFFFF00000000ULL) | (uint32_t)val;
        return;
    }
    if (addr == TIMER_TIME + 4) {
        cpu->timer_time = (cpu->timer_time & 0x00000000FFFFFFFFULL) | ((uint64_t)val << 32);
        return;
    }
    if (addr == TIMER_TIMECMP) {
        cpu->timer_cmp = (cpu->timer_cmp & 0xFFFFFFFF00000000ULL) | (uint32_t)val;
        return;
    }
    if (addr == TIMER_TIMECMP + 4) {
        cpu->timer_cmp = (cpu->timer_cmp & 0x00000000FFFFFFFFULL) | ((uint64_t)val << 32);
        return;
    }
    if (addr == POWER_BASE) {
        bus_write8(cpu, addr, val & 0xFF);
        return;
    }
}
