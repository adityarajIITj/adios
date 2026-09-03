# ==============================================================================
# AdiOS v0.2.0-alpha: Graphical Desktop Windowing System
# Bare-Metal RISC-V (RV32IM) GUI Kernel & Desktop Application Suite
# ==============================================================================

.section .text
.global _start
.global trap_handler

_start:
    # 1. Disable interrupts initially
    csrw mstatus, zero

    # 2. Set up stack pointer at 0x81000000 (16 MB mark)
    li sp, 0x81000000

    # 3. Set trap vector
    la t0, trap_handler
    csrw mtvec, t0

    # 4. Print boot message to UART terminal as well
    la a0, gui_boot_msg
    call print_uart

    # 5. Initialize Full Desktop GUI
    call init_gui_desktop

    # 6. Enable Timer Interrupts
    li t0, 0x80
    csrs mie, t0
    li t0, 0x10000010
    lw t1, 0(t0)
    li t2, 50000
    add t1, t1, t2
    sw t1, 8(t0)

    # Enable Global Interrupts (mstatus.MIE)
    li t0, 0x08
    csrs mstatus, t0

# ------------------------------------------------------------------------------
# Main GUI Event & Compositor Loop
# ------------------------------------------------------------------------------
gui_main_loop:
    # 1. Poll Mouse state from MMIO (0x20130010)
    li t0, 0x20130010
    lw s0, 0(t0)        # s0 = mouse_x (0-639)
    lw s1, 4(t0)        # s1 = mouse_y (0-479)
    lw s2, 8(t0)        # s2 = mouse_buttons (bit 0 = left click)

    # 2. Check if Left Mouse Click is active
    andi t1, s2, 0x01
    beqz t1, handle_mouse_up

    # Left mouse is pressed:
    # A. Check Paint canvas interaction
    mv a0, s0
    mv a1, s1
    call check_paint_click

    # B. Check Calculator button click
    mv a0, s0
    mv a1, s1
    call check_calc_click

    # C. Check Start Menu pill click
    mv a0, s0
    mv a1, s1
    call check_start_pill_click
    j render_step

handle_mouse_up:
    # Clear drag or button hold states
    la t0, calc_btn_pressed
    sw zero, 0(t0)

render_step:
    # Redraw cursor at current mouse position
    mv a0, s0
    mv a1, s1
    call draw_mouse_cursor

    # Signal host to flush frame to screen (0x2013000C = 1)
    li t0, 0x2013000C
    li t1, 1
    sw t1, 0(t0)

    # Check terminal keyboard input
    call check_uart_shell

    j gui_main_loop

