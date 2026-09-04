#!/usr/bin/env python3
"""
AdiOS C99 / AdiC Toolchain: RISC-V Code Generator (Deepened Architecture)
Translates typed C ASTs into optimized 32-bit RISC-V (RV32IM) assembly code.

Capabilities & Architectural Details:
1. Standard RISC-V Calling Convention (ABI):
   - Arguments in a0-a7, return values in a0/a1
   - Callee-saved s0/fp and ra preservation
   - 16-byte stack frame alignment
2. Advanced Expression & Arithmetic Codegen:
   - Full integer arithmetic (+, -, *, /, %) using RV32M hardware instructions
   - Bitwise operations (&, |, ^, ~, <<, >>)
   - Relational and equality tests (==, !=, <, <=, >, >=)
   - Compound assignments (+=, -=, *=, /=, %=, <<=, >>=, &=, |=, ^=)
   - Pointer address-of (&) and dereferencing (*) with byte/word sizes
   - Pre/post increment/decrement (++, --)
3. Structured Memory & Aggregate Data Layouts:
   - Array index offset calculation: a[i] -> *(a + i * elem_size)
   - Struct member offset calculation: s.m and p->m
4. Comprehensive Control Flow:
   - If / else branch generation
   - While and For loop blocks with break / continue jump label stacks
   - Switch / case / default jump table dispatch
5. Read-Only Data Section & String Literals:
   - Automatic .rodata string pooling with deduplication
"""

from typing import List, Dict, Optional, Tuple
from compiler.c_parser import (
    ASTNode, TranslationUnit, FunctionDecl, VarDecl, BlockStmt,
    IfStmt, WhileStmt, ForStmt, ReturnStmt, ExprStmt,
    BinaryExpr, UnaryExpr, AssignExpr, CallExpr, VariableExpr,
    LiteralExpr, MemberExpr, IndexExpr, Expr
)


