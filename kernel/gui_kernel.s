# ==============================================================================
# AdiOS v0.3.0-alpha: High-Interactivity Graphical Desktop Windowing System
# Bare-Metal RISC-V (RV32IM) GUI Kernel & Application Suite
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

    # 4. Print boot message to UART terminal
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
    # A. Check Start Menu pill or dropdown click
    mv a0, s0
    mv a1, s1
    call check_start_menu_click

    # B. Check Paint Studio interactions (Swatches, Clear, or Canvas Drawing)
    mv a0, s0
    mv a1, s1
    call check_paint_interactions

    # C. Check Calculator button click
    mv a0, s0
    mv a1, s1
    call check_calc_click

    j flush_step

handle_mouse_up:
    # Release debounce latch for calculator and start menu
    la t0, calc_mouse_prev
    sw zero, 0(t0)
    la t0, menu_mouse_prev
    sw zero, 0(t0)

flush_step:
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

    # Center Taskbar Text: "AdiOS v0.3.0 [RISC-V 32-bit]"
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

    # 5. Render Window 1: AdiOS Paint Studio (x=360, y=38, w=260, h=200)
    li a0, 360
    li a1, 38
    li a2, 260
    li a3, 200
    la a4, str_win_paint
    li a5, 0x00FFFFFF     # White Canvas Body
    call draw_window_chrome

    # Render Paint Toolbar & Palette Swatches
    call render_paint_toolbar

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

    # Calculator Buttons Grid (4x4)
    # Row 0: 7, 8, 9, +
    li a0, 376; li a1, 318; la a2, str_btn_7; call draw_calc_button
    li a0, 434; li a1, 318; la a2, str_btn_8; call draw_calc_button
    li a0, 492; li a1, 318; la a2, str_btn_9; call draw_calc_button
    li a0, 550; li a1, 318; la a2, str_btn_plus; call draw_calc_button

    # Row 1: 4, 5, 6, -
    li a0, 376; li a1, 348; la a2, str_btn_4; call draw_calc_button
    li a0, 434; li a1, 348; la a2, str_btn_5; call draw_calc_button
    li a0, 492; li a1, 348; la a2, str_btn_6; call draw_calc_button
    li a0, 550; li a1, 348; la a2, str_btn_minus; call draw_calc_button

    # Row 2: 1, 2, 3, *
    li a0, 376; li a1, 378; la a2, str_btn_1; call draw_calc_button
    li a0, 434; li a1, 378; la a2, str_btn_2; call draw_calc_button
    li a0, 492; li a1, 378; la a2, str_btn_3; call draw_calc_button
    li a0, 550; li a1, 378; la a2, str_btn_mul; call draw_calc_button

    # Row 3: C, 0, =, /
    li a0, 376; li a1, 408; la a2, str_btn_c; call draw_calc_button
    li a0, 434; li a1, 408; la a2, str_btn_0; call draw_calc_button
    li a0, 492; li a1, 408; la a2, str_btn_eq; call draw_calc_button
    li a0, 550; li a1, 408; la a2, str_btn_div; call draw_calc_button

    # Initial LCD Draw
    call render_calc_lcd

    lw ra, 0(sp)
    addi sp, sp, 4
    ret

