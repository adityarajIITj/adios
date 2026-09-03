#include "kernel.h"

#define TOTAL_PAGES (RAM_SIZE / PAGE_SIZE) // 8192 pages
#define BITMAP_WORDS (TOTAL_PAGES / 32)    // 256 words

static uint32_t page_bitmap[BITMAP_WORDS];
static uint32_t total_free_pages = 0;
static uint32_t heap_current = 0;
static uint32_t heap_base = 0;

extern uint32_t __kernel_heap_start;

void mem_init(void) {
    memset(page_bitmap, 0xFF, sizeof(page_bitmap)); // Mark all as used initially
    
    // Calculate usable pages starting at 4MB above RAM_BASE (0x80400000)
    uint32_t usable_start_page = (4 * 1024 * 1024) / PAGE_SIZE; // Page 1024
    total_free_pages = 0;

    for (uint32_t i = usable_start_page; i < TOTAL_PAGES; i++) {
        uint32_t word = i / 32;
        uint32_t bit = i % 32;
        page_bitmap[word] &= ~(1U << bit); // Mark free
        total_free_pages++;
    }

    heap_base = (uint32_t)&__kernel_heap_start;
    // Align heap to 16 bytes
    heap_base = (heap_base + 15) & ~15;
    heap_current = heap_base;

    printf("[MEM] Memory manager initialized. Usable pages: %d (%d KB free)\n",
           total_free_pages, (total_free_pages * PAGE_SIZE) / 1024);
}

void *page_alloc(void) {
    uint32_t usable_start_page = (4 * 1024 * 1024) / PAGE_SIZE;

    for (uint32_t i = usable_start_page; i < TOTAL_PAGES; i++) {
        uint32_t word = i / 32;
        uint32_t bit = i % 32;
        if (!(page_bitmap[word] & (1U << bit))) {
            page_bitmap[word] |= (1U << bit); // Mark as allocated
            total_free_pages--;
            uint32_t addr = RAM_BASE + (i * PAGE_SIZE);
            memset((void*)addr, 0, PAGE_SIZE);
            return (void*)addr;
        }
    }
    return NULL; // Out of memory
}

void page_free(void *ptr) {
    uint32_t addr = (uint32_t)ptr;
    if (addr < RAM_BASE || addr >= RAM_BASE + RAM_SIZE) return;

    uint32_t page = (addr - RAM_BASE) / PAGE_SIZE;
    uint32_t word = page / 32;
    uint32_t bit = page % 32;

    if (page_bitmap[word] & (1U << bit)) {
        page_bitmap[word] &= ~(1U << bit);
        total_free_pages++;
    }
}

void *kmalloc(size_t size) {
    if (size == 0) return NULL;
    // Align to 8 bytes
    size = (size + 7) & ~7;
    
    uint32_t alloc_addr = heap_current;
    heap_current += size;
    return (void*)alloc_addr;
}

void kfree(void *ptr) {
    // Simple bump allocator doesn't individually reclaim small blocks;
    // full tasks release whole pages.
    (void)ptr;
}

void mem_stats(uint32_t *total_pages, uint32_t *free_pages, uint32_t *heap_used) {
    if (total_pages) *total_pages = TOTAL_PAGES;
    if (free_pages)  *free_pages = total_free_pages;
    if (heap_used)   *heap_used = heap_current - heap_base;
}
