#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#ifdef _WIN32
#include <conio.h>
#include <windows.h>
#else
#include <unistd.h>
#include <termios.h>
#include <fcntl.h>
#endif

#include "cpu.h"
#include "bus.h"

static uint8_t ram[RAM_SIZE];

static void check_host_input(void) {
#ifdef _WIN32
    while (_kbhit()) {
        int c = _getch();
        if (c == 3) { // Ctrl+C
            printf("\n[AdiOS VM] Interrupted by Host (Ctrl+C).\n");
            exit(0);
        }
        if (c == 13) c = 10; // Convert Enter \r to \n
        uart_push_input((uint8_t)c);
    }
#else
    // POSIX fallback
    struct timeval tv = {0, 0};
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(0, &fds);
    if (select(1, &fds, NULL, NULL, &tv) > 0) {
        char c;
        if (read(0, &c, 1) > 0) {
            uart_push_input((uint8_t)c);
        }
    }
#endif
}

int main(int argc, char *argv[]) {
    const char *bin_path = "adios.bin";
    if (argc > 1) {
        bin_path = argv[1];
    }

    FILE *f = fopen(bin_path, "rb");
    if (!f) {
        fprintf(stderr, "[AdiOS VM] Error: Could not open kernel binary '%s'\n", bin_path);
        return 1;
    }

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size > (long)RAM_SIZE) {
        fprintf(stderr, "[AdiOS VM] Error: Kernel binary is too large for 32MB RAM\n");
        fclose(f);
        return 1;
    }

    fread(ram, 1, size, f);
    fclose(f);

    printf("=====================================================\n");
    printf("        AdiOS RISC-V Hardware Simulator (RV32IM)     \n");
    printf("=====================================================\n");
    printf("[VM] Loaded %ld bytes of kernel image into 0x80000000\n", size);
    printf("[VM] Virtual RAM: %d MB | Terminal: MMIO 0x10000000\n", RAM_SIZE / (1024 * 1024));
    printf("[VM] Booting virtual machine...\n\n");

    CPU cpu;
    cpu_init(&cpu, ram);

    uint64_t step_count = 0;
    while (cpu.running) {
        if (!cpu_step(&cpu)) {
            break;
        }

        step_count++;
        if ((step_count & 0x7FF) == 0) { // Check input every 2048 instructions
            check_host_input();
        }
    }

    printf("\n[VM] Execution stopped at cycle: %llu | Final PC: 0x%08X\n", (unsigned long long)step_count, cpu.pc);
    return 0;
}
