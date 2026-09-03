import sys
import os

sys.path.insert(0, os.path.abspath("vm"))
from vm import VM

def run_commands(commands):
    v = VM()
    v.load_binary("adios.bin")
    
    # Let it boot
    for _ in range(15000):
        v.step()

    for cmd in commands:
        # Feed command characters
        for ch in cmd + "\n":
            v.push_input(ord(ch))
        # Step through execution
        for _ in range(30000):
            v.step()

if __name__ == "__main__":
    test_cmds = ["help", "info", "mem", "ps", "spawn", "disk", "ls", "matrix"]
    run_commands(test_cmds)
