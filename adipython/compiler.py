#!/usr/bin/env python3
"""
AdiPython Compiler & JIT Driver Interface
Integrates:
- Macro Preprocessor (#include, #define, #ifdef)
- Adam Hierarchical Symbol Table
- AST Parser & Type Engine
- Native RV32IM Machine Code JIT Emitter
- Ring-0 Hardware Execution Runtime
"""

from .lexer import Lexer
from .parser import Parser
from .runtime import Runtime
from .preprocessor import Preprocessor
from .symbols import create_adam_table
from .jit import JITCompiler

class AdiPython:
    def __init__(self, vm=None, adifs=None):
        self.vm = vm
        self.adifs = adifs
        self.preprocessor = Preprocessor(adifs=adifs)
        self.adam_table = create_adam_table()
        self.runtime = Runtime(vm)
        self.jit = JITCompiler(vm)

    def preprocess(self, source_code, current_file=None):
        return self.preprocessor.process(source_code, current_file)

    def parse(self, source_code):
        clean_code = self.preprocess(source_code)
        lexer = Lexer(clean_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()

    def execute(self, source_code):
        """Preprocesses, parses, and executes AdiPython code."""
        ast = self.parse(source_code)
        return self.runtime.run(ast)

    def execute_file(self, filename):
        """Loads and executes an AdiPython (.ap) script file."""
        # Check AdiFS first
        if self.adifs and self.adifs.exists(filename):
            code = self.adifs.read_file(filename).decode("utf-8", errors="replace")
        else:
            with open(filename, "r", encoding="utf-8") as f:
                code = f.read()
        return self.execute(code)

    def jit_compile_function(self, source_code):
        """Compiles an AdiPython function directly into native RV32IM machine code in RAM."""
        ast = self.parse(source_code)
        func_node = None
        for stmt in ast.stmts:
            if stmt.__class__.__name__ == "FunctionDef":
                func_node = stmt
                break
        if not func_node:
            raise ValueError("JIT: No function definition found in source")
        return self.jit.compile_function(func_node)

    def jit_call(self, func_name, args=None):
        """Executes a JIT-compiled function on the bare-metal VM."""
        return self.jit.execute_function(func_name, args)
