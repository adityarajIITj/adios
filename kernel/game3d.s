# ==============================================================================
# AdiOS Bare-Metal 3D Assembly Game Engine: StarFlight 3D
# Pure RISC-V 32-bit (RV32IM) Machine Assembly Game
# Direct 640x480 32-bit Framebuffer, Hardware Math, PC Speaker & Mouse MMIO
# ==============================================================================

.section .text
.global _start
.global trap_handler

.include "font8x8.s"

# ------------------------------------------------------------------------------
# Constants & Memory Map
# ------------------------------------------------------------------------------
# Framebuffer: 0x20000000 (640x480 32-bit ARGB, 1,228,800 bytes)
# Mouse MMIO:  0x20130010 (x, y, buttons)
# PC Speaker:  0x10000050 (freq, duration)
# UART:        0x10000000

_start:
    # 1. Disable interrupts initially
    csrw mstatus, zero

    # 2. Set stack pointer at 0x81000000 (16 MB mark)
    li sp, 0x81000000

    # 3. Set trap vector
    la t0, trap_handler
    csrw mtvec, t0

    # 4. Print boot announcement to UART
    la a0, game_boot_msg
    call print_uart

    # 5. Initialize Game State
    li t0, 1000
    la t1, ring_z
    sw t0, 0(t1)        # Ring Z = 1000
    sw zero, 4(t1)      # Ring X = 0
    sw zero, 8(t1)      # Ring Y = 0

    la t0, score_val
    sw zero, 0(t0)      # Score = 0

    la t0, speed_val
    li t1, 14
    sw t1, 0(t0)        # Speed = 14 units/frame

# ------------------------------------------------------------------------------
# Main 3D Game Loop (~50 FPS)
# ------------------------------------------------------------------------------
game_main_loop:
    # 1. Poll Mouse MMIO (0x20130010)
    li t0, 0x20130010
    lw s0, 0(t0)        # s0 = mouse_x (0-639)
    lw s1, 4(t0)        # s1 = mouse_y (0-479)
    lw s2, 8(t0)        # s2 = mouse_buttons (bit 0 = left click)

    # Clamp mouse inputs
    bgez s0, mouse_x_ok
    li s0, 320
mouse_x_ok:
    li t1, 640
    blt s0, t1, mouse_x_clamped
    li s0, 320
mouse_x_clamped:

    bgez s1, mouse_y_ok
    li s1, 240
mouse_y_ok:
    li t1, 480
    blt s1, t1, mouse_y_clamped
    li s1, 240
mouse_y_clamped:

    # Calculate ship bank & pitch offsets relative to screen center (320, 240)
    li t0, 320
    sub s3, s0, t0      # s3 = bank offset (-320 to +320)
    li t0, 240
    sub s4, s1, t0      # s4 = pitch offset (-240 to +240)

    # 2. Advance Ring in 3D Space
    la t0, ring_z
    lw t1, 0(t0)        # t1 = ring_z
    la t2, speed_val
    lw t3, 0(t2)        # speed
    sub t1, t1, t3      # ring_z -= speed

    # Check if ring passed camera (ring_z <= 20)
    li t2, 20
    bgt t1, t2, ring_still_alive

    # Ring passed! Check collision (did ship fly through gate?)
    # Target window: |s3| < 80 and |s4| < 60
    li t2, 80
    neg t3, t2
    blt s3, t3, ring_missed
    bgt s3, t2, ring_missed

    li t2, 60
    neg t3, t2
    blt s4, t3, ring_missed
    bgt s4, t2, ring_missed

    # HIT GATE! Score +100 and play victory chime!
    la t2, score_val
    lw t3, 0(t2)
    addi t3, t3, 100
    sw t3, 0(t2)

    # Trigger PC Speaker chime (880 Hz, 80ms)
    li t2, 0x10000050
    li t3, 880
    sw t3, 0(t2)
    li t3, 80
    sw t3, 4(t2)

ring_missed:
    # Reset Ring to horizon with dynamic offset
    li t1, 1100
    # New X based on score
    la t2, score_val
    lw t3, 0(t2)
    andi t3, t3, 0x7F
    addi t3, t3, -64
    sw t3, 4(t0)        # ring_x
    sw zero, 8(t0)      # ring_y