# ------------------------------------------------------------------------------
# Desktop Initialization: Renders Wallpaper, Taskbar, and Application Windows
# ------------------------------------------------------------------------------
init_gui_desktop:
    addi sp, sp, -4
    sw ra, 0(sp)

    # 1. Fill Wallpaper with Modern Slate (#1A1B26 -> 0x001A1B26)
    li a0, 0x001A1B26
    call gfx_clear

    # 2. Top Taskbar: (x=0, y=0, w=640, h=24), Dark Charcoal (#16161E -> 0x0016161E)
    li a0, 0
    li a1, 0
    li a2, 640
    li a3, 24
    li a4, 0x0016161E
    call gfx_fill_rect

    # Taskbar bottom border line: (x=0, y=24, w=640, h=1), Slate Border (#292E42)
    li a0, 0
    li a1, 24
    li a2, 640
    li a3, 1
    li a4, 0x00292E42
    call gfx_fill_rect

    # 3. Start Pill: (x=6, y=3, w=64, h=18), Accent Blue (#7AA2F7)
    li a0, 6
    li a1, 3
    li a2, 64
    li a3, 18
    li a4, 0x007AA2F7
    call gfx_fill_rect

    # Start Pill Text: "AdiOS" in Dark Blue (#1A1B26)
    li a0, 14
    li a1, 8
    la a2, str_start_pill
    li a3, 0x001A1B26
    li a4, 0x007AA2F7
    call gfx_draw_string

    # Center Taskbar Text: "AdiOS v0.2.0 [RISC-V 32-bit]"
    li a0, 210
    li a1, 8
    la a2, str_taskbar_title
    li a3, 0x00A9B1D6
    li a4, 0x0016161E
    call gfx_draw_string

    # Right Taskbar Text: "UPTIME: 00s"
    li a0, 530
    li a1, 8
    la a2, str_taskbar_uptime
    li a3, 0x007DCFFF
    li a4, 0x0016161E
    call gfx_draw_string

    # 4. Render Window 0: Terminal Window (x=20, y=38, w=320, h=200)
    li a0, 20
    li a1, 38
    li a2, 320
    li a3, 200
    la a4, str_win_term
    li a5, 0x001F2335     # Body Color
    call draw_window_chrome

    # Terminal Content Text
    li a0, 30
    li a1, 66
    la a2, str_term_line1
    li a3, 0x0073DACA     # Cyan
    li a4, 0x001F2335
    call gfx_draw_string

    li a0, 30
    li a1, 82
    la a2, str_term_line2
    li a3, 0x00C0CAF5     # White/Blue
    li a4, 0x001F2335
    call gfx_draw_string

    li a0, 30
    li a1, 98
    la a2, str_term_line3
    li a3, 0x009ECE6A     # Green prompt
    li a4, 0x001F2335
    call gfx_draw_string

    # 5. Render Window 1: AdiOS Paint (x=360, y=38, w=260, h=200)
    li a0, 360
    li a1, 38
    li a2, 260
    li a3, 200
    la a4, str_win_paint
    li a5, 0x00FFFFFF     # White Canvas Body
    call draw_window_chrome

    # Paint Toolbar Color Palette Swatches (y=62)
    # Swatch 1: Black
    li a0, 370
    li a1, 62
    li a2, 16
    li a3, 14
    li a4, 0x00000000
    call gfx_fill_rect

    # Swatch 2: Red
    li a0, 392
    li a1, 62
    li a2, 16
    li a3, 14
    li a4, 0x00F7768E
    call gfx_fill_rect

    # Swatch 3: Green
    li a0, 414
    li a1, 62
    li a2, 16
    li a3, 14
    li a4, 0x009ECE6A
    call gfx_fill_rect

    # Swatch 4: Blue
    li a0, 436
    li a1, 62
    li a2, 16
    li a3, 14
    li a4, 0x007AA2F7
    call gfx_fill_rect

    # Swatch 5: Yellow
    li a0, 458
    li a1, 62
    li a2, 16
    li a3, 14
    li a4, 0x00E0AF68
    call gfx_fill_rect

    # Palette label
    li a0, 485
    li a1, 65
    la a2, str_paint_hint
    li a3, 0x00565F89
    li a4, 0x00FFFFFF
    call gfx_draw_string

    # 6. Render Window 2: System Monitor (x=20, y=252, w=320, h=210)
    li a0, 20
    li a1, 252
    li a2, 320
    li a3, 210
    la a4, str_win_sysmon
    li a5, 0x001A1B26     # Dark Slate
    call draw_window_chrome

    # Sysmon Labels
    li a0, 32
    li a1, 280
    la a2, str_sys_cpu
    li a3, 0x00C0CAF5
    li a4, 0x001A1B26
    call gfx_draw_string

    li a0, 32
    li a1, 304
    la a2, str_sys_ram
    li a3, 0x00C0CAF5
    li a4, 0x001A1B26
    call gfx_draw_string

    # RAM Progress Bar Outline: (x=32, y=324, w=290, h=20)
    li a0, 32
    li a1, 324
    li a2, 290
    li a3, 20
    li a4, 0x003B4261
    call gfx_draw_rect_outline

    # RAM Progress Bar Fill: (7168 free / 8192 total -> 87% green bar)
    li a0, 34
    li a1, 326
    li a2, 252
    li a3, 16
    li a4, 0x009ECE6A     # Vibrant Green Fill
    call gfx_fill_rect

    li a0, 32
    li a1, 356
    la a2, str_sys_sched
    li a3, 0x007AA2F7
    li a4, 0x001A1B26
    call gfx_draw_string

    li a0, 32
    li a1, 380
    la a2, str_sys_tasks
    li a3, 0x00BB9AF7
    li a4, 0x001A1B26
    call gfx_draw_string

    # 7. Render Window 3: Calculator (x=360, y=252, w=260, h=210)
    li a0, 360
    li a1, 252
    li a2, 260
    li a3, 210
    la a4, str_win_calc
    li a5, 0x0024283B     # Charcoal Blue
    call draw_window_chrome

    # Calculator LCD Display: (x=374, y=280, w=232, h=30)
    li a0, 374
    li a1, 280
    li a2, 232
    li a3, 30
    li a4, 0x0016161E
    call gfx_fill_rect

    li a0, 374
    li a1, 280
    li a2, 232
    li a3, 30
    li a4, 0x00414868
    call gfx_draw_rect_outline

    # Calc Display Initial Value "42"
    li a0, 580
    li a1, 290
    la a2, str_calc_val
    li a3, 0x007DCFFF
    li a4, 0x0016161E
    call gfx_draw_string

    # Calc Grid Buttons (Row 1: 7, 8, 9, +)
    li a0, 376; li a1, 320; la a2, str_btn_7; call draw_calc_button
    li a0, 434; li a1, 320; la a2, str_btn_8; call draw_calc_button
    li a0, 492; li a1, 320; la a2, str_btn_9; call draw_calc_button
    li a0, 550; li a1, 320; la a2, str_btn_plus; call draw_calc_button

    # Calc Grid Buttons (Row 2: 4, 5, 6, -)
    li a0, 376; li a1, 355; la a2, str_btn_4; call draw_calc_button
    li a0, 434; li a1, 355; la a2, str_btn_5; call draw_calc_button
    li a0, 492; li a1, 355; la a2, str_btn_6; call draw_calc_button
    li a0, 550; li a1, 355; la a2, str_btn_minus; call draw_calc_button

    # Calc Grid Buttons (Row 3: 1, 2, 3, =)
    li a0, 376; li a1, 390; la a2, str_btn_1; call draw_calc_button
    li a0, 434; li a1, 390; la a2, str_btn_2; call draw_calc_button
    li a0, 492; li a1, 390; la a2, str_btn_3; call draw_calc_button
    li a0, 550; li a1, 390; la a2, str_btn_eq; call draw_calc_button

    lw ra, 0(sp)
    addi sp, sp, 4
    ret

