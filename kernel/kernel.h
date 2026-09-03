#ifndef ADIOS_KERNEL_H
#define ADIOS_KERNEL_H

typedef unsigned int   uint32_t;
typedef int            int32_t;
typedef unsigned short uint16_t;
typedef short          int16_t;
typedef unsigned char  uint8_t;
typedef char           int8_t;
typedef unsigned int   size_t;

#define bool  _Bool
#define true  1
#define false 0
#define NULL  ((void*)0)

// Memory Map
#define RAM_BASE       0x80000000
#define RAM_SIZE       (32 * 1024 * 1024)
#define PAGE_SIZE      4096
#define STACK_SIZE     8192

// MMIO Ports
#define UART_DATA      ((volatile uint32_t*)0x10000000)
#define UART_STATUS    ((volatile uint32_t*)0x10000004)
#define TIMER_TIME     ((volatile uint32_t*)0x10000010)
#define TIMER_TIMECMP  ((volatile uint32_t*)0x10000018)
#define POWER_REG      ((volatile uint32_t*)0x10000040)

// Task States
#define TASK_UNUSED   0
#define TASK_READY    1
#define TASK_RUNNING  2
#define TASK_SLEEPING 3
#define TASK_DEAD     4

#define MAX_TASKS 16

typedef struct {
    uint32_t regs[32]; // x0-x31 (saved context)
    uint32_t pc;
    uint32_t sp;
    int pid;
    char name[32];
    int state;
    uint32_t sleep_until;
} task_t;

// Context Frame passed during trap
typedef struct {
    uint32_t regs[32];
    uint32_t pc;
} trap_frame_t;

// Drivers
void uart_putc(char c);
void uart_puts(const char *s);
bool uart_has_char(void);
char uart_getc(void);
void printf(const char *fmt, ...);

// Memory Manager
void mem_init(void);
void *page_alloc(void);
void page_free(void *ptr);
void *kmalloc(size_t size);
void kfree(void *ptr);
void mem_stats(uint32_t *total_pages, uint32_t *free_pages, uint32_t *heap_used);

// Task Scheduler
void sched_init(void);
int task_create(const char *name, void (*entry)(void));
void task_yield(void);
void task_exit(void);
void task_sleep(uint32_t ticks);
void schedule(trap_frame_t *tf);
task_t *get_current_task(void);
task_t *get_task(int index);

// Shell
void shell_init(void);
void shell_step(void);

// Utilities
size_t strlen(const char *s);
int strcmp(const char *s1, const char *s2);
int strncmp(const char *s1, const char *s2, size_t n);
char *strcpy(char *dest, const char *src);
void *memset(void *s, int c, size_t n);
void *memcpy(void *dest, const void *src, size_t n);
int atoi(const char *s);

// Hardware Helpers
static inline void poweroff(void) {
    *POWER_REG = 1;
}

static inline void reboot(void) {
    *POWER_REG = 2;
}

static inline uint32_t get_time(void) {
    return *TIMER_TIME;
}

static inline void set_timer_cmp(uint32_t ticks) {
    *TIMER_TIMECMP = ticks;
}

#endif
