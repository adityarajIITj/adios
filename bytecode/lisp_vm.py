#!/usr/bin/env python3
"""
AdiOS Bytecode Subsystem: Dynamic Bytecode VM & Lisp Engine (lisp_vm.py)
Implements high-performance stack bytecode virtual machine & Lisp compiler:
- S-Expression tokenizer & recursive AST reader
- 16-opcode stack-based Virtual Machine ISA
- Bytecode compiler compiling forms, conditionals, and functions
- Frame stack execution with local variable environments
Zero external dependencies.
"""

from typing import Any, List, Dict, Tuple, Optional

# VM Opcodes
OP_CONST        = 1
OP_LOAD         = 2
OP_STORE        = 3
OP_POP          = 4
OP_ADD          = 5
OP_SUB          = 6
OP_MUL          = 7
OP_DIV          = 8
OP_EQ           = 9
OP_LT           = 10
OP_GT           = 11
OP_JMP          = 12
OP_JMP_IF_FALSE = 13
OP_CALL         = 14
OP_RET          = 15
OP_HALT         = 16

class LispParser:
    """Tokenizes and parses Lisp S-Expressions."""
    @staticmethod
    def tokenize(code: str) -> List[str]:
        return code.replace("(", " ( ").replace(")", " ) ").split()

    @staticmethod
    def read_from_tokens(tokens: List[str]) -> Any:
        if len(tokens) == 0:
            raise SyntaxError("Unexpected EOF while reading Lisp form")
        token = tokens.pop(0)
        if token == "(":
            l = []
            while tokens[0] != ")":
                l.append(LispParser.read_from_tokens(tokens))
            tokens.pop(0) # pop ')'
            return l
        elif token == ")":
            raise SyntaxError("Unexpected ')'")
        else:
            try:
                return int(token)
            except ValueError:
                try:
                    return float(token)
                except ValueError:
                    return token

    @staticmethod
    def parse(code: str) -> Any:
        return LispParser.read_from_tokens(LispParser.tokenize(code))

class BytecodeCompiler:
    """Compiles Lisp AST into linear bytecode."""
    def __init__(self):
        self.code: List[int] = []
        self.constants: List[Any] = []
        self.locals_map: Dict[str, int] = {}
        self.functions: Dict[str, int] = {} # Name -> Entry IP

    def add_const(self, val: Any) -> int:
        if val in self.constants:
            return self.constants.index(val)
        self.constants.append(val)
        return len(self.constants) - 1

    def compile(self, ast: Any):
        if isinstance(ast, (int, float)):
            c_idx = self.add_const(ast)
            self.code.extend([OP_CONST, c_idx])

        elif isinstance(ast, str):
            # Local variable load
            if ast in self.locals_map:
                self.code.extend([OP_LOAD, self.locals_map[ast]])
            else:
                raise NameError(f"Undefined variable '{ast}'")

        elif isinstance(ast, list):
            op = ast[0]
            if op == "defun":
                # (defun name (params...) body)
                name = ast[1]
                params = ast[2]
                body = ast[3]

                # Jump over function body during linear execution
                jmp_pos = len(self.code)
                self.code.extend([OP_JMP, 0])

                self.functions[name] = len(self.code)
                old_locals = dict(self.locals_map)
                self.locals_map = {p: i for i, p in enumerate(params)}

                self.compile(body)
                self.code.append(OP_RET)

                # Patch jump over function
                self.code[jmp_pos + 1] = len(self.code)
                self.locals_map = old_locals

            elif op in ("+", "-", "*", "/", "=", "<", ">"):
                # Compile binary operations: (op left right)
                self.compile(ast[1])
                self.compile(ast[2])
                op_map = {
                    "+": OP_ADD, "-": OP_SUB, "*": OP_MUL, "/": OP_DIV,
                    "=": OP_EQ, "<": OP_LT, ">": OP_GT
                }
                self.code.append(op_map[op])

            elif op == "if":
                # (if cond then else)
                self.compile(ast[1]) # Condition
                jmp_false_pos = len(self.code)
                self.code.extend([OP_JMP_IF_FALSE, 0])

                self.compile(ast[2]) # Then
                jmp_end_pos = len(self.code)
                self.code.extend([OP_JMP, 0])

                self.code[jmp_false_pos + 1] = len(self.code)
                self.compile(ast[3]) # Else
                self.code[jmp_end_pos + 1] = len(self.code)

            elif op in self.functions:
                # Function call: (name arg1 arg2...)
                for arg in ast[1:]:
                    self.compile(arg)
                entry_ip = self.functions[op]
                self.code.extend([OP_CALL, entry_ip, len(ast) - 1])

            else:
                raise ValueError(f"Unknown Lisp form: {op}")

class CallFrame:
    def __init__(self, return_ip: int, num_args: int, locals_list: List[Any]):
        self.return_ip = return_ip
        self.locals = locals_list

class BytecodeVM:
    """Stack-based bytecode virtual machine."""
    def __init__(self, code: List[int], constants: List[Any]):
        self.code = code
        self.constants = constants
        self.stack: List[Any] = []
        self.call_stack: List[CallFrame] = []
        self.ip = 0

    def run(self) -> Any:
        curr_locals: List[Any] = []

        while self.ip < len(self.code):
            op = self.code[self.ip]
            self.ip += 1

            if op == OP_CONST:
                idx = self.code[self.ip]
                self.ip += 1
                self.stack.append(self.constants[idx])

            elif op == OP_LOAD:
                local_idx = self.code[self.ip]
                self.ip += 1
                self.stack.append(curr_locals[local_idx])

            elif op == OP_STORE:
                local_idx = self.code[self.ip]
                self.ip += 1
                curr_locals[local_idx] = self.stack.pop()

            elif op == OP_POP:
                self.stack.pop()

            elif op == OP_ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)

            elif op == OP_SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)

            elif op == OP_MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)

            elif op == OP_DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b if isinstance(a, int) and isinstance(b, int) else a / b)

            elif op == OP_EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a == b else 0)

            elif op == OP_LT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a < b else 0)

            elif op == OP_GT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a > b else 0)

            elif op == OP_JMP:
                target = self.code[self.ip]
                self.ip = target

            elif op == OP_JMP_IF_FALSE:
                target = self.code[self.ip]
                self.ip += 1
                cond = self.stack.pop()
                if not cond:
                    self.ip = target

            elif op == OP_CALL:
                entry = self.code[self.ip]
                num_args = self.code[self.ip + 1]
                self.ip += 2
                args = [self.stack.pop() for _ in range(num_args)]
                args.reverse()

                frame = CallFrame(self.ip, num_args, curr_locals)
                self.call_stack.append(frame)
                curr_locals = args
                self.ip = entry

            elif op == OP_RET:
                ret_val = self.stack.pop()
                frame = self.call_stack.pop()
                self.ip = frame.return_ip
                curr_locals = frame.locals
                self.stack.append(ret_val)

            elif op == OP_HALT:
                break

        return self.stack[-1] if self.stack else None

if __name__ == "__main__":
    ast = LispParser.parse("(+ 10 (* 3 4))")
    comp = BytecodeCompiler()
    comp.compile(ast)
    comp.code.append(OP_HALT)
    vm = BytecodeVM(comp.code, comp.constants)
    res = vm.run()
    assert res == 22
    print("Bytecode VM & Lisp Engine verified.")
