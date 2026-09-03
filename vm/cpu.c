#include "cpu.h"
#include "bus.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void cpu_init(CPU *cpu, uint8_t *ram) {
    memset(cpu, 0, sizeof(CPU));
    cpu->ram = ram;
    cpu->pc = RAM_BASE;
    cpu->running = true;
    cpu->mstatus = 0;
    cpu->timer_cmp = 0xFFFFFFFFFFFFFFFFULL;
}

static inline int32_t sign_extend(uint32_t val, int bits) {
    int32_t m = 1U << (bits - 1);
    return (val ^ m) - m;
}

static uint32_t csr_read(CPU *cpu, uint32_t csr) {
    switch (csr) {
        case CSR_MSTATUS: return cpu->mstatus;
        case CSR_MIE:     return cpu->mie;
        case CSR_MTVEC:   return cpu->mtvec;
        case CSR_MEPC:    return cpu->mepc;
        case CSR_MCAUSE:  return cpu->mcause;
        case CSR_MIP:     return cpu->mip;
        default: return 0;
    }
}

static void csr_write(CPU *cpu, uint32_t csr, uint32_t val) {
    switch (csr) {
        case CSR_MSTATUS: cpu->mstatus = val; break;
        case CSR_MIE:     cpu->mie = val; break;
        case CSR_MTVEC:   cpu->mtvec = val; break;
        case CSR_MEPC:    cpu->mepc = val; break;
        case CSR_MCAUSE:  cpu->mcause = val; break;
        case CSR_MIP:     cpu->mip = val; break;
        default: break;
    }
}

void cpu_raise_trap(CPU *cpu, uint32_t cause, uint32_t epc) {
    cpu->mepc = epc;
    cpu->mcause = cause;
    
    // Save MIE into MPIE (bit 7 into bit 3) and clear MIE
    bool mie_bit = (cpu->mstatus & (1 << 3)) != 0;
    cpu->mstatus &= ~(1 << 3); // Disable MIE
    if (mie_bit) {
        cpu->mstatus |= (1 << 7); // MPIE = 1
    } else {
        cpu->mstatus &= ~(1 << 7);
    }
    
    // Vector jump
    cpu->pc = cpu->mtvec;
}

void cpu_check_interrupts(CPU *cpu) {
    // Check Machine Timer Interrupt
    bool mstatus_mie = (cpu->mstatus & (1 << 3)) != 0;
    bool mie_mtie    = (cpu->mie & (1 << 7)) != 0;

    if (cpu->timer_time >= cpu->timer_cmp) {
        cpu->mip |= (1 << 7); // Set MTIP
    } else {
        cpu->mip &= ~(1 << 7);
    }

    if (mstatus_mie && mie_mtie && (cpu->mip & (1 << 7))) {
        cpu_raise_trap(cpu, CAUSE_TIMER_INT, cpu->pc);
    }
}