ring_still_alive:
    sw t1, 0(t0)        # update ring_z

    # Advance terrain scroll offset
    la t0, terrain_scroll
    lw t1, 0(t0)
    addi t1, t1, 10
    li t2, 100
    rem t1, t1, t2
    sw t1, 0(t0)

    # 3. Render Complete 3D Frame
    call render_sky_and_ground
    call render_terrain_grid
    call render_3d_ring
    call render_starfighter
    call render_hud

    # 4. Check Laser Blasters (if mouse_buttons & 1)
    andi t1, s2, 0x01
    beqz t1, skip_lasers
    call render_lasers
skip_lasers:

    # 5. Delay loop (~50 FPS)
    li t0, 25000
delay_loop:
    addi t0, t0, -1
    bnez t0, delay_loop

    j game_main_loop

# ------------------------------------------------------------------------------
# 3D Renderer: Sky, Ground & Horizon
# ------------------------------------------------------------------------------
render_sky_and_ground:
    li t0, 0x20000000   # Framebuffer base

    # Fill Sky (Lines 0..239) with Deep Cosmic Navy (0x00101424)
    li t1, 0x00101424
    li t2, 153600       # 640 * 240 pixels
sky_fill_loop:
    sw t1, 0(t0)
    addi t0, t0, 4
    addi t2, t2, -1
    bnez t2, sky_fill_loop

    # Fill Ground (Lines 240..479) with Cyberpunk Dark Emerald (0x00162B22)
    li t1, 0x00162B22
    li t2, 153600       # 640 * 240 pixels
ground_fill_loop:
    sw t1, 0(t0)
    addi t0, t0, 4
    addi t2, t2, -1
    bnez t2, ground_fill_loop

    # Draw Horizon Line at Y=240 in Neon Emerald (0x009ECE6A)
    li t0, 0x20000000
    li t1, 614400       # 240 * 640 * 4
    add t0, t0, t1
    li t1, 0x009ECE6A
    li t2, 640
horizon_loop:
    sw t1, 0(t0)
    addi t0, t0, 4
    addi t2, t2, -1
    bnez t2, horizon_loop

    ret

# ------------------------------------------------------------------------------
# 3D Renderer: Perspective Terrain Grid
# ------------------------------------------------------------------------------
render_terrain_grid:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s5, 8(sp)
    sw s6, 4(sp)

    # 1. Transverse Perspective Lines (moving towards camera)
    la t0, terrain_scroll
    lw s5, 0(t0)        # offset 0..99
    li s6, 1            # index k = 1..6

grid_z_loop:
    # Z_k = k * 120 - s5
    li t0, 120
    mul t0, s6, t0
    sub t0, t0, s5
    blez t0, next_grid_z

    # Perspective Y: Sy = 240 + (Ground_Height * Focal) / Z
    # Ground_Height = 80, Focal = 256 -> 80 * 256 = 20480
    li t1, 20480
    div t1, t1, t0
    addi t1, t1, 240    # Sy = 240 + offset
    li t2, 479
    bge t1, t2, next_grid_z

    # Draw horizontal line at Y = t1 from X=0 to X=639
    li a0, 0
    mv a1, t1
    li a2, 639
    mv a3, t1
    li a4, 0x002E7D5A   # Muted Emerald
    call draw_line_fast

next_grid_z:
    addi s6, s6, 1
    li t0, 7
    blt s6, t0, grid_z_loop

    # 2. Radial Perspective Lines (radiating from horizon vanishing point)
    # Fan out to X = 0, 80, 160, 240, 320, 400, 480, 560, 639 at Y=479
    li s6, 0
