#include "kernel.h"
#include <stdarg.h>

void uart_putc(char c) {
    if (c == '\n') {
        *UART_DATA = '\r';
    }
    *UART_DATA = (uint32_t)c;
}

void uart_puts(const char *s) {
    while (*s) {
        uart_putc(*s++);
    }
}

bool uart_has_char(void) {
    return (*UART_STATUS & 0x01) != 0;
}

char uart_getc(void) {
    while (!uart_has_char()) {
        // Poll
    }
    return (char)(*UART_DATA & 0xFF);
}

static void print_dec(int n) {
    if (n < 0) {
        uart_putc('-');
        n = -n;
    }
    if (n / 10) {
        print_dec(n / 10);
    }
    uart_putc((n % 10) + '0');
}

static void print_hex(uint32_t n) {
    const char hex_chars[] = "0123456789ABCDEF";
    uart_puts("0x");
    for (int i = 7; i >= 0; i--) {
        int nibble = (n >> (i * 4)) & 0xF;
        uart_putc(hex_chars[nibble]);
    }
}

void printf(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);

    for (const char *p = fmt; *p != '\0'; p++) {
        if (*p != '%') {
            uart_putc(*p);
            continue;
        }

        p++;
        switch (*p) {
            case 'c':
                uart_putc((char)va_arg(args, int));
                break;
            case 's': {
                const char *s = va_arg(args, const char*);
                uart_puts(s ? s : "(null)");
                break;
            }
            case 'd':
                print_dec(va_arg(args, int));
                break;
            case 'x':
                print_hex(va_arg(args, uint32_t));
                break;
            case '%':
                uart_putc('%');
                break;
            default:
                uart_putc('%');
                uart_putc(*p);
                break;
        }
    }

    va_end(args);
}

// Utility string functions
size_t strlen(const char *s) {
    size_t len = 0;
    while (*s++) len++;
    return len;
}

int strcmp(const char *s1, const char *s2) {
    while (*s1 && (*s1 == *s2)) {
        s1++;
        s2++;
    }
    return *(const unsigned char*)s1 - *(const unsigned char*)s2;
}

int strncmp(const char *s1, const char *s2, size_t n) {
    while (n && *s1 && (*s1 == *s2)) {
        s1++;
        s2++;
        n--;
    }
    if (n == 0) return 0;
    return *(const unsigned char*)s1 - *(const unsigned char*)s2;
}

char *strcpy(char *dest, const char *src) {
    char *d = dest;
    while ((*d++ = *src++));
    return dest;
}

void *memset(void *s, int c, size_t n) {
    unsigned char *p = s;
    while (n--) *p++ = (unsigned char)c;
    return s;
}

void *memcpy(void *dest, const void *src, size_t n) {
    unsigned char *d = dest;
    const unsigned char *s = src;
    while (n--) *d++ = *s++;
    return dest;
}

int atoi(const char *s) {
    int res = 0;
    int sign = 1;
    if (*s == '-') {
        sign = -1;
        s++;
    }
    while (*s >= '0' && *s <= '9') {
        res = res * 10 + (*s - '0');
        s++;
    }
    return res * sign;
}
