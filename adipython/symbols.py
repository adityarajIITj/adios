#!/usr/bin/env python3
"""
The "Adam" Hierarchical Symbol Table for AdiOS & AdiPython
Inspired by Terry A. Davis's Adam Task Symbol Table in TempleOS.
Provides O(1) hash-based symbol lookups across global and task scopes.
"""

SYM_VARIABLE = 1
SYM_FUNCTION = 2
SYM_CONSTANT = 3
SYM_KEYWORD  = 4
SYM_STRUCT   = 5

class Symbol:
    def __init__(self, name, sym_type, address=0, size=4, params=None, val=None):
        self.name = name
        self.type = sym_type
        self.address = address
        self.size = size
        self.params = params or []
        self.value = val

    def __repr__(self):
        types = {1: "VAR", 2: "FUNC", 3: "CONST", 4: "KEYWORD", 5: "STRUCT"}
        t = types.get(self.type, "UNKNOWN")
        return f"Symbol({t}, '{self.name}', addr=0x{self.address:08X}, val={self.value})"

class SymbolTable:
    def __init__(self, parent=None, name="Adam"):
        self.name = name
        self.parent = parent
        self.table = {} # Hash map: name -> Symbol

    def insert(self, name, sym_type, address=0, size=4, params=None, val=None):
        sym = Symbol(name, sym_type, address, size, params, val)
        self.table[name] = sym
        return sym

    def lookup(self, name):
        """Hierarchical lookup: checks current table, then walks up to Adam Root Table."""
        if name in self.table:
            return self.table[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def exists(self, name):
        return self.lookup(name) is not None

    def all_symbols(self):
        """Returns flattened dictionary of all visible symbols."""
        res = {}
        if self.parent:
            res.update(self.parent.all_symbols())
        res.update(self.table)
        return res

def create_adam_table():
    """Initializes the Adam Root Symbol Table with all AdiOS system primitives."""
    adam = SymbolTable(name="Adam_Root")

    # System Color Constants
    adam.insert("BLACK",   SYM_CONSTANT, val=0x00000000)
    adam.insert("WHITE",   SYM_CONSTANT, val=0x00FFFFFF)
    adam.insert("RED",     SYM_CONSTANT, val=0x00F7768E)
    adam.insert("GREEN",   SYM_CONSTANT, val=0x009ECE6A)
    adam.insert("YELLOW",  SYM_CONSTANT, val=0x00E0AF68)
    adam.insert("BLUE",    SYM_CONSTANT, val=0x007AA2F7)
    adam.insert("MAGENTA", SYM_CONSTANT, val=0x00BB9AF7)
    adam.insert("CYAN",    SYM_CONSTANT, val=0x007DCFFF)

    # Hardware MMIO Addresses
    adam.insert("MMIO_UART",       SYM_CONSTANT, val=0x10000000)
    adam.insert("MMIO_TIMER",      SYM_CONSTANT, val=0x10000010)
    adam.insert("MMIO_POWER",      SYM_CONSTANT, val=0x10000040)
    adam.insert("MMIO_AUDIO_FREQ", SYM_CONSTANT, val=0x10000050)
    adam.insert("MMIO_DISK",       SYM_CONSTANT, val=0x10001000)
    adam.insert("MMIO_FB",         SYM_CONSTANT, val=0x20000000)

    # Built-in Core Functions
    adam.insert("print",  SYM_FUNCTION, params=["*args"])
    adam.insert("peek",   SYM_FUNCTION, params=["addr"])
    adam.insert("poke",   SYM_FUNCTION, params=["addr", "val"])
    adam.insert("pixel",  SYM_FUNCTION, params=["x", "y", "color"])
    adam.insert("rect",   SYM_FUNCTION, params=["x", "y", "w", "h", "color"])
    adam.insert("line",   SYM_FUNCTION, params=["x0", "y0", "x1", "y1", "color"])
    adam.insert("clear",  SYM_FUNCTION, params=["color"])
    adam.insert("tone",   SYM_FUNCTION, params=["freq", "duration"])
    adam.insert("sleep",  SYM_FUNCTION, params=["ms"])

    return adam