# ------------------------------------------------------------------------------
# Window Chrome Drawing (Title Bar, Title Text, Close Button, Drop Shadow)
# a0 = x, a1 = y, a2 = w, a3 = h, a4 = title_ptr, a5 = body_color
# ------------------------------------------------------------------------------
draw_window_chrome:
    addi sp, sp, -28
    sw ra, 24(sp)
    sw s0, 20(sp)
    sw s1, 16(sp)
    sw s2, 12(sp)
    sw s3, 8(sp)
    sw s4, 4(sp)
    sw s5, 0(sp)

    mv s0, a0
    mv s1, a1
    mv s2, a2
    mv s3, a3
    mv s4, a4
    mv s5, a5

    # 1. Subtle Window Drop Shadow: (x+4, y+4, w, h)
    addi a0, s0, 4
    addi a1, s1, 4
    mv a2, s2
    mv a3, s3
    li a4, 0x000F0F14
    call gfx_fill_rect

    # 2. Window Body Fill
    mv a0, s0
    mv a1, s1
    mv a2, s2
    mv a3, s3
    mv a4, s5
    call gfx_fill_rect

    # 3. Window Outer Border
    mv a0, s0
    mv a1, s1
    mv a2, s2
    mv a3, s3
    li a4, 0x00414868
    call gfx_draw_rect_outline

    # 4. Title Bar Fill (Height = 20) in Slate Blue (#292E42)
    mv a0, s0
    mv a1, s1
    mv a2, s2
    li a3, 20
    li a4, 0x00292E42
    call gfx_fill_rect

    # Title Bar Text
    addi a0, s0, 8
    addi a1, s1, 6
    mv a2, s4
    li a3, 0x00C0CAF5
    li a4, 0x00292E42
    call gfx_draw_string

    # Close Button [X] Red Circle: (x + w - 16, y + 5, 10, 10)
    add t0, s0, s2
    addi a0, t0, -16
    addi a1, s1, 5
    li a2, 10
    li a3, 10
    li a4, 0x00F7768E     # Soft Red
    call gfx_fill_rect

    lw s5, 0(sp)
    lw s4, 4(sp)
    lw s3, 8(sp)
    lw s2, 12(sp)
    lw s1, 16(sp)
    lw s0, 20(sp)
    lw ra, 24(sp)
    addi sp, sp, 28
    ret

