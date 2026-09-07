#!/usr/bin/env python3
"""
Unit Test Suite for AdiOS Separate Sovereign Paint Studio & Programmable Graphing Calculator.
Tests:
- Paint Studio 2D vector engine drawing, tools, swatches, brush sizing, flood fill, undo/redo, export
- Programmable Graphing Calculator arithmetic, functions, variables, REPL evaluation, 2D grapher zoom/pan
Strict Zero Emoji Policy.
"""

import unittest
import os
import math
from desktop.paint_studio import PaintStudio
from desktop.calculator import ProgrammableCalculator

class TestPaintStudioAndCalculator(unittest.TestCase):
    def setUp(self):
        self.paint = PaintStudio(x=10, y=10, w=680, h=500)
        self.calc = ProgrammableCalculator(x=20, y=20, w=720, h=490)
        self.fb = bytearray(1280 * 720 * 4)

    # --------------------------------------------------------------------------
    # Paint Studio Tests
    # --------------------------------------------------------------------------

    def test_01_paint_initialization_and_rendering(self):
        """Verify PaintStudio initializes with 2D vector canvas and renders."""
        self.assertEqual(self.paint.win_id, "paint")
        self.assertEqual(self.paint.active_tool, "brush")
        self.assertEqual(self.paint.canvas_w, 460)
        self.assertEqual(self.paint.canvas_h, 360)
        self.paint.on_draw_content(self.paint, self.fb, {})
        # Framebuffer must have been populated
        self.assertTrue(any(b != 0 for b in self.fb))

    def test_02_paint_tool_switching(self):
        """Verify selecting tools on dock updates active_tool."""
        # Click Pencil at row 0, col 0 (rel_x=12, rel_y=25)
        self.paint.handle_click_content(self.paint, 12, 25)
        self.assertEqual(self.paint.active_tool, "pencil")

        # Click Eraser at row 1, col 0 (rel_x=12, rel_y=48)
        self.paint.handle_click_content(self.paint, 12, 48)
        self.assertEqual(self.paint.active_tool, "eraser")

        # Click Line at row 1, col 1 (rel_x=52, rel_y=48)
        self.paint.handle_click_content(self.paint, 52, 48)
        self.assertEqual(self.paint.active_tool, "line")

    def test_03_paint_brush_sizes_and_colors(self):
        """Verify brush sizes and palette swatches."""
        # Click size 6px (index 2: rel_x = 8 + 2*16 = 40, rel_y = 145)
        self.paint.handle_click_content(self.paint, 40, 145)
        self.assertEqual(self.paint.brush_size, 6)

        # Click Swatch (idx 3: Emerald Jade 0x009ECE6A at rel_x = 106 + 3*26 = 184, rel_y = 15)
        self.paint.handle_click_content(self.paint, 184, 15)
        self.assertEqual(self.paint.active_color, 0x009ECE6A)

    def test_04_paint_stroke_and_undo_redo(self):
        """Verify canvas stroke drawing and multi-level undo/redo stack."""
        # Draw stroke at canvas coordinate (150, 100) -> rel_x = 106 + 150 = 256, rel_y = 38 + 100 = 138
        self.paint.handle_click_content(self.paint, 256, 138)
        self.assertGreaterEqual(len(self.paint.undo_stack), 1)

        # Verify pixel color on canvas
        pixel_col = self.paint.canvas.get_pixel(150, 100)
        self.assertEqual(pixel_col & 0x00FFFFFF, self.paint.active_color & 0x00FFFFFF)

        # Undo stroke
        self.paint.undo()
        self.assertEqual(len(self.paint.redo_stack), 1)

        # Redo stroke
        self.paint.redo()
        pixel_col_redo = self.paint.canvas.get_pixel(150, 100)
        self.assertEqual(pixel_col_redo & 0x00FFFFFF, self.paint.active_color & 0x00FFFFFF)

    def test_05_paint_export_storage(self):
        """Verify saving artwork to storage/paint/."""
        test_path = "storage/paint/test_art.ppm"
        if os.path.exists(test_path):
            os.remove(test_path)
        self.paint.save_artwork(test_path)
        self.assertTrue(os.path.exists(test_path))
        self.assertGreater(os.path.getsize(test_path), 100)
        # Cleanup test artifact
        os.remove(test_path)

    # --------------------------------------------------------------------------
    # Programmable Graphing Calculator Tests
    # --------------------------------------------------------------------------

    def test_06_calculator_initialization_and_rendering(self):
        """Verify calculator initializes and renders dual panes."""
        self.assertEqual(self.calc.win_id, "calc")
        self.assertEqual(self.calc.calc_display, "0")
        self.calc.on_draw_content(self.calc, self.fb, {})
        self.assertTrue(any(b != 0 for b in self.fb))

    def test_07_calculator_arithmetic_operations(self):
        """Verify standard & scientific arithmetic key operations."""
        # 9 * 8 = 72
        self.calc.handle_calc_key("9")
        self.assertEqual(self.calc.calc_display, "9")
        self.calc.handle_calc_key("*")
        self.calc.handle_calc_key("8")
        self.calc.handle_calc_key("=")
        self.assertEqual(self.calc.calc_display, "72")

        # SQRT(144) = 12
        self.calc.handle_calc_key("C")
        self.calc.handle_calc_key("1")
        self.calc.handle_calc_key("4")
        self.calc.handle_calc_key("4")
        self.calc.handle_calc_key("SQRT")
        self.assertEqual(self.calc.calc_display, "12")

    def test_08_calculator_memory_registers(self):
        """Verify M+, MR, M-, MC memory registers."""
        self.calc.handle_calc_key("5")
        self.calc.handle_calc_key("0")
        self.calc.handle_calc_key("M+")
        self.assertEqual(self.calc.memory, 50.0)

        self.calc.handle_calc_key("C")
        self.assertEqual(self.calc.calc_display, "0")
        self.calc.handle_calc_key("MR")
        self.assertEqual(self.calc.calc_display, "50.0")

        self.calc.handle_calc_key("MC")
        self.assertEqual(self.calc.memory, 0.0)

    def test_09_calculator_programmable_repl(self):
        """Verify programmable assignment, math expressions, and variable table."""
        # Variable assignment: radius = 10
        self.calc.execute_prog_line("radius = 10")
        self.assertIn("radius", self.calc.variables)
        self.assertEqual(self.calc.variables["radius"], 10.0)

        # Compound expression using assigned variable and built-in constant pi
        self.calc.execute_prog_line("area = pi * radius**2")
        self.assertIn("area", self.calc.variables)
        expected_area = math.pi * 100.0
        self.assertAlmostEqual(self.calc.variables["area"], expected_area, places=4)

    def test_10_calculator_graphing_engine(self):
        """Verify 2D function grapher curve evaluation, presets, and zoom/pan."""
        # Switch function preset to cos(x)
        self.calc.func_str = "cos(x)"
        res_0 = self.calc._eval_math(self.calc.func_str, x_val=0.0)
        self.assertAlmostEqual(res_0, 1.0, places=5)

        res_pi = self.calc._eval_math(self.calc.func_str, x_val=math.pi)
        self.assertAlmostEqual(res_pi, -1.0, places=5)

        # Test Zoom In
        orig_range = self.calc.x_max - self.calc.x_min
        # Click zoom in button (+) in right pane: rel_x = 310 + 10 = 320, rel_y = 350
        self.calc.handle_click_content(self.calc, 320, 350)
        new_range = self.calc.x_max - self.calc.x_min
        self.assertLess(new_range, orig_range)

if __name__ == "__main__":
    unittest.main()