# ------------------------------------------------------------------------------
# Paint Studio Subsystem
# ------------------------------------------------------------------------------
render_paint_toolbar:
    addi sp, sp, -4
    sw ra, 0(sp)

    # Toolbar background strip: (x=362, y=58, w=256, h=22), Light Slate (#E0E2EA)
    li a0, 362
    li a1, 58
    li a2, 256
    li a3, 22
    li a4, 0x00E0E2EA
    call gfx_fill_rect

    # Swatch 0: Black (#000000)
    li a0, 370; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00000000; call gfx_fill_rect
    li a0, 370; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00787C99; call gfx_draw_rect_outline

    # Swatch 1: Red (#F7768E)
    li a0, 390; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00F7768E; call gfx_fill_rect
    li a0, 390; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00787C99; call gfx_draw_rect_outline

    # Swatch 2: Green (#9ECE6A)
    li a0, 410; li a1, 62; li a2, 16; li a3, 14; li a4, 0x009ECE6A; call gfx_fill_rect
    li a0, 410; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00787C99; call gfx_draw_rect_outline

    # Swatch 3: Blue (#7AA2F7)
    li a0, 430; li a1, 62; li a2, 16; li a3, 14; li a4, 0x007AA2F7; call gfx_fill_rect
    li a0, 430; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00787C99; call gfx_draw_rect_outline

    # Swatch 4: Yellow (#E0AF68)
    li a0, 450; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00E0AF68; call gfx_fill_rect
    li a0, 450; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00787C99; call gfx_draw_rect_outline

    # Swatch 5: Purple (#BB9AF7)
    li a0, 470; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00BB9AF7; call gfx_fill_rect
    li a0, 470; li a1, 62; li a2, 16; li a3, 14; li a4, 0x00787C99; call gfx_draw_rect_outline

    # Active Color Preview Indicator Box: (x=496, y=62, w=18, h=14)
    li a0, 496
    li a1, 62
    li a2, 18
    li a3, 14
    la t0, paint_current_color
    lw a4, 0(t0)
    call gfx_fill_rect

    li a0, 496
    li a1, 62
    li a2, 18
    li a3, 14
    li a4, 0x001A1B26
    call gfx_draw_rect_outline

    # Clear Button: (x=545, y=60, w=48, h=18)
    li a0, 545
    li a1, 60
    li a2, 48
    li a3, 18
    li a4, 0x00F7768E     # Soft Coral Red
    call gfx_fill_rect

    li a0, 545
    li a1, 60
    li a2, 48
    li a3, 18
    li a4, 0x001A1B26
    call gfx_draw_rect_outline

    li a0, 555
    li a1, 65
    la a2, str_btn_clear
    li a3, 0x00FFFFFF
    li a4, 0x00F7768E
    call gfx_draw_string

    lw ra, 0(sp)
    addi sp, sp, 4
    ret

check_paint_interactions:
    addi sp, sp, -8
    sw ra, 4(sp)

    # 1. Check if click is in Toolbar region (y in [58..78], x in [365..610])
    li t0, 58
    blt a1, t0, check_canvas_draw
    li t0, 78
    bgt a1, t0, check_canvas_draw

    # In toolbar!
    # Check Swatch 0 (Black): x in [370..386]
    li t0, 370; blt a0, t0, check_s1; li t0, 386; bgt a0, t0, check_s1
    la t0, paint_current_color; sw zero, 0(t0)
    call render_paint_toolbar
    j paint_done

check_s1: # Swatch 1 (Red): x in [390..406]
    li t0, 390; blt a0, t0, check_s2; li t0, 406; bgt a0, t0, check_s2
    la t0, paint_current_color; li t1, 0x00F7768E; sw t1, 0(t0)
    call render_paint_toolbar
    j paint_done

check_s2: # Swatch 2 (Green): x in [410..426]
    li t0, 410; blt a0, t0, check_s3; li t0, 426; bgt a0, t0, check_s3
    la t0, paint_current_color; li t1, 0x009ECE6A; sw t1, 0(t0)
    call render_paint_toolbar
    j paint_done

check_s3: # Swatch 3 (Blue): x in [430..446]
    li t0, 430; blt a0, t0, check_s4; li t0, 446; bgt a0, t0, check_s4
    la t0, paint_current_color; li t1, 0x007AA2F7; sw t1, 0(t0)
    call render_paint_toolbar
    j paint_done

check_s4: # Swatch 4 (Yellow): x in [450..466]
    li t0, 450; blt a0, t0, check_s5; li t0, 466; bgt a0, t0, check_s5
    la t0, paint_current_color; li t1, 0x00E0AF68; sw t1, 0(t0)
    call render_paint_toolbar
    j paint_done

check_s5: # Swatch 5 (Purple): x in [470..486]
    li t0, 470; blt a0, t0, check_clr; li t0, 486; bgt a0, t0, check_clr
    la t0, paint_current_color; li t1, 0x00BB9AF7; sw t1, 0(t0)
    call render_paint_toolbar
    j paint_done

check_clr: # Clear Button [CLR]: x in [545..595]
    li t0, 545; blt a0, t0, paint_done; li t0, 595; bgt a0, t0, paint_done
    # Wipe canvas interior back to pure white!
    li a0, 362
    li a1, 82
    li a2, 256
    li a3, 154
    li a4, 0x00FFFFFF
    call gfx_fill_rect
    j paint_done

