#!/usr/bin/env python3
"""
AdiOS Compiler IR Code Generator
Traverses AdiPython AST and emits Three-Address Code (TAC) into an IRModule.
"""

from typing import Dict, List, Optional
from .parser import (
    Program, FunctionDef, Return, If, While, For, ExprStmt,
    Assign, AugAssign, BinaryOp, UnaryOp, Number, String, Identifier,
    Call, Break, Continue
)
from .ir import (
    IRModule, IRFunction, IRBasicBlock, IRInstruction, IROperand,
    IR_MOVE, IR_ADD, IR_SUB, IR_MUL, IR_DIV, IR_REM,
    IR_AND, IR_OR, IR_XOR, IR_SHL, IR_SHR,
    IR_EQ, IR_NE, IR_LT, IR_LE, IR_GT, IR_GE,
    IR_PEEK, IR_POKE, IR_JUMP, IR_JUMP_IF_NOT,
    IR_CALL, IR_PARAM, IR_RETURN, IR_LABEL
)

BINARY_OP_MAP = {
    "+": IR_ADD, "-": IR_SUB, "*": IR_MUL, "/": IR_DIV, "%": IR_REM,
    "&": IR_AND, "|": IR_OR, "^": IR_XOR, "<<": IR_SHL, ">>": IR_SHR,
    "==": IR_EQ, "!=": IR_NE, "<": IR_LT, "<=": IR_LE, ">": IR_GT, ">=": IR_GE
}