# ------------------------------------------------------------------------------
# Calculator Button Drawer (a0=x, a1=y, a2=label_ptr)
# ------------------------------------------------------------------------------
draw_calc_button:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s0, 8(sp)
    sw s1, 4(sp)
    sw s2, 0(sp)

    mv s0, a0
    mv s1, a1
    mv s2, a2

    # Button Body: (w=48, h=26)
    mv a0, s0
    mv a1, s1
    li a2, 48
    li a3, 26
    li a4, 0x003B4261
    call gfx_fill_rect

    # Button Border
    mv a0, s0
    mv a1, s1
    li a2, 48
    li a3, 26
    li a4, 0x00565F89
    call gfx_draw_rect_outline

    # Button Text centered
    addi a0, s0, 20
    addi a1, s1, 8
    mv a2, s2
    li a3, 0x00FFFFFF
    li a4, 0x003B4261
    call gfx_draw_string

    lw s2, 0(sp)
    lw s1, 4(sp)
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# ------------------------------------------------------------------------------
# Mouse Interaction Handlers
# ------------------------------------------------------------------------------
check_paint_click:
    addi sp, sp, -8
    sw ra, 4(sp)

    # If mouse_x in [370..610] and mouse_y in [80..230], draw 3x3 brush!
    li t0, 370
    blt a0, t0, paint_click_done
    li t0, 610
    bge a0, t0, paint_click_done
    li t0, 80
    blt a1, t0, paint_click_done
    li t0, 230
    bge a1, t0, paint_click_done

    # Draw brush pixel: (x, y, w=4, h=4, color=0x00F7768E)
    mv a0, s0
    mv a1, s1
    li a2, 4
    li a3, 4
    li a4, 0x00F7768E
    call gfx_fill_rect

paint_click_done:
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

check_calc_click:
    addi sp, sp, -8
    sw ra, 4(sp)

    # Check if click is inside Calculator button region (x in [376..600], y in [320..420])
    li t0, 376
    blt a0, t0, calc_click_done
    li t0, 600
    bge a0, t0, calc_click_done
    li t0, 320
    blt a1, t0, calc_click_done
    li t0, 420
    bge a1, t0, calc_click_done

    # Clicked! Flash display with "7" as demo feedback
    li a0, 580
    li a1, 290
    la a2, str_btn_7
    li a3, 0x009ECE6A     # Green
    li a4, 0x0016161E
    call gfx_draw_string

calc_click_done:
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

check_start_pill_click:
    addi sp, sp, -8
    sw ra, 4(sp)

    # Start pill is at (6, 3, 64, 18)
    li t0, 6
    blt a0, t0, pill_click_done
    li t0, 70
    bge a0, t0, pill_click_done
    li t0, 3
    blt a1, t0, pill_click_done
    li t0, 21
    bge a1, t0, pill_click_done

    # Toggle Start Menu Dropdown
    call render_start_menu

