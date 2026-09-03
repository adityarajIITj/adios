"""
AdiPython Standard Library Package
"""
import os

STDLIB_DIR = os.path.dirname(__file__)

def get_stdlib_path(name):
    return os.path.join(STDLIB_DIR, name)
