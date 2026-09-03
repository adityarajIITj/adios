#!/usr/bin/env python3
"""
AdiOS Compiler Intermediate Representation (IR / TAC)
Three-Address Code (TAC) and Control Flow Graph (CFG) for Native Optimization.
Inspired by modern SSA intermediate representations and Terry A. Davis's HolyC IR.
"""

from typing import List, Dict, Optional, Any

# IR Operation Opcodes
IR_NOP          = "NOP"
IR_LABEL        = "LABEL"
IR_MOVE         = "MOVE"          # dest = src1
IR_ADD          = "ADD"           # dest = src1 + src2
IR_SUB          = "SUB"           # dest = src1 - src2
IR_MUL          = "MUL"           # dest = src1 * src2
IR_DIV          = "DIV"           # dest = src1 / src2
IR_REM          = "REM"           # dest = src1 % src2
IR_AND          = "AND"           # dest = src1 & src2
IR_OR           = "OR"            # dest = src1 | src2
IR_XOR          = "XOR"           # dest = src1 ^ src2
IR_SHL          = "SHL"           # dest = src1 << src2
IR_SHR          = "SHR"           # dest = src1 >> src2

# Comparisons
IR_EQ           = "EQ"            # dest = (src1 == src2)
IR_NE           = "NE"            # dest = (src1 != src2)
IR_LT           = "LT"            # dest = (src1 < src2)
IR_LE           = "LE"            # dest = (src1 <= src2)
IR_GT           = "GT"            # dest = (src1 > src2)
IR_GE           = "GE"            # dest = (src1 >= src2)

# Memory & MMIO
IR_PEEK         = "PEEK"          # dest = peek(src1)
IR_POKE         = "POKE"          # poke(src1, src2)
IR_ALLOCA       = "ALLOCA"        # dest = stack_alloc(size)

# Control Flow
IR_JUMP         = "JUMP"          # jump label
IR_JUMP_IF      = "JUMP_IF"       # if src1 != 0 jump label
IR_JUMP_IF_NOT  = "JUMP_IF_NOT"   # if src1 == 0 jump label
IR_CALL         = "CALL"          # dest = call func(args)
IR_PARAM        = "PARAM"         # param src1
IR_RETURN       = "RETURN"        # return src1

class IROperand:
    """Represents a virtual register, constant literal, or symbol."""
    def __init__(self, kind: str, value: Any):
        self.kind = kind          # "REG", "CONST", "LABEL", "SYM"
        self.value = value

    @staticmethod
    def reg(reg_id: int) -> 'IROperand':
        return IROperand("REG", reg_id)

    @staticmethod
    def const(val: int) -> 'IROperand':
        return IROperand("CONST", val)

    @staticmethod
    def label(lbl_name: str) -> 'IROperand':
        return IROperand("LABEL", lbl_name)

    @staticmethod
    def sym(sym_name: str) -> 'IROperand':
        return IROperand("SYM", sym_name)

    def is_reg(self) -> bool:
        return self.kind == "REG"

    def is_const(self) -> bool:
        return self.kind == "CONST"

    def __repr__(self) -> str:
        if self.kind == "REG":
            return f"%v{self.value}"
        elif self.kind == "CONST":
            return f"${self.value}"
        elif self.kind == "LABEL":
            return f".L{self.value}"
        return str(self.value)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, IROperand): return False
        return self.kind == other.kind and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.kind, self.value))

class IRInstruction:
    """A single Three-Address Code (TAC) instruction."""
    def __init__(self, op: str, dest: Optional[IROperand] = None,
                 src1: Optional[IROperand] = None, src2: Optional[IROperand] = None):
        self.op = op
        self.dest = dest
        self.src1 = src1
        self.src2 = src2

    def __repr__(self) -> str:
        if self.op == IR_LABEL:
            return f"{self.dest}:"
        elif self.op in (IR_JUMP,):
            return f"    {self.op} {self.dest}"
        elif self.op in (IR_JUMP_IF, IR_JUMP_IF_NOT):
            return f"    {self.op} {self.src1}, {self.dest}"
        elif self.op == IR_RETURN:
            return f"    {self.op} {self.src1 or ''}"
        elif self.op == IR_PARAM:
            return f"    {self.op} {self.src1}"
        elif self.op == IR_POKE:
            return f"    {self.op} [{self.src1}], {self.src2}"
        elif self.op == IR_MOVE:
            return f"    {self.dest} = {self.src1}"
        elif self.src2 is not None:
            return f"    {self.dest} = {self.op} {self.src1}, {self.src2}"
        elif self.src1 is not None:
            return f"    {self.dest} = {self.op} {self.src1}"
        return f"    {self.op}"

class IRBasicBlock:
    """A sequence of linear IR instructions with single entry and exit."""
    def __init__(self, label: str):
        self.label = label
        self.instructions: List[IRInstruction] = []
        self.predecessors: List['IRBasicBlock'] = []
        self.successors: List['IRBasicBlock'] = []

    def add_instruction(self, inst: IRInstruction):
        self.instructions.append(inst)

    def is_terminated(self) -> bool:
        if not self.instructions: return False
        last_op = self.instructions[-1].op
        return last_op in (IR_JUMP, IR_RETURN)

    def __repr__(self) -> str:
        lines = [f"{self.label}:"]
        for inst in self.instructions:
            lines.append(str(inst))
        return "\n".join(lines)

class IRFunction:
    """Control Flow Graph (CFG) of basic blocks representing a function."""
    def __init__(self, name: str, params: List[str]):
        self.name = name
        self.params = params
        self.blocks: List[IRBasicBlock] = []
        self.entry_block: Optional[IRBasicBlock] = None
        self.reg_counter = 0
        self.label_counter = 0

    def new_reg(self) -> IROperand:
        r = IROperand.reg(self.reg_counter)
        self.reg_counter += 1
        return r

    def new_label(self, prefix: str = "L") -> str:
        lbl = f"{prefix}_{self.name}_{self.label_counter}"
        self.label_counter += 1
        return lbl

    def create_block(self, label: Optional[str] = None) -> IRBasicBlock:
        if label is None:
            label = self.new_label("bb")
        block = IRBasicBlock(label)
        self.blocks.append(block)
        if self.entry_block is None:
            self.entry_block = block
        return block

    def linear_instructions(self) -> List[IRInstruction]:
        result = []
        for bb in self.blocks:
            result.append(IRInstruction(IR_LABEL, IROperand.label(bb.label)))
            result.extend(bb.instructions)
        return result

    def __repr__(self) -> str:
        header = f"fn {self.name}({', '.join(self.params)}):"
        blocks_str = "\n".join(str(b) for b in self.blocks)
        return f"{header}\n{blocks_str}\n"

class IRModule:
    """A collection of IR functions and global data definitions."""
    def __init__(self, name: str = "module"):
        self.name = name
        self.functions: Dict[str, IRFunction] = {}
        self.globals: Dict[str, Any] = {}

    def add_function(self, func: IRFunction):
        self.functions[func.name] = func

    def __repr__(self) -> str:
        funcs = "\n".join(str(f) for f in self.functions.values())
        return f"; Module: {self.name}\n{funcs}"