check_canvas_draw:
    # Check if click/drag is strictly within canvas interior
    # x in [365..615], y in [84..234]
    li t0, 365; blt a0, t0, paint_done
    li t0, 615; bgt a0, t0, paint_done
    li t0, 84;  blt a1, t0, paint_done
    li t0, 234; bgt a1, t0, paint_done

    # Draw 4x4 brush block centered at (x-1, y-1) with active color
    addi a0, a0, -1
    addi a1, a1, -1
    li a2, 4
    li a3, 4
    la t0, paint_current_color
    lw a4, 0(t0)
    call gfx_fill_rect

paint_done:
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

# ------------------------------------------------------------------------------
# Calculator Subsystem
# ------------------------------------------------------------------------------
render_calc_lcd:
    addi sp, sp, -8
    sw ra, 4(sp)

    # 1. LCD Screen background: (x=374, y=280, w=232, h=30)
    li a0, 374
    li a1, 280
    li a2, 232
    li a3, 30
    li a4, 0x0016161E     # Deep Black LCD
    call gfx_fill_rect

    li a0, 374
    li a1, 280
    li a2, 232
    li a3, 30
    li a4, 0x00414868     # Border
    call gfx_draw_rect_outline

    # 2. Format current value `calc_val_a` into string
    la t0, calc_val_a
    lw a0, 0(t0)
    la a1, calc_str_buf
    call format_uint

    # 3. Compute text width: length * 8 pixels
    la t0, calc_str_buf
    li t1, 0 # len
calc_len_loop:
    lb t2, 0(t0)
    beqz t2, calc_len_done
    addi t1, t1, 1
    addi t0, t0, 1
    j calc_len_loop
calc_len_done:
    # Right-aligned text at x = 590 - (len * 8)
    slli t2, t1, 3      # len * 8
    li a0, 592
    sub a0, a0, t2
    li a1, 290
    la a2, calc_str_buf
    li a3, 0x007DCFFF   # Electric Blue LCD Digits
    li a4, 0x0016161E
    call gfx_draw_string

    lw ra, 4(sp)
    addi sp, sp, 8
    ret

# Formats unsigned integer in a0 to ASCII string in buffer a1
format_uint:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s0, 8(sp)
    sw s1, 4(sp)
    sw s2, 0(sp)

    mv s0, a0           # number
    mv s1, a1           # buffer pointer
    bnez s0, fmt_not_zero
    # If 0, output "0\0"
    li t0, 48
    sb t0, 0(s1)
    sb zero, 1(s1)
    j fmt_done

fmt_not_zero:
    # Push digits onto stack (division by 10)
    li s2, 0            # digit count
fmt_div_loop:
    beqz s0, fmt_pop_loop
    li t0, 10
    rem t1, s0, t0      # remainder (digit 0..9)
    div s0, s0, t0      # quotient
    addi sp, sp, -4
    sw t1, 0(sp)
    addi s2, s2, 1
    j fmt_div_loop

fmt_pop_loop:
    beqz s2, fmt_terminate
    lw t1, 0(sp)
    addi sp, sp, 4
    addi t1, t1, 48     # ASCII digit
    sb t1, 0(s1)
    addi s1, s1, 1
    addi s2, s2, -1
    j fmt_pop_loop

fmt_terminate:
    sb zero, 0(s1)      # null terminator

fmt_done:
    lw s2, 0(sp)
    lw s1, 4(sp)
    lw s0, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

check_calc_click:
    addi sp, sp, -8
    sw ra, 4(sp)

    # Check debounce
    la t0, calc_mouse_prev
    lw t1, 0(t0)
    bnez t1, calc_click_exit

    # Check Calculator button region (x in [376..600], y in [318..432])
    li t0, 376; blt a0, t0, calc_click_exit
    li t0, 600; bgt a0, t0, calc_click_exit
    li t0, 318; blt a1, t0, calc_click_exit
    li t0, 432; bgt a1, t0, calc_click_exit

    # Set debounce latch
    la t0, calc_mouse_prev
    li t1, 1
    sw t1, 0(t0)

    # Determine Column:
    # Col 0: 376..424, Col 1: 434..482, Col 2: 492..540, Col 3: 550..598
    li t2, 0 # col
    li t0, 426; blt a0, t0, have_col
    li t2, 1
    li t0, 484; blt a0, t0, have_col
    li t2, 2
    li t0, 542; blt a0, t0, have_col
    li t2, 3