radial_loop:
    # X_bottom = s6 * 80
    li t0, 80
    mul a2, s6, t0
    li a0, 320          # X_horizon
    li a1, 240          # Y_horizon
    li a3, 479          # Y_bottom
    li a4, 0x001B4D3E   # Deep Emerald
    call draw_line_fast

    addi s6, s6, 1
    li t0, 9
    blt s6, t0, radial_loop

    lw s6, 4(sp)
    lw s5, 8(sp)
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# ------------------------------------------------------------------------------
# 3D Renderer: Navigation Rings / Space Gates
# ------------------------------------------------------------------------------
render_3d_ring:
    addi sp, sp, -32
    sw ra, 28(sp)
    sw s5, 24(sp)
    sw s6, 20(sp)
    sw s7, 16(sp)

    la t0, ring_z
    lw s5, 0(t0)        # s5 = ring_z
    lw s6, 4(t0)        # s6 = ring_x
    lw s7, 8(t0)        # s7 = ring_y

    blez s5, ring_draw_done

    # Ring radius = 60 units in 3D space
    # 3D Octagon Vertices relative to center:
    # 0: (-42, 60), 1: (42, 60), 2: (60, 42), 3: (60, -42)
    # 4: (42, -60), 5: (-42, -60), 6: (-60, -42), 7: (-60, 42)
    # Project center:
    # Sx_c = 320 + ((ring_x - ship_x) * 256) / ring_z
    # Sy_c = 240 - ((ring_y - ship_y) * 256) / ring_z

    # R_proj = (60 * 256) / ring_z
    li t0, 15360        # 60 * 256
    div t0, t0, s5      # t0 = R_proj (screen radius)
    blez t0, ring_draw_done

    # D_proj = (42 * 256) / ring_z
    li t1, 10752        # 42 * 256
    div t1, t1, s5      # t1 = D_proj

    # Center on screen:
    sub t2, s6, s3      # ring_x - bank
    slli t2, t2, 8      # * 256
    div t2, t2, s5
    addi s6, t2, 320    # s6 = Sx_center

    sub t2, s7, s4      # ring_y - pitch
    slli t2, t2, 8      # * 256
    div t2, t2, s5
    sub s7, zero, t2
    addi s7, s7, 240    # s7 = Sy_center

    # Draw Octagon edges in Neon Gold (0x00E0AF68)
    li a4, 0x00E0AF68

    # Edge 0-1: (-D, -R) to (D, -R)
    sub a0, s6, t1
    sub a1, s7, t0
    add a2, s6, t1
    sub a3, s7, t0
    call draw_line_fast

    # Edge 1-2: (D, -R) to (R, -D)
    add a0, s6, t1
    sub a1, s7, t0
    add a2, s6, t0
    sub a3, s7, t1
    call draw_line_fast

    # Edge 2-3: (R, -D) to (R, D)
    add a0, s6, t0
    sub a1, s7, t1
    add a2, s6, t0
    add a3, s7, t1
    call draw_line_fast

    # Edge 3-4: (R, D) to (D, R)
    add a0, s6, t0
    add a1, s7, t1
    add a2, s6, t1
    add a3, s7, t0
    call draw_line_fast

    # Edge 4-5: (D, R) to (-D, R)
    add a0, s6, t1
    add a1, s7, t0
    sub a2, s6, t1
    add a3, s7, t0
    call draw_line_fast

    # Edge 5-6: (-D, R) to (-R, D)
    sub a0, s6, t1
    add a1, s7, t0
    sub a2, s6, t0
    add a3, s7, t1
    call draw_line_fast

    # Edge 6-7: (-R, D) to (-R, -D)
    sub a0, s6, t0
    add a1, s7, t1
    sub a2, s6, t0
    sub a3, s7, t1
    call draw_line_fast

    # Edge 7-0: (-R, -D) to (-D, -R)
    sub a0, s6, t0
    sub a1, s7, t1
    sub a2, s6, t1
    sub a3, s7, t0
    call draw_line_fast

ring_draw_done:
    lw s7, 16(sp)
    lw s6, 20(sp)
    lw s5, 24(sp)
    lw ra, 28(sp)
    addi sp, sp, 32
    ret

