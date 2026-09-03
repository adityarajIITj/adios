#include "kernel.h"

#define TIME_SLICE 50000 // Cycles per scheduler quantum

static task_t tasks[MAX_TASKS];
static int current_task_id = 0;
static int next_pid = 1;

void sched_init(void) {
    memset(tasks, 0, sizeof(tasks));
    
    // Task 0 is the main kernel task (Shell)
    tasks[0].pid = next_pid++;
    strcpy(tasks[0].name, "kmain");
    tasks[0].state = TASK_RUNNING;
    tasks[0].sp = 0x81000000;
    current_task_id = 0;

    // Set initial timer interrupt
    set_timer_cmp(get_time() + TIME_SLICE);
    printf("[SCHED] Round-Robin scheduler initialized. Quantum: %d cycles\n", TIME_SLICE);
}

task_t *get_current_task(void) {
    return &tasks[current_task_id];
}

task_t *get_task(int index) {
    if (index >= 0 && index < MAX_TASKS) {
        return &tasks[index];
    }
    return NULL;
}

int task_create(const char *name, void (*entry)(void)) {
    int slot = -1;
    for (int i = 1; i < MAX_TASKS; i++) {
        if (tasks[i].state == TASK_UNUSED || tasks[i].state == TASK_DEAD) {
            slot = i;
            break;
        }
    }

    if (slot == -1) {
        printf("[SCHED] Error: Task table full (max %d tasks)\n", MAX_TASKS);
        return -1;
    }

    // Allocate 2 pages (8 KB) for stack
    void *stack1 = page_alloc();
    void *stack2 = page_alloc();
    if (!stack1 || !stack2) {
        printf("[SCHED] Error: Out of memory for task stack\n");
        return -1;
    }

    uint32_t stack_top = (uint32_t)stack2 + PAGE_SIZE - 16;

    task_t *t = &tasks[slot];
    memset(t, 0, sizeof(task_t));
    t->pid = next_pid++;
    strncpy(t->name, name, 31);
    t->pc = (uint32_t)entry;
    t->sp = stack_top;
    t->state = TASK_READY;

    // Set up register context
    t->regs[1] = (uint32_t)task_exit; // Return address (ra) -> task_exit
    t->regs[2] = stack_top;           // Stack pointer (sp)

    printf("[SCHED] Created task '%s' (PID %d, Entry 0x%08X, SP 0x%08X)\n",
           name, t->pid, t->pc, t->sp);
    return t->pid;
}

void task_yield(void) {
    // Force timer match immediately to trigger context switch
    set_timer_cmp(get_time());
}

void task_exit(void) {
    task_t *t = get_current_task();
    printf("\n[SCHED] Task '%s' (PID %d) finished execution.\n", t->name, t->pid);
    t->state = TASK_DEAD;
    task_yield();
    while (1) {
        // Halt until next tick
    }
}

void schedule(trap_frame_t *tf) {
    // Save current task context
    task_t *cur = &tasks[current_task_id];
    if (cur->state == TASK_RUNNING) {
        cur->state = TASK_READY;
    }
    
    // Save registers from trap frame
    for (int i = 0; i < 32; i++) {
        cur->regs[i] = tf->regs[i];
    }
    cur->pc = tf->pc;

    // Find next ready task (Round-Robin)
    int next = current_task_id;
    for (int i = 0; i < MAX_TASKS; i++) {
        next = (next + 1) % MAX_TASKS;
        if (tasks[next].state == TASK_READY || tasks[next].state == TASK_RUNNING) {
            break;
        }
    }

    current_task_id = next;
    task_t *next_task = &tasks[current_task_id];
    next_task->state = TASK_RUNNING;

    // Restore registers into trap frame
    for (int i = 0; i < 32; i++) {
        tf->regs[i] = next_task->regs[i];
    }
    tf->pc = next_task->pc;

    // Re-arm timer compare for next quantum
    set_timer_cmp(get_time() + TIME_SLICE);
}