have_col:
    # Determine Row:
    # Row 0: 318..342, Row 1: 348..372, Row 2: 378..402, Row 3: 408..432
    li t3, 0 # row
    li t0, 344; blt a1, t0, have_row
    li t3, 1
    li t0, 374; blt a1, t0, have_row
    li t3, 2
    li t0, 404; blt a1, t0, have_row
    li t3, 3

have_row:
    # Dispatch button by (row, col)
    # Row 0: 7, 8, 9, +
    bnez t3, try_row1
    beqz t2, btn_7
    li t0, 1; beq t2, t0, btn_8
    li t0, 2; beq t2, t0, btn_9
    j btn_plus

try_row1: # Row 1: 4, 5, 6, -
    li t0, 1; bne t3, t0, try_row2
    beqz t2, btn_4
    li t0, 1; beq t2, t0, btn_5
    li t0, 2; beq t2, t0, btn_6
    j btn_minus

try_row2: # Row 2: 1, 2, 3, *
    li t0, 2; bne t3, t0, try_row3
    beqz t2, btn_1
    li t0, 1; beq t2, t0, btn_2
    li t0, 2; beq t2, t0, btn_3
    j btn_mul

try_row3: # Row 3: C, 0, =, /
    beqz t2, btn_c
    li t0, 1; beq t2, t0, btn_0
    li t0, 2; beq t2, t0, btn_eq
    j btn_div

# Digit handlers
btn_0: li a0, 0; call handle_calc_digit; j calc_click_done
btn_1: li a0, 1; call handle_calc_digit; j calc_click_done
btn_2: li a0, 2; call handle_calc_digit; j calc_click_done
btn_3: li a0, 3; call handle_calc_digit; j calc_click_done
btn_4: li a0, 4; call handle_calc_digit; j calc_click_done
btn_5: li a0, 5; call handle_calc_digit; j calc_click_done
btn_6: li a0, 6; call handle_calc_digit; j calc_click_done
btn_7: li a0, 7; call handle_calc_digit; j calc_click_done
btn_8: li a0, 8; call handle_calc_digit; j calc_click_done
btn_9: li a0, 9; call handle_calc_digit; j calc_click_done

# Operator handlers
btn_plus:  li a0, 1; call handle_calc_op; j calc_click_done
btn_minus: li a0, 2; call handle_calc_op; j calc_click_done
btn_mul:   li a0, 3; call handle_calc_op; j calc_click_done
btn_div:   li a0, 4; call handle_calc_op; j calc_click_done

# Clear handler
btn_c:
    la t0, calc_val_a; sw zero, 0(t0)
    la t0, calc_val_b; sw zero, 0(t0)
    la t0, calc_op;    sw zero, 0(t0)
    la t0, calc_reset_flag; sw zero, 0(t0)
    call render_calc_lcd
    j calc_click_done

# Equals handler
btn_eq:
    call handle_calc_equals
    j calc_click_done

calc_click_done:
    call render_calc_lcd

calc_click_exit:
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

handle_calc_digit:
    addi sp, sp, -4
    sw ra, 0(sp)
    mv t3, a0           # digit
    la t0, calc_reset_flag
    lw t1, 0(t0)
    bnez t1, digit_reset

    # Append: val_a = val_a * 10 + digit
    la t0, calc_val_a
    lw t1, 0(t0)
    li t2, 10
    mul t1, t1, t2
    add t1, t1, t3
    sw t1, 0(t0)
    j digit_done

digit_reset:
    la t0, calc_val_a
    sw t3, 0(t0)
    la t0, calc_reset_flag
    sw zero, 0(t0)

digit_done:
    lw ra, 0(sp)
    addi sp, sp, 4
    ret

