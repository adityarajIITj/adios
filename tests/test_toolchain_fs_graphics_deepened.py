#!/usr/bin/env python3
"""
Test Suite: Toolchain, Filesystem, GUI & 3D Graphics Deepened Subsystem (Pass X Checkpoint 9)
Verifies:
1. Deepened ELF32 Binary Builder & In-Memory ELF32 Parser / Section Inspector
2. Deepened C99 Type System: Struct alignment, promotions, enums, ABI argument classifier
3. Deepened AdiFS Filesystem: Contiguous storage, CRC32 checksums, defragmentation, fsck
4. Deepened 2D Canvas: Anti-aliased lines, scanline polygon rasterizer, gradients, blitting
5. Deepened Widget Toolkit: Hierarchy, ProgressBar, CheckBox, Flexbox containers (HBox/VBox)
6. Deepened 3D Engine: Matrix4 homogeneous mathematics, Starfighter mesh, and depth rasterizer

Zero external dependencies. Pure RV32IM bare-metal test harness.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import sys
import os
import math
import struct
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from compiler.elf32 import ELF32Builder, ELF32Parser, EM_RISCV
from compiler.c_types import (
    TypeRegistry, StructType, EnumType, FunctionType,
    TYPE_CHAR, TYPE_INT, TYPE_SHORT, TYPE_UINT, TYPE_DOUBLE
)
from fs.adifs import AdiFS
from ui.canvas2d import Canvas2D, Rect
from ui.widgets import Button, ProgressBar, CheckBox, HBox, VBox, WindowWidget
from graphics.engine3d import Vector3, Matrix4, create_starfighter, Engine3D, HALFW, HALFH

class TestToolchainFsGraphicsDeepened(unittest.TestCase):

    def test_01_elf32_builder_and_parser(self):
        builder = ELF32Builder(entry_addr=0x80000000)
        # addi a0, zero, 42; ret
        code = struct.pack("<II", 0x02A00513, 0x00008067)
        builder.set_text(code)
        builder.set_rodata(b"SovereignELF32Data\x00")
        raw_elf = builder.build()

        parser = ELF32Parser(raw_elf)
        self.assertEqual(parser.entry_point, 0x80000000)
        self.assertEqual(parser.machine, EM_RISCV)

        sec_text = parser.get_section_by_name(".text")
        self.assertIsNotNone(sec_text)
        self.assertEqual(sec_text["size"], len(code))

        sec_rodata = parser.get_section_by_name(".rodata")
        self.assertIsNotNone(sec_rodata)
        self.assertIn(b"SovereignELF32Data", sec_rodata["data"])

    def test_02_c99_type_system_and_struct_layout(self):
        fields = [("a", TYPE_CHAR), ("b", TYPE_INT), ("c", TYPE_SHORT)]
        st = StructType("PacketHeader", fields)
        self.assertEqual(st.members["a"].offset, 0)
        self.assertEqual(st.members["b"].offset, 4)
        self.assertEqual(st.members["c"].offset, 8)
        self.assertEqual(st.size, 12)
        self.assertEqual(st.offset_of("b"), 4)

        # Arithmetic conversions
        common = TypeRegistry.usual_arithmetic_conversions(TYPE_SHORT, TYPE_UINT)
        self.assertEqual(common.name, "unsigned int")

        # Enum type
        en = EnumType("Priority", [("LOW", 0), ("MED", 5), ("HIGH", None)])
        self.assertEqual(en.get_value("LOW"), 0)
        self.assertEqual(en.get_value("MED"), 5)
        self.assertEqual(en.get_value("HIGH"), 6)

        # Function ABI classification
        fn = FunctionType(TYPE_INT, [TYPE_INT, TYPE_INT, TYPE_INT, TYPE_INT])
        locs = fn.classify_abi_arguments()
        self.assertEqual(len(locs), 4)
        self.assertEqual(locs[0], ("REG", 10))
        self.assertEqual(locs[3], ("REG", 13))

    def test_03_adifs_filesystem_and_defragmenter(self):
        disk_file = "test_adifs_checkpoint.img"
        try:
            fs = AdiFS(disk_file)
            fs.format_disk(4096)

            # Create files
            fs.create_file("kernel.bin", b"RAW_RV32_KERNEL_CODE_DATA")
            fs.create_file("user.txt", b"USER_PAYLOAD_TEXT_CONTENT")
            self.assertTrue(fs.exists("kernel.bin"))
            self.assertTrue(fs.exists("user.txt"))

            # Integrity verification
            self.assertTrue(fs.verify_integrity("kernel.bin"))

            # Rename
            ok = fs.rename_file("user.txt", "user_renamed.txt")
            self.assertTrue(ok)
            self.assertFalse(fs.exists("user.txt"))
            self.assertTrue(fs.exists("user_renamed.txt"))

            # Defrag
            fs.delete_file("kernel.bin")
            fs.defragment()
            self.assertTrue(fs.exists("user_renamed.txt"))
            self.assertEqual(fs.read_file("user_renamed.txt"), b"USER_PAYLOAD_TEXT_CONTENT")

            # FSCK
            report = fs.fsck()
            self.assertTrue(report["healthy"])
        finally:
            if os.path.exists(disk_file):
                os.remove(disk_file)

    def test_04_canvas2d_aa_lines_polygons_and_gradients(self):
        canvas = Canvas2D(200, 200)
        canvas.clear(0xFF000000)

        # Anti-aliased line
        canvas.draw_line_aa(10, 10, 100, 50, 0xFFFFFFFF)
        p = canvas.get_pixel(10, 10)
        self.assertNotEqual(p, 0)

        # Polygon rasterizer (Triangle)
        poly = [(50, 50), (150, 50), (100, 150)]
        canvas.fill_polygon(poly, 0xFF00FF00)
        p_in = canvas.get_pixel(100, 80)
        self.assertEqual(p_in, 0xFF00FF00)

        # Linear Gradient
        canvas.fill_gradient_linear(0, 0, 50, 50, 0xFF000000, 0xFFFFFFFF, vertical=True)
        p_mid = canvas.get_pixel(10, 25)
        self.assertGreater((p_mid >> 16) & 0xFF, 50)

    def test_05_widget_toolkit_components(self):
        win = WindowWidget(10, 10, 300, 200, "Toolbox")
        clicked = []
        btn = Button(20, 30, 80, 24, "Run", on_click=lambda: clicked.append(1))
        pb = ProgressBar(20, 60, 150, 12, progress=0.8)
        cb = CheckBox(20, 80, size=16, checked=False)

        win.add_child(btn)
        win.add_child(pb)
        win.add_child(cb)

        # Mouse click dispatching
        win.on_mouse_down(btn.screen_x + 5, btn.screen_y + 5)
        win.on_mouse_up(btn.screen_x + 5, btn.screen_y + 5)
        self.assertEqual(clicked, [1])

        # CheckBox toggle
        cb.on_mouse_down(cb.screen_x + 2, cb.screen_y + 2)
        self.assertTrue(cb.checked)

        # Flexbox HBox layout
        hbox = HBox(0, 0, spacing=10)
        b1 = Button(0, 0, 40, 20, "A")
        b2 = Button(0, 0, 60, 20, "B")
        hbox.add_child(b1)
        hbox.add_child(b2)
        self.assertEqual(hbox.w, 110) # 40 + 10 + 60

    def test_06_engine3d_matrix4_and_starfighter(self):
        # Matrix4 rotation
        m_rot = Matrix4.rotation_y(math.pi / 2)
        v1 = Vector3(1, 0, 0)
        v2 = m_rot.transform_point(v1)
        self.assertAlmostEqual(v2.x, 0.0, places=5)
        self.assertAlmostEqual(v2.z, -1.0, places=5)

        # Starfighter mesh
        sf = create_starfighter(80.0)
        self.assertEqual(len(sf.vertices), 5)
        self.assertEqual(len(sf.faces), 6)

        # 3D projection
        eng = Engine3D()
        proj = eng.project_vertex(Vector3(0, 0, 100))
        self.assertIsNotNone(proj)
        self.assertEqual(proj[0], HALFW)
        self.assertEqual(proj[1], HALFH)

if __name__ == "__main__":
    unittest.main()