pill_click_done:
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

render_start_menu:
    addi sp, sp, -4
    sw ra, 0(sp)

    # Dropdown Menu: (x=6, y=26, w=140, h=110), Dark Navy
    li a0, 6
    li a1, 26
    li a2, 140
    li a3, 110
    li a4, 0x0016161E
    call gfx_fill_rect

    li a0, 6
    li a1, 26
    li a2, 140
    li a3, 110
    li a4, 0x007AA2F7
    call gfx_draw_rect_outline

    # Menu Items
    li a0, 16; li a1, 36; la a2, str_menu_term; li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 56; la a2, str_menu_paint; li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 76; la a2, str_menu_sys; li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 96; la a2, str_menu_calc; li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 116; la a2, str_menu_off; li a3, 0x00F7768E; li a4, 0x0016161E; call gfx_draw_string

    lw ra, 0(sp)
    addi sp, sp, 4
    ret

# ------------------------------------------------------------------------------
# Hardware Mouse Cursor Rendering (Classic 11x16 Arrow Pointer)
# ------------------------------------------------------------------------------
draw_mouse_cursor:
    addi sp, sp, -8
    sw ra, 4(sp)

    # Draw small arrow head using 4 rect strokes
    # Tip: (x, y) to (x+8, y+8)
    mv t0, a0
    mv t1, a1

    # Vertical stem
    mv a0, t0
    mv a1, t1
    li a2, 2
    li a3, 12
    li a4, 0x00FFFFFF     # White cursor
    call gfx_fill_rect

    # Diagonal wing
    addi a0, t0, 2
    addi a1, t1, 2
    li a2, 2
    li a3, 6
    li a4, 0x00FFFFFF
    call gfx_fill_rect

    addi a0, t0, 4
    addi a1, t1, 4
    li a2, 2
    li a3, 4
    li a4, 0x00FFFFFF
    call gfx_fill_rect

    lw ra, 4(sp)
    addi sp, sp, 8
    ret

# ------------------------------------------------------------------------------
# 2D Graphics Engine Primitives (Targeting 0x20000000 640x480 32-bit Framebuffer)
# ------------------------------------------------------------------------------
gfx_clear:
    # a0 = color (0x00RRGGBB)
    li t0, 0x20000000
    li t1, 0x2012C000     # 640 * 480 * 4 = 0x12C000
clear_loop:
    bge t0, t1, clear_done
    sw a0, 0(t0)
    sw a0, 4(t0)
    sw a0, 8(t0)
    sw a0, 12(t0)
    addi t0, t0, 16
    j clear_loop
clear_done:
    ret

gfx_fill_rect:
    # a0 = x, a1 = y, a2 = w, a3 = h, a4 = color
    li t0, 640
    mul t1, a1, t0      # y * 640
    add t1, t1, a0      # y * 640 + x
    slli t1, t1, 2      # * 4
    li t0, 0x20000000
    add t1, t1, t0      # t1 = start pointer for row 0

    li t4, 2560         # 640 * 4 = 2560 bytes row stride
    li t2, 0            # row counter
rect_row_loop:
    bge t2, a3, rect_done

    mv t0, t1           # t0 = pixel pointer for current row
    li t3, 0            # col counter
rect_col_loop:
    bge t3, a2, rect_col_done
    sw a4, 0(t0)
    addi t0, t0, 4
    addi t3, t3, 1
    j rect_col_loop
rect_col_done:
    add t1, t1, t4      # advance to next row by +2560 bytes
    addi t2, t2, 1
    j rect_row_loop
rect_done:
    ret

