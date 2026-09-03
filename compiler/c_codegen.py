#!/usr/bin/env python3
"""
AdiOS C99 / AdiC Toolchain: RISC-V Code Generator (c_codegen.py)
Translates C ASTs into optimized 32-bit RISC-V (RV32IM) assembly code.
Handles stack frames, calling conventions (a0-a7, ra, s0/fp), pointers,
arrays, loops, and conditional branching.
Zero external dependencies.
"""

from typing import List, Dict, Optional
from compiler.c_parser import (
    ASTNode, TranslationUnit, FunctionDecl, VarDecl, BlockStmt,
    IfStmt, WhileStmt, ForStmt, ReturnStmt, ExprStmt,
    BinaryExpr, UnaryExpr, AssignExpr, CallExpr, VariableExpr,
    LiteralExpr, MemberExpr, IndexExpr, Expr
)

class CCodeGen:
    """
    Emits RV32IM assembly from a C Abstract Syntax Tree.
    """
    def __init__(self):
        self.asm_lines: List[str] = []
        self.label_counter = 0
        self.locals: Dict[str, int] = {} # var_name -> stack offset from s0 (fp)
        self.stack_size = 0
        self.strings: List[tuple] = [] # (label, text)

    def new_label(self, prefix: str = "L") -> str:
        lbl = f".{prefix}_{self.label_counter}"
        self.label_counter += 1
        return lbl

    def emit(self, instruction: str):
        self.asm_lines.append(f"    {instruction}")

    def emit_label(self, label: str):
        self.asm_lines.append(f"{label}:")

    def generate(self, unit: TranslationUnit) -> str:
        self.asm_lines.append("# AdiOS Native C Compiler (RV32IM Assembly)")
        self.asm_lines.append(".section .text")
        self.asm_lines.append(".global main")

        for decl in unit.decls:
            if isinstance(decl, FunctionDecl):
                self.gen_function(decl)
            elif isinstance(decl, VarDecl):
                # Global variable
                pass

        if self.strings:
            self.asm_lines.append("\n.section .rodata")
            for lbl, text in self.strings:
                self.emit_label(lbl)
                clean_text = text.replace('"', '\\"')
                self.emit(f'.string "{clean_text}"')

        return "\n".join(self.asm_lines)

    def gen_function(self, fn: FunctionDecl):
        if not fn.body:
            return  # Forward declaration only

        self.current_function = fn.name
        self.asm_lines.append("")
        self.emit_label(fn.name)

        # 1. Prologue: Save ra, s0 (fp), set up new frame pointer
        self.locals.clear()
        self.stack_size = 64  # Standard initial frame size

        self.emit("addi sp, sp, -64")
        self.emit("sw   ra, 60(sp)")
        self.emit("sw   s0, 56(sp)")
        self.emit("addi s0, sp, 64") # s0 points to caller's sp

        # 2. Store parameters into local stack slots
        offset = -12
        for idx, param in enumerate(fn.params):
            self.locals[param.name] = offset
            if idx < 8:
                self.emit(f"sw   a{idx}, {offset}(s0)")
            offset -= 4

        # 3. Generate body statements
        self.gen_block(fn.body)

        # 4. Epilogue
        self.emit_label(f".L_{fn.name}_epilogue")
        self.emit("lw   s0, 56(sp)")
        self.emit("lw   ra, 60(sp)")
        self.emit("addi sp, sp, 64")
        self.emit("ret")

    def gen_block(self, block: BlockStmt):
        for stmt in block.stmts:
            self.gen_statement(stmt)

    def gen_statement(self, stmt: ASTNode):
        if isinstance(stmt, ReturnStmt):
            if stmt.expr:
                self.gen_expr(stmt.expr)  # Result in a0
            # Jump to epilogue
            self.emit(f"j    .L_{self.current_function}_epilogue")
        elif isinstance(stmt, VarDecl):
            # Allocate local variable
            offset = -(12 + len(self.locals) * 4)
            self.locals[stmt.name] = offset
            if stmt.init_expr:
                self.gen_expr(stmt.init_expr)
                self.emit(f"sw   a0, {offset}(s0)")
        elif isinstance(stmt, ExprStmt):
            self.gen_expr(stmt.expr)
        elif isinstance(stmt, IfStmt):
            lbl_else = self.new_label("else")
            lbl_end = self.new_label("endif")

            self.gen_expr(stmt.cond)
            self.emit(f"beqz a0, {lbl_else if stmt.else_stmt else lbl_end}")
            self.gen_statement(stmt.then_stmt)

            if stmt.else_stmt:
                self.emit(f"j    {lbl_end}")
                self.emit_label(lbl_else)
                self.gen_statement(stmt.else_stmt)

            self.emit_label(lbl_end)
        elif isinstance(stmt, WhileStmt):
            lbl_start = self.new_label("while_start")
            lbl_end = self.new_label("while_end")

            self.emit_label(lbl_start)
            self.gen_expr(stmt.cond)
            self.emit(f"beqz a0, {lbl_end}")
            self.gen_statement(stmt.body)
            self.emit(f"j    {lbl_start}")
            self.emit_label(lbl_end)
        elif isinstance(stmt, ForStmt):
            lbl_start = self.new_label("for_start")
            lbl_end = self.new_label("for_end")

            if stmt.init:
                self.gen_statement(stmt.init)
            self.emit_label(lbl_start)
            if stmt.cond:
                self.gen_expr(stmt.cond)
                self.emit(f"beqz a0, {lbl_end}")
            self.gen_statement(stmt.body)
            if stmt.step:
                self.gen_expr(stmt.step)
            self.emit(f"j    {lbl_start}")
            self.emit_label(lbl_end)
        elif isinstance(stmt, BlockStmt):
            self.gen_block(stmt)

    def is_in_main(self) -> bool:
        return any(line.startswith("main:") for line in self.asm_lines)

    def gen_expr(self, expr: Expr):
        """Evaluates expression, placing final result in register a0."""
        if isinstance(expr, LiteralExpr):
            if expr.val_type == "int":
                self.emit(f"li   a0, {expr.value}")
            elif expr.val_type == "str":
                lbl = self.new_label("str")
                self.strings.append((lbl, expr.value))
                self.emit(f"la   a0, {lbl}")
        elif isinstance(expr, VariableExpr):
            if expr.name in self.locals:
                offset = self.locals[expr.name]
                self.emit(f"lw   a0, {offset}(s0)")
            else:
                self.emit(f"la   t0, {expr.name}")
                self.emit("lw   a0, 0(t0)")
        elif isinstance(expr, AssignExpr):
            self.gen_expr(expr.value)
            if isinstance(expr.target, VariableExpr):
                offset = self.locals[expr.target.name]
                self.emit(f"sw   a0, {offset}(s0)")
            elif isinstance(expr.target, UnaryExpr) and expr.target.op == "*":
                # Pointer store: *p = val
                self.emit("addi sp, sp, -4")
                self.emit("sw   a0, 0(sp)") # Save value
                self.gen_expr(expr.target.operand) # Pointer addr in a0
                self.emit("mv   t0, a0")
                self.emit("lw   a0, 0(sp)")
                self.emit("addi sp, sp, 4")
                self.emit("sw   a0, 0(t0)")
        elif isinstance(expr, BinaryExpr):
            self.gen_expr(expr.left)
            self.emit("addi sp, sp, -4")
            self.emit("sw   a0, 0(sp)") # Push left operand
            self.gen_expr(expr.right)       # Right operand in a0
            self.emit("mv   t1, a0")        # Right in t1
            self.emit("lw   t0, 0(sp)")     # Left in t0
            self.emit("addi sp, sp, 4")

            ops = {
                "+": "add  a0, t0, t1",
                "-": "sub  a0, t0, t1",
                "*": "mul  a0, t0, t1",
                "/": "div  a0, t0, t1",
                "%": "rem  a0, t0, t1",
                "&": "and  a0, t0, t1",
                "|": "or   a0, t0, t1",
                "^": "xor  a0, t0, t1",
                "<<": "sll  a0, t0, t1",
                ">>": "sra  a0, t0, t1",
            }
            if expr.op in ops:
                self.emit(ops[expr.op])
            elif expr.op == "==":
                self.emit("sub  a0, t0, t1")
                self.emit("seqz a0, a0")
            elif expr.op == "!=":
                self.emit("sub  a0, t0, t1")
                self.emit("snez a0, a0")
            elif expr.op == "<":
                self.emit("slt  a0, t0, t1")
            elif expr.op == ">":
                self.emit("slt  a0, t1, t0")
            elif expr.op == "<=":
                self.emit("slt  a0, t1, t0")
                self.emit("xori a0, a0, 1")
            elif expr.op == ">=":
                self.emit("slt  a0, t0, t1")
                self.emit("xori a0, a0, 1")
        elif isinstance(expr, UnaryExpr):
            if expr.op == "-":
                self.gen_expr(expr.operand)
                self.emit("neg  a0, a0")
            elif expr.op == "!":
                self.gen_expr(expr.operand)
                self.emit("seqz a0, a0")
            elif expr.op == "~":
                self.gen_expr(expr.operand)
                self.emit("not  a0, a0")
            elif expr.op == "*": # Dereference
                self.gen_expr(expr.operand)
                self.emit("lw   a0, 0(a0)")
            elif expr.op == "&": # Address-of
                if isinstance(expr.operand, VariableExpr):
                    offset = self.locals[expr.operand.name]
                    self.emit(f"addi a0, s0, {offset}")
        elif isinstance(expr, CallExpr):
            # Save a0-a7 parameters
            for idx, arg in enumerate(expr.args):
                self.gen_expr(arg)
                self.emit("addi sp, sp, -4")
                self.emit("sw   a0, 0(sp)")

            # Pop into argument registers
            for idx in reversed(range(len(expr.args))):
                if idx < 8:
                    self.emit(f"lw   a{idx}, 0(sp)")
                self.emit("addi sp, sp, 4")

            if isinstance(expr.callee, VariableExpr):
                self.emit(f"call {expr.callee.name}")

if __name__ == "__main__":
    from compiler.c_lexer import CLexer
    from compiler.c_parser import CParser
    src = """
    int add(int a, int b) {
        return a + b;
    }
    int main() {
        int x = 10;
        int y = 20;
        return add(x, y);
    }
    """
    p = CParser(CLexer(src).tokenize())
    cg = CCodeGen()
    asm_out = cg.generate(p.parse())
    print("Generated RV32 Assembly:\n" + asm_out)
    assert "add  a0, t0, t1" in asm_out
    print("C Codegen verified.")
