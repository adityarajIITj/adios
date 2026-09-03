import sys
import os

sys.path.insert(0, os.path.abspath("vm"))
from vm import VM

v = VM()
v.load_binary("adios.bin")
prev_pc = v.pc
for i in range(10000):
    prev_pc = v.pc
    if not v.step():
        print(f"Halted at step {i}, prev PC: 0x{prev_pc:08X}, current PC: 0x{v.pc:08X}")
        break
    if v.pc == 0:
        print(f"Jumped to 0 at step {i}! Prev PC: 0x{prev_pc:08X}")
        print(f"Registers:")
        for r_idx, reg_val in enumerate(v.regs):
            print(f"x{r_idx}: 0x{reg_val:08X} ", end="\n" if r_idx % 4 == 3 else "")
        print()
        break