gfx_draw_rect_outline:
    # a0 = x, a1 = y, a2 = w, a3 = h, a4 = color
    addi sp, sp, -24
    sw ra, 20(sp)
    sw s0, 16(sp)
    sw s1, 12(sp)
    sw s2, 8(sp)
    sw s3, 4(sp)
    sw s4, 0(sp)

    mv s0, a0
    mv s1, a1
    mv s2, a2
    mv s3, a3
    mv s4, a4

    # Top border: (x, y, w, 1)
    mv a0, s0; mv a1, s1; mv a2, s2; li a3, 1; mv a4, s4; call gfx_fill_rect
    # Bottom border: (x, y+h-1, w, 1)
    add t0, s1, s3; addi a1, t0, -1; mv a0, s0; mv a2, s2; li a3, 1; mv a4, s4; call gfx_fill_rect
    # Left border: (x, y, 1, h)
    mv a0, s0; mv a1, s1; li a2, 1; mv a3, s3; mv a4, s4; call gfx_fill_rect
    # Right border: (x+w-1, y, 1, h)
    add t0, s0, s2; addi a0, t0, -1; mv a1, s1; li a2, 1; mv a3, s3; mv a4, s4; call gfx_fill_rect

    lw s4, 0(sp)
    lw s3, 4(sp)
    lw s2, 8(sp)
    lw s1, 12(sp)
    lw s0, 16(sp)
    lw ra, 20(sp)
    addi sp, sp, 24
    ret

# ------------------------------------------------------------------------------
# 8x8 Bitmap Font Blitter
# a0 = x, a1 = y, a2 = char_ascii, a3 = fg_color, a4 = bg_color
# ------------------------------------------------------------------------------
gfx_draw_char:
    addi sp, sp, -28
    sw ra, 24(sp)
    sw s0, 20(sp)
    sw s1, 16(sp)
    sw s2, 12(sp)
    sw s3, 8(sp)
    sw s4, 4(sp)

    mv s0, a0 # x
    mv s1, a1 # y
    mv s2, a2 # char
    mv s3, a3 # fg
    mv s4, a4 # bg

    # Calculate font offset: (char - 32) * 8
    li t0, 32
    blt s2, t0, char_done
    li t0, 126
    bgt s2, t0, char_done

    addi t0, s2, -32
    slli t0, t0, 3      # * 8
    la t1, font8x8_data
    add t1, t1, t0      # pointer to 8 bytes for this char

    li t2, 0            # row (0..7)
char_row_loop:
    li t3, 8
    bge t2, t3, char_done

    lb t4, 0(t1)        # 8-bit row mask
    addi t1, t1, 1

    # Base address for this row in framebuffer
    add t0, s1, t2      # y + row
    li t5, 640
    mul t0, t0, t5
    add t0, t0, s0      # (y + row)*640 + x
    slli t0, t0, 2
    li t5, 0x20000000
    add t0, t0, t5      # pointer to pixel (x, y+row)

    li t5, 0            # bit (0..7)
char_bit_loop:
    li t6, 8
    bge t5, t6, char_row_next

    # Check MSB: (t4 << bit) & 0x80
    sll t6, t4, t5
    andi t6, t6, 0x80
    beqz t6, char_draw_bg

    # Draw Foreground
    sw s3, 0(t0)
    j char_bit_next
char_draw_bg:
    # If bg != 0, draw background
    beqz s4, char_bit_next
    sw s4, 0(t0)
char_bit_next:
    addi t0, t0, 4
    addi t5, t5, 1
    j char_bit_loop

char_row_next:
    addi t2, t2, 1
    j char_row_loop

char_done:
    lw s4, 4(sp)
    lw s3, 8(sp)
    lw s2, 12(sp)
    lw s1, 16(sp)
    lw s0, 20(sp)
    lw ra, 24(sp)
    addi sp, sp, 28
    ret

gfx_draw_string:
    # a0 = x, a1 = y, a2 = str_ptr, a3 = fg, a4 = bg
    addi sp, sp, -28
    sw ra, 24(sp)
    sw s0, 20(sp)
    sw s1, 16(sp)
    sw s2, 12(sp)
    sw s3, 8(sp)
    sw s4, 4(sp)

    mv s0, a0
    mv s1, a1
    mv s2, a2
    mv s3, a3
    mv s4, a4