bool cpu_step(CPU *cpu) {
    if (!cpu->running) return false;

    // Check interrupts
    cpu->timer_time++;
    cpu_check_interrupts(cpu);

    // Fetch
    uint32_t inst = bus_read32(cpu, cpu->pc);
    uint32_t pc = cpu->pc;
    cpu->pc += 4;

    uint32_t opcode = inst & 0x7F;
    uint32_t rd     = (inst >> 7) & 0x1F;
    uint32_t funct3 = (inst >> 12) & 0x07;
    uint32_t rs1    = (inst >> 15) & 0x1F;
    uint32_t rs2    = (inst >> 20) & 0x1F;
    uint32_t funct7 = (inst >> 25) & 0x7F;

    uint32_t *r = cpu->regs;

    switch (opcode) {
        case 0x37: // LUI
            r[rd] = inst & 0xFFFFF000;
            break;

        case 0x17: // AUIPC
            r[rd] = pc + (inst & 0xFFFFF000);
            break;

        case 0x6F: { // JAL
            int32_t imm = sign_extend(
                ((inst >> 31) << 20) |
                (((inst >> 21) & 0x3FF) << 1) |
                (((inst >> 20) & 0x1) << 11) |
                (((inst >> 12) & 0xFF) << 12), 21);
            if (rd != 0) r[rd] = cpu->pc;
            cpu->pc = pc + imm;
            break;
        }

        case 0x67: { // JALR
            int32_t imm = sign_extend(inst >> 20, 12);
            uint32_t target = (r[rs1] + imm) & ~1;
            if (rd != 0) r[rd] = cpu->pc;
            cpu->pc = target;
            break;
        }

        case 0x63: { // Branch
            int32_t imm = sign_extend(
                ((inst >> 31) << 12) |
                (((inst >> 25) & 0x3F) << 5) |
                (((inst >> 8) & 0x0F) << 1) |
                (((inst >> 7) & 0x01) << 11), 13);
            bool take = false;
            switch (funct3) {
                case 0x0: take = (r[rs1] == r[rs2]); break; // BEQ
                case 0x1: take = (r[rs1] != r[rs2]); break; // BNE
                case 0x4: take = ((int32_t)r[rs1] < (int32_t)r[rs2]); break; // BLT
                case 0x5: take = ((int32_t)r[rs1] >= (int32_t)r[rs2]); break; // BGE
                case 0x6: take = (r[rs1] < r[rs2]); break; // BLTU
                case 0x7: take = (r[rs1] >= r[rs2]); break; // BGEU
            }
            if (take) cpu->pc = pc + imm;
            break;
        }

        case 0x03: { // Load
            int32_t imm = sign_extend(inst >> 20, 12);
            uint32_t addr = r[rs1] + imm;
            switch (funct3) {
                case 0x0: r[rd] = (int32_t)(int8_t)bus_read8(cpu, addr); break; // LB
                case 0x1: r[rd] = (int32_t)(int16_t)bus_read16(cpu, addr); break; // LH
                case 0x2: r[rd] = bus_read32(cpu, addr); break; // LW
                case 0x4: r[rd] = bus_read8(cpu, addr); break; // LBU
                case 0x5: r[rd] = bus_read16(cpu, addr); break; // LHU
            }
            break;
        }

        case 0x23: { // Store
            int32_t imm = sign_extend(((inst >> 25) << 5) | ((inst >> 7) & 0x1F), 12);
            uint32_t addr = r[rs1] + imm;
            switch (funct3) {
                case 0x0: bus_write8(cpu, addr, r[rs2]); break; // SB
                case 0x1: bus_write16(cpu, addr, r[rs2]); break; // SH
                case 0x2: bus_write32(cpu, addr, r[rs2]); break; // SW
            }
            break;
        }

        case 0x13: { // ALU Immediate
            int32_t imm = sign_extend(inst >> 20, 12);
            uint32_t shamt = (inst >> 20) & 0x1F;
            switch (funct3) {
                case 0x0: r[rd] = r[rs1] + imm; break; // ADDI
                case 0x2: r[rd] = ((int32_t)r[rs1] < imm) ? 1 : 0; break; // SLTI
                case 0x3: r[rd] = (r[rs1] < (uint32_t)imm) ? 1 : 0; break; // SLTIU
                case 0x4: r[rd] = r[rs1] ^ imm; break; // XORI
                case 0x6: r[rd] = r[rs1] | imm; break; // ORI
                case 0x7: r[rd] = r[rs1] & imm; break; // ANDI
                case 0x1: r[rd] = r[rs1] << shamt; break; // SLLI
                case 0x5: // SRLI / SRAI
                    if (funct7 & 0x20) {
                        r[rd] = (int32_t)r[rs1] >> shamt; // SRAI
                    } else {
                        r[rd] = r[rs1] >> shamt; // SRLI
                    }
                    break;
            }
            break;
        }

        case 0x33: { // ALU Register-Register
            if (funct7 == 0x01) { // RV32M Extension (Multiply & Divide)
                switch (funct3) {
                    case 0x0: r[rd] = (uint32_t)((int32_t)r[rs1] * (int32_t)r[rs2]); break; // MUL
                    case 0x1: { // MULH
                        int64_t res = (int64_t)(int32_t)r[rs1] * (int64_t)(int32_t)r[rs2];
                        r[rd] = (uint32_t)(res >> 32);
                        break;
                    }
                    case 0x2: { // MULHSU
                        int64_t res = (int64_t)(int32_t)r[rs1] * (uint64_t)r[rs2];
                        r[rd] = (uint32_t)(res >> 32);
                        break;
                    }
                    case 0x3: { // MULHU
                        uint64_t res = (uint64_t)r[rs1] * (uint64_t)r[rs2];
                        r[rd] = (uint32_t)(res >> 32);
                        break;
                    }
                    case 0x4: { // DIV
                        if (r[rs2] == 0) r[rd] = 0xFFFFFFFF;
                        else if (r[rs1] == 0x80000000 && (int32_t)r[rs2] == -1) r[rd] = 0x80000000;
                        else r[rd] = (int32_t)r[rs1] / (int32_t)r[rs2];
                        break;
                    }
                    case 0x5: // DIVU
                        r[rd] = (r[rs2] == 0) ? 0xFFFFFFFF : r[rs1] / r[rs2];
                        break;
                    case 0x6: // REM
                        if (r[rs2] == 0) r[rd] = r[rs1];
                        else if (r[rs1] == 0x80000000 && (int32_t)r[rs2] == -1) r[rd] = 0;
                        else r[rd] = (int32_t)r[rs1] % (int32_t)r[rs2];
                        break;
                    case 0x7: // REMU
                        r[rd] = (r[rs2] == 0) ? r[rs1] : r[rs1] % r[rs2];
                        break;
                }
            } else { // Standard RV32I ALU
                uint32_t shamt = r[rs2] & 0x1F;
                switch (funct3) {
                    case 0x0:
                        if (funct7 & 0x20) r[rd] = r[rs1] - r[rs2]; // SUB
                        else r[rd] = r[rs1] + r[rs2]; // ADD
                        break;
                    case 0x1: r[rd] = r[rs1] << shamt; break; // SLL
                    case 0x2: r[rd] = ((int32_t)r[rs1] < (int32_t)r[rs2]) ? 1 : 0; break; // SLT
                    case 0x3: r[rd] = (r[rs1] < r[rs2]) ? 1 : 0; break; // SLTU
                    case 0x4: r[rd] = r[rs1] ^ r[rs2]; break; // XOR
                    case 0x5:
                        if (funct7 & 0x20) r[rd] = (int32_t)r[rs1] >> shamt; // SRA
                        else r[rd] = r[rs1] >> shamt; // SRL
                        break;
                    case 0x6: r[rd] = r[rs1] | r[rs2]; break; // OR
                    case 0x7: r[rd] = r[rs1] & r[rs2]; break; // AND
                }
            }
            break;
        }

        case 0x73: { // System & CSR
            uint32_t csr_addr = inst >> 20;
            if (funct3 == 0x0) {
                if (inst == 0x00000073) { // ECALL
                    cpu_raise_trap(cpu, CAUSE_MACH_ECALL, pc);
                } else if (inst == 0x00100073) { // EBREAK
                    cpu_raise_trap(cpu, 3, pc);
                } else if (inst == 0x30200073) { // MRET
                    cpu->pc = cpu->mepc;
                    // Restore MIE from MPIE
                    bool mpie_bit = (cpu->mstatus & (1 << 7)) != 0;
                    if (mpie_bit) cpu->mstatus |= (1 << 3);
                    else cpu->mstatus &= ~(1 << 3);
                    cpu->mstatus |= (1 << 7); // MPIE = 1
                } else if (inst == 0x10500073) { // WFI (Wait for Interrupt)
                    // No-op in single-core emulator
                }
            } else { // CSR operations
                uint32_t old_val = csr_read(cpu, csr_addr);
                uint32_t zimm = rs1; // For immediate forms
                uint32_t wval = (funct3 & 0x4) ? zimm : r[rs1];

                switch (funct3 & 0x3) {
                    case 0x1: // CSRRW / CSRRWI
                        csr_write(cpu, csr_addr, wval);
                        break;
                    case 0x2: // CSRRS / CSRRSI
                        csr_write(cpu, csr_addr, old_val | wval);
                        break;
                    case 0x3: // CSRRC / CSRRCI
                        csr_write(cpu, csr_addr, old_val & ~wval);
                        break;
                }
                if (rd != 0) r[rd] = old_val;
            }
            break;
        }

        default:
            printf("[AdiOS VM] Unknown instruction: 0x%08X at PC: 0x%08X\n", inst, pc);
            cpu->running = false;
            return false;
    }

    r[0] = 0; // x0 is always 0
    return true;
}