# ------------------------------------------------------------------------------
# 3D Renderer: Player Starfighter (Cockpit, Wings, Afterburners)
# ------------------------------------------------------------------------------
render_starfighter:
    addi sp, sp, -16
    sw ra, 12(sp)

    # Base center of ship on screen
    li t0, 320
    srai t1, s3, 3      # Slight horizontal tilt offset
    add s5, t0, t1      # Ship center X (around 320)

    li t0, 390
    srai t1, s4, 3      # Slight vertical tilt offset
    add s6, t0, t1      # Ship center Y (around 390)

    # Calculate bank roll tilt
    srai s7, s3, 4      # Wing tilt (-20 to +20)

    # 1. Cockpit Canopy (Triangle: Tip at (s5, s6 - 35), Left (s5 - 16, s6 + 10), Right (s5 + 16, s6 + 10))
    li a4, 0x007DCFFF   # Electric Cyan
    mv a0, s5
    addi a1, s6, -35
    addi a2, s5, -16
    addi a3, s6, 10
    call draw_line_fast

    mv a0, s5
    addi a1, s6, -35
    addi a2, s5, 16
    addi a3, s6, 10
    call draw_line_fast

    addi a0, s5, -16
    addi a1, s6, 10
    addi a2, s5, 16
    addi a3, s6, 10
    call draw_line_fast

    # 2. Left Wing (Swept-back Delta Wing)
    li a4, 0x007AA2F7   # Fighter Blue
    addi a0, s5, -16
    addi a1, s6, 10
    addi a2, s5, -95
    addi a3, s6, 30
    sub a3, a3, s7      # Wing tilt roll
    call draw_line_fast

    # Wing Tip Cannon
    addi a0, s5, -95
    addi a1, s6, 30
    sub a1, a1, s7
    addi a2, s5, -95
    addi a3, s6, 12
    sub a3, a3, s7
    call draw_line_fast

    # Inner wing connector
    addi a0, s5, -95
    addi a1, s6, 30
    sub a1, a1, s7
    addi a2, s5, -10
    addi a3, s6, 25
    call draw_line_fast

    # 3. Right Wing (Swept-back Delta Wing)
    addi a0, s5, 16
    addi a1, s6, 10
    addi a2, s5, 95
    addi a3, s6, 30
    add a3, a3, s7      # Opposite wing tilt roll
    call draw_line_fast

    # Right Wing Tip Cannon
    addi a0, s5, 95
    addi a1, s6, 30
    add a1, a1, s7
    addi a2, s5, 95
    addi a3, s6, 12
    add a3, a3, s7
    call draw_line_fast

    # Right Inner wing connector
    addi a0, s5, 95
    addi a1, s6, 30
    add a1, a1, s7
    addi a2, s5, 10
    addi a3, s6, 25
    call draw_line_fast

    # 4. Twin Afterburners (Orange/Yellow Glow)
    li a4, 0x00FFA500   # Bright Orange
    addi a0, s5, -8
    addi a1, s6, 22
    addi a2, s5, -8
    addi a3, s6, 32
    call draw_line_fast

    addi a0, s5, 8
    addi a1, s6, 22
    addi a2, s5, 8
    addi a3, s6, 32
    call draw_line_fast

    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# ------------------------------------------------------------------------------
# 3D Renderer: Twin Laser Blasters
# ------------------------------------------------------------------------------
render_lasers:
    addi sp, sp, -16
    sw ra, 12(sp)

    li a4, 0x00F7768E   # Neon Red / Crimson Lasers

    # Left laser: from wing tip (s5 - 95, s6 + 12 - s7) to center horizon (320, 240)
    addi a0, s5, -95
    addi a1, s6, 12
    sub a1, a1, s7
    li a2, 320
    li a3, 240
    call draw_line_fast

    # Right laser: from wing tip (s5 + 95, s6 + 12 + s7) to center horizon (320, 240)
    addi a0, s5, 95
    addi a1, s6, 12
    add a1, a1, s7
    li a2, 320
    li a3, 240
    call draw_line_fast

    # Laser Audio MMIO burst (1200 Hz, 30ms)
    li t0, 0x10000050
    li t1, 1200
    sw t1, 0(t0)
    li t1, 30
    sw t1, 4(t0)

    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# ------------------------------------------------------------------------------