str_draw_loop:
    lb a2, 0(s2)
    beqz a2, str_draw_done
    mv a0, s0
    mv a1, s1
    mv a3, s3
    mv a4, s4
    call gfx_draw_char

    addi s0, s0, 8      # Advance 8 pixels
    addi s2, s2, 1      # Next character
    j str_draw_loop

str_draw_done:
    lw s4, 4(sp)
    lw s3, 8(sp)
    lw s2, 12(sp)
    lw s1, 16(sp)
    lw s0, 20(sp)
    lw ra, 24(sp)
    addi sp, sp, 28
    ret

# ------------------------------------------------------------------------------
# Terminal and UART Helpers
# ------------------------------------------------------------------------------
check_uart_shell:
    addi sp, sp, -4
    sw ra, 0(sp)
    li t0, 0x10000004
    lw t1, 0(t0)
    andi t1, t1, 0x01
    beqz t1, uart_shell_done
    li t0, 0x10000000
    lw a0, 0(t0)
    # Echo back to terminal
    sw a0, 0(t0)
uart_shell_done:
    lw ra, 0(sp)
    addi sp, sp, 4
    ret

print_uart:
    li t0, 0x10000000
uart_str_loop:
    lb t1, 0(a0)
    beqz t1, uart_str_done
    sw t1, 0(t0)
    addi a0, a0, 1
    j uart_str_loop
uart_str_done:
    ret

# ------------------------------------------------------------------------------
# Trap Vector & Clock Timer
# ------------------------------------------------------------------------------
.align 4
trap_handler:
    # Re-arm timer compare
    li t0, 0x10000010
    lw t1, 0(t0)
    li t2, 50000
    add t1, t1, t2
    sw t1, 8(t0)
    mret

# ------------------------------------------------------------------------------
# String Constants
# ------------------------------------------------------------------------------
.section .data
gui_boot_msg:
    .string "[AdiOS Kernel] Initializing Graphical Windowing System (640x480 32-bit ARGB)...\n"

str_start_pill:
    .string "AdiOS"

str_taskbar_title:
    .string "AdiOS v0.2.0 [RISC-V 32-bit Desktop]"

str_taskbar_uptime:
    .string "LIVE: 60 FPS"

str_win_term:
    .string "Terminal - Shell"

str_term_line1:
    .string "AdiOS v0.2 GUI Shell [RV32IM]"

str_term_line2:
    .string "Window Compositor & Mouse Active"

str_term_line3:
    .string "adios> Ready."

str_win_paint:
    .string "AdiOS Paint Studio"

str_paint_hint:
    .string "Draw here!"

str_win_sysmon:
    .string "System Monitor - Memory & Tasks"

str_sys_cpu:
    .string "CPU: RISC-V 32-bit RV32IM @ 50 MHz"

str_sys_ram:
    .string "RAM: 32 MB (8,192 Pages x 4KB)"

str_sys_sched:
    .string "Scheduler: Preemptive Timer-driven"

str_sys_tasks:
    .string "Tasks: 2 Active (Shell, Desktop WM)"

str_win_calc:
    .string "Desktop Calculator"

str_calc_val:
    .string "42"

str_btn_7:     .string "7"
str_btn_8:     .string "8"
str_btn_9:     .string "9"
str_btn_plus:  .string "+"
str_btn_4:     .string "4"
str_btn_5:     .string "5"
str_btn_6:     .string "6"
str_btn_minus: .string "-"
str_btn_1:     .string "1"
str_btn_2:     .string "2"
str_btn_3:     .string "3"
str_btn_eq:    .string "="

str_menu_term:  .string ">_ Terminal"
str_menu_paint: .string "*  Paint"
str_menu_sys:   .string "#  SysMon"
str_menu_calc:  .string "=  Calculator"
str_menu_off:   .string "x  Shutdown"

.section .bss
calc_btn_pressed:
    .word 0

.include "font8x8.s"
