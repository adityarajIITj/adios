#!/usr/bin/env python3
"""
AdiPython Compiler & JIT Driver Interface (Deepened Architecture)
Integrates:
- Macro Preprocessor (#include, #define, #ifdef, #ifndef)
- Adam Hierarchical Symbol Table
- AST Parser, Visitor & Type Engine
- Three-Address Code (TAC) IR Generator & Optimizer Pipeline
- Linear Scan Register Allocator
- Native RV32IM Machine Code JIT Emitter directly in RAM
- Ring-0 Hardware Execution Runtime with MMIO acceleration
"""

from typing import Optional, List, Dict, Any
from .lexer import Lexer
from .parser import Parser, ASTNode, Program, FunctionDef
from .runtime import Runtime
from .preprocessor import Preprocessor
from .symbols import create_adam_table
from .jit import JITCompiler
from .ir_gen import IRGenerator
from .optimizer import Optimizer
from .regalloc import LinearScanAllocator


class CompilationTelemetry:
    """Collects runtime and compilation phase metrics."""
    def __init__(self):
        self.preprocessor_lines = 0
        self.tokens_emitted = 0
        self.ast_statements = 0
        self.ir_instructions = 0
        self.optimized_instructions = 0
        self.jit_bytes = 0
        self.jit_functions = 0


class AdiPython:
    """
    Unified High-Level Interface for the AdiPython Language Subsystem.
    Provides source preprocessing, AST parsing, AST tree execution,
    TAC IR generation, multi-pass optimization, and native RV32IM JIT compilation.
    """
    def __init__(self, vm=None, adifs=None):
        self.vm = vm
        self.adifs = adifs
        self.preprocessor = Preprocessor(adifs=adifs)
        self.adam_table = create_adam_table()
        self.runtime = Runtime(vm)
        self.jit = JITCompiler(vm)
        self.ir_gen = IRGenerator()
        self.optimizer = Optimizer()
        self.telemetry = CompilationTelemetry()

    def preprocess(self, source_code: str, current_file: Optional[str] = None) -> str:
        """Runs the macro preprocessor (#define, #ifdef, #include)."""
        clean = self.preprocessor.process(source_code, current_file)
        self.telemetry.preprocessor_lines = len(clean.splitlines())
        return clean

    def tokenize(self, source_code: str) -> list:
        """Tokenizes preprocessed source code into a Token stream."""
        clean_code = self.preprocess(source_code)
        lexer = Lexer(clean_code)
        tokens = lexer.tokenize()
        self.telemetry.tokens_emitted = len(tokens)
        return tokens

    def parse(self, source_code: str) -> Program:
        """Parses source code into an Abstract Syntax Tree (AST)."""
        tokens = self.tokenize(source_code)
        parser = Parser(tokens)
        ast = parser.parse()
        self.telemetry.ast_statements = len(ast.stmts)
        return ast

    def execute(self, source_code: str):
        """Preprocesses, parses, and executes AdiPython code directly on the runtime."""
        ast = self.parse(source_code)
        return self.runtime.run(ast)

    def execute_file(self, filename: str):
        """Loads and executes an AdiPython (.ap) script from AdiFS or the host filesystem."""
        if self.adifs and self.adifs.exists(filename):
            code = self.adifs.read_file(filename).decode("utf-8", errors="replace")
        else:
            with open(filename, "r", encoding="utf-8") as f:
                code = f.read()
        return self.execute(code)

    def compile_to_ir(self, source_code: str, optimize: bool = True):
        """
        Compiles source code into Three-Address Code (TAC) IR.
        Optionally executes the multi-pass optimization pipeline.
        """
        ast = self.parse(source_code)
        generator = IRGenerator()
        ir_mod = generator.generate(ast)
        self.telemetry.ir_instructions = sum(
            len(bb.instructions)
            for fn in ir_mod.functions.values()
            for bb in fn.blocks
        )

        if optimize:
            opt = Optimizer()
            ir_mod = opt.optimize_module(ir_mod)
            self.telemetry.optimized_instructions = sum(
                len(bb.instructions)
                for fn in ir_mod.functions.values()
                for bb in fn.blocks
            )

        return ir_mod

    def jit_compile_function(self, source_code: str) -> int:
        """
        Compiles an AdiPython function directly into native RV32IM machine code in RAM.
        Returns the executable memory entry address.
        """
        ast = self.parse(source_code)
        func_node = None
        for stmt in ast.stmts:
            if isinstance(stmt, FunctionDef) or stmt.__class__.__name__ == "FunctionDef":
                func_node = stmt
                break
        if not func_node:
            raise ValueError("JIT: No function definition found in source code")

        entry_addr = self.jit.compile_function(func_node)
        self.telemetry.jit_functions += 1
        self.telemetry.jit_bytes += len(self.jit.code)
        return entry_addr

    def jit_call(self, func_name: str, args: Optional[List[Any]] = None) -> int:
        """
        Executes a JIT-compiled function on the bare-metal VM with arguments.
        """
        return self.jit.execute_function(func_name, args)

    def dump_ast(self, source_code: str) -> str:
        """Renders an indented text representation of the parsed AST."""
        ast = self.parse(source_code)
        lines = []

        def walk(node, indent=0):
            prefix = "  " * indent
            lines.append(f"{prefix}{node.__class__.__name__}")
            for field, val in node.__dict__.items():
                if field.startswith("_") or field in ("lineno", "col_offset"):
                    continue
                if isinstance(val, list):
                    lines.append(f"{prefix}  {field}:")
                    for elem in val:
                        if isinstance(elem, ASTNode):
                            walk(elem, indent + 2)
                        else:
                            lines.append(f"{prefix}    {repr(elem)}")
                elif isinstance(val, ASTNode):
                    lines.append(f"{prefix}  {field}:")
                    walk(val, indent + 2)
                else:
                    lines.append(f"{prefix}  {field} = {repr(val)}")

        walk(ast)
        return "\n".join(lines)