# 3D Renderer: Heads-Up Display (HUD)
# ------------------------------------------------------------------------------
render_hud:
    addi sp, sp, -16
    sw ra, 12(sp)

    # 1. Target Crosshair at (320, 240)
    li a4, 0x007DCFFF
    # Horizontal crosshair: (308, 240) to (332, 240)
    li a0, 308
    li a1, 240
    li a2, 332
    li a3, 240
    call draw_line_fast

    # Vertical crosshair: (320, 228) to (320, 252)
    li a0, 320
    li a1, 228
    li a2, 320
    li a3, 252
    call draw_line_fast

    # 2. Draw HUD Banner: "STARFLIGHT 3D // AdiOS Sovereign Engine"
    la a0, hud_title_str
    li a1, 20
    li a2, 14
    li a3, 0x007AA2F7
    call draw_string

    # 3. Draw Score: "SCORE: "
    la a0, hud_score_str
    li a1, 20
    li a2, 30
    li a3, 0x00E0AF68
    call draw_string

    # Draw Score Number
    la t0, score_val
    lw a0, 0(t0)
    li a1, 80
    li a2, 30
    li a3, 0x00E0AF68
    call draw_number

    # 4. Draw Airspeed: "SPD: 420 KTS"
    la a0, hud_speed_str
    li a1, 520
    li a2, 30
    li a3, 0x009ECE6A
    call draw_string

    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# ------------------------------------------------------------------------------
# Fast Bresenham Line Drawing in Pure Assembly
# Args: a0 = x0, a1 = y0, a2 = x1, a3 = y1, a4 = color (0x00RRGGBB)
# ------------------------------------------------------------------------------
draw_line_fast:
    # dx = abs(x1 - x0)
    sub t0, a2, a0
    bgez t0, dx_pos
    neg t0, t0
dx_pos:

    # dy = -abs(y1 - y0)
    sub t1, a3, a1
    bgez t1, dy_calc
    neg t1, t1
dy_calc:
    neg t1, t1          # t1 = -abs(dy)

    # sx = 1 if x0 < x1 else -1
    li t2, 1
    blt a0, a2, sx_ok
    li t2, -1
sx_ok:

    # sy = 1 if y0 < y1 else -1
    li t3, 1
    blt a1, a3, sy_ok
    li t3, -1
sy_ok:

    # err = dx + dy
    add t4, t0, t1

line_loop:
    # Plot pixel at (a0, a1) if inside 640x480
    bltz a0, skip_plot
    li t5, 640
    bge a0, t5, skip_plot
    bltz a1, skip_plot
    li t5, 480
    bge a1, t5, skip_plot

    # Framebuffer offset = (a1 * 640 + a0) * 4
    li t5, 640
    mul t6, a1, t5
    add t6, t6, a0
    slli t6, t6, 2
    li t5, 0x20000000
    add t6, t6, t5
    sw a4, 0(t6)

skip_plot:
    beq a0, a2, check_y_end
    j continue_line
check_y_end:
    beq a1, a3, line_done

continue_line:
    slli t5, t4, 1      # e2 = 2 * err

    # if e2 >= dy: err += dy; x0 += sx
    blt t5, t1, check_e2_dx
    add t4, t4, t1
    add a0, a0, t2

check_e2_dx:
    # if e2 <= dx: err += dx; y0 += sy
    bgt t5, t0, line_loop
    add t4, t4, t0
    add a1, a1, t3
    j line_loop

line_done:
    ret

# ------------------------------------------------------------------------------
# Fast Bitmap String Drawing
# Args: a0 = string ptr, a1 = x, a2 = y, a3 = color
# ------------------------------------------------------------------------------
draw_string:
    addi sp, sp, -20
    sw ra, 16(sp)
    sw s0, 12(sp)
    sw s1, 8(sp)
    sw s2, 4(sp)
    sw s3, 0(sp)

    mv s0, a0           # string ptr
    mv s1, a1           # x
    mv s2, a2           # y
    mv s3, a3           # color

