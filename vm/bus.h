#ifndef ADIOS_BUS_H
#define ADIOS_BUS_H

#include "cpu.h"
#include <stdint.h>
#include <stdbool.h>

uint32_t bus_read8(CPU *cpu, uint32_t addr);
uint32_t bus_read16(CPU *cpu, uint32_t addr);
uint32_t bus_read32(CPU *cpu, uint32_t addr);

void bus_write8(CPU *cpu, uint32_t addr, uint32_t val);
void bus_write16(CPU *cpu, uint32_t addr, uint32_t val);
void bus_write32(CPU *cpu, uint32_t addr, uint32_t val);

// UART I/O Buffer
void uart_push_input(uint8_t c);
bool uart_has_input(void);
uint8_t uart_pop_input(void);

#endif