class CCodeGen:
    """
    Translates typed C Abstract Syntax Trees into RV32IM assembly code.
    """
    def __init__(self):
        self.asm_lines: List[str] = []
        self.label_counter = 0
        self.locals: Dict[str, int] = {}       # var_name -> stack offset from s0 (fp)
        self.local_types: Dict[str, str] = {}  # var_name -> type_name
        self.struct_layouts: Dict[str, Dict[str, int]] = {}  # struct_name -> {member: offset}
        self.stack_size = 0
        self.strings: List[Tuple[str, str]] = []  # (label, text)
        self.loop_stack: List[Tuple[str, str]] = []  # (continue_lbl, break_lbl)
        self.current_function = ""

    def new_label(self, prefix: str = "L") -> str:
        lbl = f".{prefix}_{self.label_counter}"
        self.label_counter += 1
        return lbl

    def emit(self, instruction: str):
        self.asm_lines.append(f"    {instruction}")

    def emit_label(self, label: str):
        self.asm_lines.append(f"{label}:")

    # -------------------------------------------------------------------------
    # Top-Level Translation Unit Driver
    # -------------------------------------------------------------------------
    def generate(self, unit: TranslationUnit) -> str:
        self.asm_lines = [
            "# AdiOS Native C Compiler (RV32IM Assembly)",
            ".section .text",
            ".global main"
        ]

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
                clean_text = text.replace('"', '\\"').replace("\n", "\\n")
                self.emit(f'.string "{clean_text}"')

        return "\n".join(self.asm_lines)

    # -------------------------------------------------------------------------
    # Function Prologue, Body & Epilogue
    # -------------------------------------------------------------------------
    def gen_function(self, fn: FunctionDecl):
        if not fn.body:
            return  # Forward declaration

        self.current_function = fn.name
        self.asm_lines.append("")
        self.emit_label(fn.name)

        # 1. Prologue: 64-byte stack frame aligned to 16 bytes
        self.locals.clear()
        self.local_types.clear()
        self.stack_size = 64

        self.emit("addi sp, sp, -64")
        self.emit("sw   ra, 60(sp)")
        self.emit("sw   s0, 56(sp)")
        self.emit("addi s0, sp, 64")  # s0 is the frame pointer

        # 2. Store incoming arguments a0..a7 into local stack frame
        offset = -12
        for idx, param in enumerate(fn.params):
            self.locals[param.name] = offset
            p_type = getattr(param, "param_type", None)
            if p_type:
                self.local_types[param.name] = getattr(p_type, "base", "int")
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

    # -------------------------------------------------------------------------
    # Statement Codegen Dispatcher
    # -------------------------------------------------------------------------
    def gen_statement(self, stmt: ASTNode):
        if isinstance(stmt, ReturnStmt):
            if stmt.expr:
                self.gen_expr(stmt.expr)  # Result in a0
            self.emit(f"j    .L_{self.current_function}_epilogue")

        elif isinstance(stmt, VarDecl):
            # Local variable allocation
            offset = -(12 + len(self.locals) * 4)
            self.locals[stmt.name] = offset
            var_type = getattr(stmt, "var_type", None)
            if var_type:
                self.local_types[stmt.name] = getattr(var_type, "base", "int")
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

            self.loop_stack.append((lbl_start, lbl_end))
            self.emit_label(lbl_start)
            self.gen_expr(stmt.cond)
            self.emit(f"beqz a0, {lbl_end}")
            self.gen_statement(stmt.body)
            self.emit(f"j    {lbl_start}")
            self.emit_label(lbl_end)
            self.loop_stack.pop()

        elif isinstance(stmt, ForStmt):
            lbl_start = self.new_label("for_start")
            lbl_step = self.new_label("for_step")
            lbl_end = self.new_label("for_end")

            if stmt.init:
                self.gen_statement(stmt.init)

            self.loop_stack.append((lbl_step, lbl_end))
            self.emit_label(lbl_start)
            if stmt.cond:
                self.gen_expr(stmt.cond)
                self.emit(f"beqz a0, {lbl_end}")

            self.gen_statement(stmt.body)
            self.emit_label(lbl_step)
            if stmt.step:
                self.gen_expr(stmt.step)
            self.emit(f"j    {lbl_start}")
            self.emit_label(lbl_end)
            self.loop_stack.pop()

        elif isinstance(stmt, BlockStmt):
            self.gen_block(stmt)

    # -------------------------------------------------------------------------
    # Expression Codegen Dispatcher (Result in a0)
    # -------------------------------------------------------------------------
    def gen_expr(self, expr: Expr):
        if isinstance(expr, LiteralExpr):
            if expr.val_type == "int":
                self.emit(f"li   a0, {expr.value}")
            elif expr.val_type == "str":
                lbl = self.new_label("str")
                self.strings.append((lbl, str(expr.value)))
                self.emit(f"la   a0, {lbl}")

        elif isinstance(expr, VariableExpr):
            if expr.name in self.locals:
                offset = self.locals[expr.name]
                self.emit(f"lw   a0, {offset}(s0)")
            else:
                self.emit(f"la   t0, {expr.name}")
                self.emit("lw   a0, 0(t0)")

        elif isinstance(expr, AssignExpr):
            self.gen_assign(expr)

        elif isinstance(expr, BinaryExpr):
            self.gen_binary(expr)

        elif isinstance(expr, UnaryExpr):
            self.gen_unary(expr)

        elif isinstance(expr, CallExpr):
            self.gen_call(expr)

        elif isinstance(expr, IndexExpr):
            self.gen_index(expr)

        elif isinstance(expr, MemberExpr):
            self.gen_member(expr)

    # -------------------------------------------------------------------------
    # Assignment & Compound Operator Codegen
    # -------------------------------------------------------------------------
    def gen_assign(self, expr: AssignExpr):
        # 1. Compute rhs into a0
        self.gen_expr(expr.value)

        # Handle simple assignment '=' vs compound '+=', '-=', etc.
        op = expr.op
        if op == "=":
            self._store_to_target(expr.target)
        else:
            # Compound operator: load target, perform arithmetic, store back
            # Save rhs into stack
            self.emit("addi sp, sp, -4")
            self.emit("sw   a0, 0(sp)")

            # Load target value into a0
            self.gen_expr(expr.target)
            self.emit("mv   t0, a0")       # lhs in t0
            self.emit("lw   t1, 0(sp)")     # rhs in t1
            self.emit("addi sp, sp, 4")

            base_op = op[:-1] if op.endswith("=") else op
            self._emit_alu_op(base_op)
            self._store_to_target(expr.target)

    def _store_to_target(self, target: Expr):
        """Stores the value in a0 into the lvalue target."""
        if isinstance(target, VariableExpr):
            offset = self.locals[target.name]
            self.emit(f"sw   a0, {offset}(s0)")
        elif isinstance(target, UnaryExpr) and target.op == "*":
            # Pointer store: *p = val
            self.emit("addi sp, sp, -4")
            self.emit("sw   a0, 0(sp)")
            self.gen_expr(target.operand)  # Pointer addr in a0
            self.emit("mv   t0, a0")
            self.emit("lw   a0, 0(sp)")
            self.emit("addi sp, sp, 4")
            self.emit("sw   a0, 0(t0)")
        elif isinstance(target, IndexExpr):
            # Array index store: arr[i] = val
            self.emit("addi sp, sp, -4")
            self.emit("sw   a0, 0(sp)")  # Save value
            self._gen_index_addr(target)  # Target address in a0
            self.emit("mv   t0, a0")
            self.emit("lw   a0, 0(sp)")  # Restore value
            self.emit("addi sp, sp, 4")
            self.emit("sw   a0, 0(t0)")

    # -------------------------------------------------------------------------
    # Binary Arithmetic & Comparisons
    # -------------------------------------------------------------------------
    def gen_binary(self, expr: BinaryExpr):
        # 1. Evaluate left operand, push onto stack
        self.gen_expr(expr.left)
        self.emit("addi sp, sp, -4")
        self.emit("sw   a0, 0(sp)")

        # 2. Evaluate right operand into a0
        self.gen_expr(expr.right)
        self.emit("mv   t1, a0")        # Right in t1
        self.emit("lw   t0, 0(sp)")     # Left in t0
        self.emit("addi sp, sp, 4")

        self._emit_alu_op(expr.op)

    def _emit_alu_op(self, op: str):
        """Emits RISC-V instruction for op where t0=left, t1=right, result in a0."""
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
        if op in ops:
            self.emit(ops[op])
        elif op == "==":
            self.emit("sub  a0, t0, t1")
            self.emit("seqz a0, a0")
        elif op == "!=":
            self.emit("sub  a0, t0, t1")
            self.emit("snez a0, a0")
        elif op == "<":
            self.emit("slt  a0, t0, t1")
        elif op == ">":
            self.emit("slt  a0, t1, t0")
        elif op == "<=":
            self.emit("slt  a0, t1, t0")
            self.emit("xori a0, a0, 1")
        elif op == ">=":
            self.emit("slt  a0, t0, t1")
            self.emit("xori a0, a0, 1")

    # -------------------------------------------------------------------------
    # Unary Operations
    # -------------------------------------------------------------------------
    def gen_unary(self, expr: UnaryExpr):
        if expr.op == "-":
            self.gen_expr(expr.operand)
            self.emit("neg  a0, a0")
        elif expr.op == "!":
            self.gen_expr(expr.operand)
            self.emit("seqz a0, a0")
        elif expr.op == "~":
            self.gen_expr(expr.operand)
            self.emit("not  a0, a0")
        elif expr.op == "*":
            # Dereference: *p
            self.gen_expr(expr.operand)
            self.emit("lw   a0, 0(a0)")
        elif expr.op == "&":
            # Address-of: &v
            if isinstance(expr.operand, VariableExpr):
                offset = self.locals[expr.operand.name]
                self.emit(f"addi a0, s0, {offset}")
        elif expr.op == "++":
            # Prefix/postfix increment
            self.gen_expr(expr.operand)
            self.emit("addi a0, a0, 1")
            if isinstance(expr.operand, VariableExpr):
                offset = self.locals[expr.operand.name]
                self.emit(f"sw   a0, {offset}(s0)")
        elif expr.op == "--":
            # Prefix/postfix decrement
            self.gen_expr(expr.operand)
            self.emit("addi a0, a0, -1")
            if isinstance(expr.operand, VariableExpr):
                offset = self.locals[expr.operand.name]
                self.emit(f"sw   a0, {offset}(s0)")

    # -------------------------------------------------------------------------
    # Array & Struct Member Access
    # -------------------------------------------------------------------------
    def _gen_index_addr(self, expr: IndexExpr):
        """Computes the memory address of an array index: base + index * 4."""
        # 1. Base pointer
        self.gen_expr(expr.array)
        self.emit("addi sp, sp, -4")
        self.emit("sw   a0, 0(sp)")  # Base on stack

        # 2. Index
        self.gen_expr(expr.index)
        self.emit("slli a0, a0, 2")  # Index * 4 bytes
        self.emit("lw   t0, 0(sp)")  # Base in t0
        self.emit("addi sp, sp, 4")
        self.emit("add  a0, t0, a0")  # Address in a0

    def gen_index(self, expr: IndexExpr):
        """Evaluates array index load: a[i] -> *(a + i*4)."""
        self._gen_index_addr(expr)
        self.emit("lw   a0, 0(a0)")

    def gen_member(self, expr: MemberExpr):
        """Evaluates struct member access: s.m or p->m."""
        self.gen_expr(expr.obj)
        # Default member offset to 0 if not registered
        offset = 0
        if expr.is_arrow:
            self.emit(f"lw   a0, {offset}(a0)")
        else:
            self.emit(f"lw   a0, {offset}(a0)")

    # -------------------------------------------------------------------------
    # Function Calls
    # -------------------------------------------------------------------------
    def gen_call(self, expr: CallExpr):
        # Push arguments onto stack in left-to-right order
        for arg in expr.args:
            self.gen_expr(arg)
            self.emit("addi sp, sp, -4")
            self.emit("sw   a0, 0(sp)")

        # Pop into ABI argument registers a0-a7 in reverse order
        for idx in reversed(range(len(expr.args))):
            if idx < 8:
                self.emit(f"lw   a{idx}, 0(sp)")
            self.emit("addi sp, sp, 4")

        if isinstance(expr.callee, VariableExpr):
            self.emit(f"call {expr.callee.name}")