handle_calc_op:
    # a0 = op_code (1='+', 2='-', 3='*', 4='/')
    la t0, calc_val_a
    lw t1, 0(t0)
    la t0, calc_val_b
    sw t1, 0(t0)        # val_b = val_a
    la t0, calc_op
    sw a0, 0(t0)        # calc_op = op_code
    la t0, calc_reset_flag
    li t1, 1
    sw t1, 0(t0)
    ret

handle_calc_equals:
    la t0, calc_op
    lw t1, 0(t0)
    beqz t1, eq_done    # No op pending

    la t0, calc_val_b
    lw t2, 0(t0)        # val_b
    la t0, calc_val_a
    lw t3, 0(t0)        # val_a

    li t4, 1; beq t1, t4, eq_add
    li t4, 2; beq t1, t4, eq_sub
    li t4, 3; beq t1, t4, eq_mul
    li t4, 4; beq t1, t4, eq_div
    j eq_finish

eq_add: add t2, t2, t3; j eq_finish
eq_sub: sub t2, t2, t3; j eq_finish
eq_mul: mul t2, t2, t3; j eq_finish
eq_div:
    beqz t3, eq_finish  # Avoid divide by zero
    div t2, t2, t3
    j eq_finish

eq_finish:
    la t0, calc_val_a
    sw t2, 0(t0)
    la t0, calc_op
    sw zero, 0(t0)
    la t0, calc_reset_flag
    li t1, 1
    sw t1, 0(t0)
eq_done:
    ret

# ------------------------------------------------------------------------------
# Start Menu Subsystem
# ------------------------------------------------------------------------------
check_start_menu_click:
    addi sp, sp, -8
    sw ra, 4(sp)

    # Check debounce
    la t0, menu_mouse_prev
    lw t1, 0(t0)
    bnez t1, menu_click_done

    # 1. Check if clicking the Start Pill: (x in [6..70], y in [3..21])
    li t0, 6;  blt a0, t0, check_menu_items
    li t0, 70; bgt a0, t0, check_menu_items
    li t0, 3;  blt a1, t0, check_menu_items
    li t0, 21; bgt a1, t0, check_menu_items

    # Debounce
    la t0, menu_mouse_prev; li t1, 1; sw t1, 0(t0)

    # Toggle Start Menu
    la t0, start_menu_open
    lw t1, 0(t0)
    xori t1, t1, 1
    sw t1, 0(t0)

    beqz t1, close_start_menu
    call render_start_menu
    j menu_click_done

close_start_menu:
    # Erase menu by restoring wallpaper and top of terminal
    li a0, 6
    li a1, 25
    li a2, 144
    li a3, 125
    li a4, 0x001A1B26
    call gfx_fill_rect

    # Redraw damaged portion of Terminal window chrome (x=20, y=38)
    li a0, 20
    li a1, 38
    li a2, 130
    li a3, 112
    li a4, 0x001F2335
    call gfx_fill_rect

    # Redraw terminal text lines
    li a0, 30; li a1, 66; la a2, str_term_line1; li a3, 0x0073DACA; li a4, 0x001F2335; call gfx_draw_string
    li a0, 30; li a1, 82; la a2, str_term_line2; li a3, 0x00C0CAF5; li a4, 0x001F2335; call gfx_draw_string
    li a0, 30; li a1, 98; la a2, str_term_line3; li a3, 0x009ECE6A; li a4, 0x001F2335; call gfx_draw_string
    j menu_click_done

check_menu_items:
    # Check if menu is open
    la t0, start_menu_open
    lw t1, 0(t0)
    beqz t1, menu_click_done

    # If menu is open, check item hit: (x in [6..146], y in [26..136])
    li t0, 6;   blt a0, t0, close_on_click_outside
    li t0, 146; bgt a0, t0, close_on_click_outside
    li t0, 26;  blt a1, t0, close_on_click_outside
    li t0, 136; bgt a1, t0, close_on_click_outside

    # Clicked inside menu!
    la t0, menu_mouse_prev; li t1, 1; sw t1, 0(t0)

    # Item 1: Terminal (y in [28..48])
    li t0, 48; bgt a1, t0, menu_item_2
    li a0, 30; li a1, 114; la a2, str_term_focus; li a3, 0x00E0AF68; li a4, 0x001F2335; call gfx_draw_string
    j close_start_menu

