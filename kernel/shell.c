#include "kernel.h"

#define LINE_BUF_SIZE 128
static char line_buf[LINE_BUF_SIZE];
static int line_idx = 0;

// Background worker tasks demonstrating multitasking
static void worker_counter(void) {
    for (int i = 1; i <= 5; i++) {
        // Sleep / waste some cycles
        for (volatile int d = 0; d < 200000; d++);
        printf("\n[Background Task 1] Working... Count: %d/5\nadios> ", i);
    }
    printf("\n[Background Task 1] Work completed!\nadios> ");
}

static void worker_prime(void) {
    int primes_found = 0;
    for (int num = 2; primes_found < 6; num++) {
        bool is_prime = true;
        for (int d = 2; d * d <= num; d++) {
            if (num % d == 0) {
                is_prime = false;
                break;
            }
        }
        if (is_prime) {
            primes_found++;
            for (volatile int w = 0; w < 150000; w++);
            printf("\n[Prime Finder] Found prime #%d: %d\nadios> ", primes_found, num);
        }
    }
}

static void cmd_help(void) {
    printf("\nAvailable AdiOS Commands:\n");
    printf("  help            - Show this command reference\n");
    printf("  info            - System specifications and architecture\n");
    printf("  mem             - Memory statistics (Pages, RAM, Heap)\n");
    printf("  ps              - List running processes & task states\n");
    printf("  spawn counter   - Launch background counter task\n");
    printf("  spawn prime     - Launch background prime-number calculator\n");
    printf("  kill <pid>      - Terminate a running task\n");
    printf("  matrix          - Visual ASCII demo\n");
    printf("  clear           - Clear terminal display\n");
    printf("  reboot          - Restart the virtual machine\n");
    printf("  shutdown        - Power off the system\n\n");
}

static void cmd_info(void) {
    printf("\n--- AdiOS System Information ---\n");
    printf("  OS:           AdiOS v1.0 (Zero-Bloat Lightweight OS)\n");
    printf("  Architecture: RISC-V 32-bit (RV32IM Standard)\n");
    printf("  Total RAM:    %d MB (32,768 KB)\n", RAM_SIZE / (1024 * 1024));
    printf("  Page Size:    %d Bytes\n", PAGE_SIZE);
    printf("  Scheduler:    Preemptive Round-Robin\n");
    printf("  Terminal:     Memory-Mapped UART (0x10000000)\n\n");
}

static void cmd_mem(void) {
    uint32_t total, free_p, heap_used;
    mem_stats(&total, &free_p, &heap_used);

    printf("\n--- Memory Allocation Statistics ---\n");
    printf("  Total Physical Pages: %d (%d KB)\n", total, (total * PAGE_SIZE) / 1024);
    printf("  Free Pages:           %d (%d KB)\n", free_p, (free_p * PAGE_SIZE) / 1024);
    printf("  Allocated Pages:      %d (%d KB)\n", total - free_p, ((total - free_p) * PAGE_SIZE) / 1024);
    printf("  Kernel Heap Used:     %d Bytes\n\n", heap_used);
}

static void cmd_ps(void) {
    printf("\nPID  STATE     STACK POINTER  NAME\n");
    printf("-----------------------------------------\n");
    const char *state_names[] = {"UNUSED", "READY", "RUNNING", "SLEEP", "DEAD"};

    for (int i = 0; i < MAX_TASKS; i++) {
        task_t *t = get_task(i);
        if (t && t->state != TASK_UNUSED) {
            printf("%-4d %-9s 0x%08X     %s\n",
                   t->pid,
                   state_names[t->state],
                   t->sp,
                   t->name);
        }
    }
    printf("\n");
}

static void cmd_spawn(const char *arg) {
    if (strcmp(arg, "counter") == 0) {
        int pid = task_create("worker_counter", worker_counter);
        if (pid > 0) printf("Spawned counter worker with PID %d\n", pid);
    } else if (strcmp(arg, "prime") == 0) {
        int pid = task_create("worker_prime", worker_prime);
        if (pid > 0) printf("Spawned prime finder with PID %d\n", pid);
    } else {
        printf("Unknown task. Try: 'spawn counter' or 'spawn prime'\n");
    }
}

static void cmd_kill(int pid) {
    for (int i = 1; i < MAX_TASKS; i++) {
        task_t *t = get_task(i);
        if (t && t->pid == pid && t->state != TASK_DEAD) {
            t->state = TASK_DEAD;
            printf("Terminated process with PID %d (%s)\n", pid, t->name);
            return;
        }
    }
    printf("Error: No active process with PID %d\n", pid);
}

static void cmd_matrix(void) {
    printf("\033[32m"); // Green color
    printf("0 1 0 1 1 0 1 0   AdiOS CYBERSPACE   0 1 0 1 1 0 1 0\n");
    printf("1 0 0 1 0 1 1 0   Bare-Metal RISC-V  1 0 0 1 0 1 1 0\n");
    printf("0 1 1 0 1 0 0 1   Goodbye Bloat!     0 1 1 0 1 0 0 1\n");
    printf("\033[0m\n"); // Reset color
}

static void handle_command(char *cmd) {
    // Strip leading whitespace
    while (*cmd == ' ') cmd++;
    if (*cmd == '\0') return;

    if (strcmp(cmd, "help") == 0) {
        cmd_help();
    } else if (strcmp(cmd, "info") == 0) {
        cmd_info();
    } else if (strcmp(cmd, "mem") == 0) {
        cmd_mem();
    } else if (strcmp(cmd, "ps") == 0) {
        cmd_ps();
    } else if (strncmp(cmd, "spawn ", 6) == 0) {
        cmd_spawn(cmd + 6);
    } else if (strncmp(cmd, "kill ", 5) == 0) {
        cmd_kill(atoi(cmd + 5));
    } else if (strcmp(cmd, "matrix") == 0) {
        cmd_matrix();
    } else if (strcmp(cmd, "clear") == 0) {
        printf("\033[2J\033[H");
    } else if (strcmp(cmd, "reboot") == 0) {
        reboot();
    } else if (strcmp(cmd, "shutdown") == 0) {
        poweroff();
    } else {
        printf("Unknown command: '%s'. Type 'help' for commands.\n", cmd);
    }
}

void shell_init(void) {
    line_idx = 0;
    line_buf[0] = '\0';
    printf("adios> ");
}

void shell_step(void) {
    if (uart_has_char()) {
        char c = uart_getc();

        if (c == '\r' || c == '\n') {
            uart_putc('\n');
            line_buf[line_idx] = '\0';
            handle_command(line_buf);
            line_idx = 0;
            line_buf[0] = '\0';
            printf("adios> ");
        } else if (c == 0x08 || c == 0x7F) { // Backspace
            if (line_idx > 0) {
                line_idx--;
                uart_puts("\b \b");
            }
        } else if (c >= 32 && c <= 126) {
            if (line_idx < LINE_BUF_SIZE - 1) {
                line_buf[line_idx++] = c;
                uart_putc(c); // Echo
            }
        }
    }
}