class IRGenerator:
    def __init__(self):
        self.module = IRModule()
        self.curr_func: Optional[IRFunction] = None
        self.curr_block: Optional[IRBasicBlock] = None
        self.var_map: Dict[str, IROperand] = {}
        self.loop_stack: List[Dict[str, str]] = [] # stack of {'cond': lbl, 'exit': lbl}

    def generate(self, ast: Program) -> IRModule:
        # Separate top-level statements from function definitions
        top_stmts = []
        for stmt in ast.stmts:
            if isinstance(stmt, FunctionDef):
                self.gen_function(stmt)
            else:
                top_stmts.append(stmt)

        if top_stmts:
            # Wrap top-level statements into __main__ function
            main_fn = FunctionDef("__main__", [], top_stmts)
            self.gen_function(main_fn)

        return self.module

    def gen_function(self, fn_def: FunctionDef):
        func = IRFunction(fn_def.name, fn_def.params)
        self.curr_func = func
        self.var_map = {}
        self.loop_stack = []

        entry = func.create_block(f"{fn_def.name}_entry")
        self.curr_block = entry

        # Map parameters to virtual registers
        for p in fn_def.params:
            r = func.new_reg()
            self.var_map[p] = r

        # Emit statements
        for stmt in fn_def.body:
            self.gen_statement(stmt)

        # Default return 0 if block not terminated
        if not self.curr_block.is_terminated():
            zero_op = IROperand.const(0)
            self.curr_block.add_instruction(IRInstruction(IR_RETURN, src1=zero_op))

        self.module.add_function(func)

    def gen_statement(self, stmt):
        if self.curr_block.is_terminated():
            # Code after return or unconditional jump is unreachable, create dead block
            dead = self.curr_func.create_block()
            self.curr_block = dead

        if isinstance(stmt, Assign):
            val_op = self.gen_expression(stmt.value)
            reg = self.var_map.get(stmt.target)
            if reg is None:
                reg = self.curr_func.new_reg()
                self.var_map[stmt.target] = reg
            self.curr_block.add_instruction(IRInstruction(IR_MOVE, dest=reg, src1=val_op))

        elif isinstance(stmt, AugAssign):
            val_op = self.gen_expression(stmt.value)
            reg = self.var_map.get(stmt.target)
            if reg is None:
                reg = self.curr_func.new_reg()
                self.var_map[stmt.target] = reg
            ir_op = BINARY_OP_MAP.get(stmt.op, IR_ADD)
            res = self.curr_func.new_reg()
            self.curr_block.add_instruction(IRInstruction(ir_op, dest=res, src1=reg, src2=val_op))
            self.curr_block.add_instruction(IRInstruction(IR_MOVE, dest=reg, src1=res))

        elif isinstance(stmt, Return):
            val_op = self.gen_expression(stmt.value) if stmt.value else IROperand.const(0)
            self.curr_block.add_instruction(IRInstruction(IR_RETURN, src1=val_op))

        elif isinstance(stmt, If):
            cond_op = self.gen_expression(stmt.cond)
            then_bb = self.curr_func.create_block(self.curr_func.new_label("then"))
            else_bb = self.curr_func.create_block(self.curr_func.new_label("else")) if stmt.else_body else None
            merge_bb = self.curr_func.create_block(self.curr_func.new_label("merge"))

            target_false = else_bb if else_bb else merge_bb
            self.curr_block.add_instruction(IRInstruction(IR_JUMP_IF_NOT, dest=IROperand.label(target_false.label), src1=cond_op))

            # Emit then block
            self.curr_block = then_bb
            for s in stmt.then_body:
                self.gen_statement(s)
            if not self.curr_block.is_terminated():
                self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(merge_bb.label)))

            # Emit else block if exists
            if else_bb:
                self.curr_block = else_bb
                for s in stmt.else_body:
                    self.gen_statement(s)
                if not self.curr_block.is_terminated():
                    self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(merge_bb.label)))

            self.curr_block = merge_bb

        elif isinstance(stmt, While):
            cond_bb = self.curr_func.create_block(self.curr_func.new_label("while_cond"))
            body_bb = self.curr_func.create_block(self.curr_func.new_label("while_body"))
            exit_bb = self.curr_func.create_block(self.curr_func.new_label("while_exit"))

            self.loop_stack.append({'cond': cond_bb.label, 'exit': exit_bb.label})

            self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(cond_bb.label)))

            # Cond BB
            self.curr_block = cond_bb
            cond_op = self.gen_expression(stmt.cond)
            self.curr_block.add_instruction(IRInstruction(IR_JUMP_IF_NOT, dest=IROperand.label(exit_bb.label), src1=cond_op))

            # Body BB
            self.curr_block = body_bb
            for s in stmt.body:
                self.gen_statement(s)
            if not self.curr_block.is_terminated():
                self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(cond_bb.label)))

            self.loop_stack.pop()
            self.curr_block = exit_bb

        elif isinstance(stmt, For):
            # for var in range(start, end, step)
            start_op = self.gen_expression(stmt.start)
            end_op = self.gen_expression(stmt.end)
            step_op = self.gen_expression(stmt.step)

            var_reg = self.curr_func.new_reg()
            self.var_map[stmt.var] = var_reg
            self.curr_block.add_instruction(IRInstruction(IR_MOVE, dest=var_reg, src1=start_op))

            cond_bb = self.curr_func.create_block(self.curr_func.new_label("for_cond"))
            body_bb = self.curr_func.create_block(self.curr_func.new_label("for_body"))
            exit_bb = self.curr_func.create_block(self.curr_func.new_label("for_exit"))

            self.loop_stack.append({'cond': cond_bb.label, 'exit': exit_bb.label})
            self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(cond_bb.label)))

            # Check condition: var < end
            self.curr_block = cond_bb
            cmp_reg = self.curr_func.new_reg()
            self.curr_block.add_instruction(IRInstruction(IR_LT, dest=cmp_reg, src1=var_reg, src2=end_op))
            self.curr_block.add_instruction(IRInstruction(IR_JUMP_IF_NOT, dest=IROperand.label(exit_bb.label), src1=cmp_reg))

            # Body
            self.curr_block = body_bb
            for s in stmt.body:
                self.gen_statement(s)

            # Step increment: var += step
            new_val = self.curr_func.new_reg()
            self.curr_block.add_instruction(IRInstruction(IR_ADD, dest=new_val, src1=var_reg, src2=step_op))
            self.curr_block.add_instruction(IRInstruction(IR_MOVE, dest=var_reg, src1=new_val))

            if not self.curr_block.is_terminated():
                self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(cond_bb.label)))

            self.loop_stack.pop()
            self.curr_block = exit_bb

        elif isinstance(stmt, Break):
            if self.loop_stack:
                target = self.loop_stack[-1]['exit']
                self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(target)))

        elif isinstance(stmt, Continue):
            if self.loop_stack:
                target = self.loop_stack[-1]['cond']
                self.curr_block.add_instruction(IRInstruction(IR_JUMP, dest=IROperand.label(target)))

        elif isinstance(stmt, ExprStmt):
            self.gen_expression(stmt.expr)

    def gen_expression(self, expr) -> IROperand:
        if isinstance(expr, Number):
            return IROperand.const(expr.value)

        elif isinstance(expr, Identifier):
            reg = self.var_map.get(expr.name)
            if reg is None:
                # Undefined variable initialized to 0
                reg = self.curr_func.new_reg()
                self.var_map[expr.name] = reg
                self.curr_block.add_instruction(IRInstruction(IR_MOVE, dest=reg, src1=IROperand.const(0)))
            return reg

        elif isinstance(expr, BinaryOp):
            l_op = self.gen_expression(expr.left)
            r_op = self.gen_expression(expr.right)
            ir_op = BINARY_OP_MAP.get(expr.op, IR_ADD)
            res_reg = self.curr_func.new_reg()
            self.curr_block.add_instruction(IRInstruction(ir_op, dest=res_reg, src1=l_op, src2=r_op))
            return res_reg

        elif isinstance(expr, UnaryOp):
            operand = self.gen_expression(expr.operand)
            res_reg = self.curr_func.new_reg()
            if expr.op == "-":
                self.curr_block.add_instruction(IRInstruction(IR_SUB, dest=res_reg, src1=IROperand.const(0), src2=operand))
            elif expr.op == "not":
                self.curr_block.add_instruction(IRInstruction(IR_EQ, dest=res_reg, src1=operand, src2=IROperand.const(0)))
            return res_reg

        elif isinstance(expr, Call):
            # Special MMIO primitives
            if expr.name == "peek":
                addr_op = self.gen_expression(expr.args[0])
                res = self.curr_func.new_reg()
                self.curr_block.add_instruction(IRInstruction(IR_PEEK, dest=res, src1=addr_op))
                return res

            elif expr.name == "poke":
                addr_op = self.gen_expression(expr.args[0])
                val_op = self.gen_expression(expr.args[1])
                self.curr_block.add_instruction(IRInstruction(IR_POKE, src1=addr_op, src2=val_op))
                return IROperand.const(0)

            else:
                # Standard function call: emit parameters followed by CALL
                for arg in expr.args:
                    arg_op = self.gen_expression(arg)
                    self.curr_block.add_instruction(IRInstruction(IR_PARAM, src1=arg_op))
                res = self.curr_func.new_reg()
                self.curr_block.add_instruction(IRInstruction(IR_CALL, dest=res, src1=IROperand.sym(expr.name)))
                return res

        return IROperand.const(0)