str_char_loop:
    lb a0, 0(s0)
    beqz a0, str_done
    mv a1, s1
    mv a2, s2
    mv a3, s3
    call draw_char
    addi s1, s1, 8      # advance 8px
    addi s0, s0, 1
    j str_char_loop

str_done:
    lw s3, 0(sp)
    lw s2, 4(sp)
    lw s1, 8(sp)
    lw s0, 12(sp)
    lw ra, 16(sp)
    addi sp, sp, 20
    ret

draw_char:
    # a0 = char, a1 = x, a2 = y, a3 = color
    addi a0, a0, -32
    bltz a0, char_blank
    li t0, 95
    bge a0, t0, char_blank

    # font offset = a0 * 8
    slli t0, a0, 3
    la t1, font8x8_data
    add t1, t1, t0      # t1 = bitmap ptr (8 bytes)

    li t2, 0            # row = 0..7
char_row_loop:
    lb t3, 0(t1)        # byte of row
    li t4, 0            # col = 0..7

char_col_loop:
    li t5, 7
    sub t5, t5, t4
    srl t6, t3, t5
    andi t6, t6, 1
    beqz t6, skip_char_pixel

    # Plot (a1 + t4, a2 + t2)
    add t5, a1, t4
    add t6, a2, t2
    bltz t5, skip_char_pixel
    li t0, 640
    bge t5, t0, skip_char_pixel
    bltz t6, skip_char_pixel
    li t0, 480
    bge t6, t0, skip_char_pixel

    mul t0, t6, t0
    add t0, t0, t5
    slli t0, t0, 2
    li t5, 0x20000000
    add t0, t0, t5
    sw a3, 0(t0)

skip_char_pixel:
    addi t4, t4, 1
    li t0, 8
    blt t4, t0, char_col_loop

    addi t1, t1, 1
    addi t2, t2, 1
    li t0, 8
    blt t2, t0, char_row_loop

char_blank:
    ret

draw_number:
    # Args: a0 = integer, a1 = x, a2 = y, a3 = color
    addi sp, sp, -24
    sw ra, 20(sp)
    sw s0, 16(sp)
    sw s1, 12(sp)
    sw s2, 8(sp)

    mv s0, a1
    mv s1, a2
    mv s2, a3

    # Format into decimal buffer
    la t0, num_buf
    addi t0, t0, 15
    sb zero, 0(t0)      # null terminator
    li t1, 10

    mv t2, a0
    bnez t2, num_loop
    addi t0, t0, -1
    li t3, 48           # '0'
    sb t3, 0(t0)
    j num_print

num_loop:
    beqz t2, num_print
    rem t3, t2, t1
    addi t3, t3, 48     # to ASCII
    addi t0, t0, -1
    sb t3, 0(t0)
    div t2, t2, t1
    j num_loop

num_print:
    mv a0, t0
    mv a1, s0
    mv a2, s1
    mv a3, s2
    call draw_string

    lw s2, 8(sp)
    lw s1, 12(sp)
    lw s0, 16(sp)
    lw ra, 20(sp)
    addi sp, sp, 24
    ret

print_uart:
    li t0, 0x10000000
uart_loop:
    lb t1, 0(a0)
    beqz t1, uart_done
    sw t1, 0(t0)
    addi a0, a0, 1
    j uart_loop
uart_done:
    ret

trap_handler:
    mret

# ------------------------------------------------------------------------------
# Data Section
# ------------------------------------------------------------------------------
.section .data
game_boot_msg:
    .string "[AdiOS 3D] StarFlight Bare-Metal 3D Assembly Kernel Active!\n[AdiOS 3D] 640x480 Framebuffer Initialized.\n"

hud_title_str:
    .string "STARFLIGHT 3D // AdiOS SOVEREIGN ENGINE"

hud_score_str:
    .string "SCORE:"

hud_speed_str:
    .string "SPD: 420 KTS"

# ------------------------------------------------------------------------------
# BSS Section
# ------------------------------------------------------------------------------
.section .bss
.align 4
ring_z:         .word 0
ring_x:         .word 0
ring_y:         .word 0
score_val:      .word 0
speed_val:      .word 0
terrain_scroll: .word 0

num_buf:
    .space 16