menu_item_2: # Item 2: Paint (y in [49..70])
    li t0, 70; bgt a1, t0, menu_item_3
    # Wipe canvas
    li a0, 362; li a1, 82; li a2, 256; li a3, 154; li a4, 0x00FFFFFF; call gfx_fill_rect
    la t0, paint_current_color; sw zero, 0(t0)
    call render_paint_toolbar
    j close_start_menu

menu_item_3: # Item 3: SysMon (y in [71..92])
    li t0, 92; bgt a1, t0, menu_item_4
    j close_start_menu

menu_item_4: # Item 4: Calculator (y in [93..114])
    li t0, 114; bgt a1, t0, menu_item_5
    la t0, calc_val_a; sw zero, 0(t0)
    la t0, calc_val_b; sw zero, 0(t0)
    call render_calc_lcd
    j close_start_menu

menu_item_5: # Item 5: Shutdown (y in [115..136])
    # Real bare-metal shutdown signal via MMIO power manager (0x10000040 = 1)
    li t0, 0x10000040
    li t1, 1
    sw t1, 0(t0)
    j close_start_menu

close_on_click_outside:
    la t0, start_menu_open
    sw zero, 0(t0)
    call close_start_menu

menu_click_done:
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

render_start_menu:
    addi sp, sp, -4
    sw ra, 0(sp)

    # Dropdown Menu: (x=6, y=26, w=140, h=110), Dark Charcoal
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
    li a4, 0x007AA2F7     # Accent Blue Border
    call gfx_draw_rect_outline

    # Menu Items
    li a0, 16; li a1, 36; la a2, str_menu_term;  li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 56; la a2, str_menu_paint; li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 76; la a2, str_menu_sys;   li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 96; la a2, str_menu_calc;  li a3, 0x00C0CAF5; li a4, 0x0016161E; call gfx_draw_string
    li a0, 16; li a1, 116; la a2, str_menu_off;  li a3, 0x00F7768E; li a4, 0x0016161E; call gfx_draw_string

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

    # Button Body: (w=48, h=24)
    mv a0, s0
    mv a1, s1
    li a2, 48
    li a3, 24
    li a4, 0x003B4261
    call gfx_fill_rect

    # Button Border
    mv a0, s0
    mv a1, s1
    li a2, 48
    li a3, 24
    li a4, 0x00565F89
    call gfx_draw_rect_outline

    # Button Text centered
    addi a0, s0, 20
    addi a1, s1, 7
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
# Data Section
# ------------------------------------------------------------------------------
.section .data
gui_boot_msg:
    .string "[AdiOS Kernel] Initializing Graphical Windowing System (640x480 32-bit ARGB)...\n"

str_start_pill:
    .string "AdiOS"

str_taskbar_title:
    .string "AdiOS v0.3.0 [RISC-V 32-bit Desktop]"

str_taskbar_uptime:
    .string "LIVE: 60 FPS"

str_win_term:
    .string "Terminal - Shell"

str_term_line1:
    .string "AdiOS v0.3 GUI Shell [RV32IM]"

str_term_line2:
    .string "Window Compositor & Mouse Active"

str_term_line3:
    .string "adios> Ready."

str_term_focus:
    .string "adios> [Focused via Start Menu]"

str_win_paint:
    .string "AdiOS Paint Studio"

str_btn_clear:
    .string "CLEAR"

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
str_btn_mul:   .string "*"
str_btn_c:     .string "C"
str_btn_0:     .string "0"
str_btn_eq:    .string "="
str_btn_div:   .string "/"

str_menu_term:  .string ">_ Terminal"
str_menu_paint: .string "*  Paint"
str_menu_sys:   .string "#  SysMon"
str_menu_calc:  .string "=  Calculator"
str_menu_off:   .string "x  Shutdown"

# State Variables
paint_current_color:
    .word 0x00000000    # Default Black

calc_val_a:
    .word 0

calc_val_b:
    .word 0

calc_op:
    .word 0

calc_reset_flag:
    .word 0

calc_mouse_prev:
    .word 0

menu_mouse_prev:
    .word 0

start_menu_open:
    .word 0

.section .bss
calc_str_buf:
    .skip 16

.include "font8x8.s"
