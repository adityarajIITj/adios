#!/usr/bin/env python3
"""
AdiPython Compiler & Driver Interface
Provides high-level API to compile and execute AdiPython code.
"""

from .lexer import Lexer
from .parser import Parser
from .runtime import Runtime

class AdiPython:
    def __init__(self, vm=None):
        self.vm = vm
        self.runtime = Runtime(vm)

    def execute(self, source_code):
        """Compiles and executes an AdiPython source string."""
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        return self.runtime.run(ast)

    def execute_file(self, filename):
        """Loads and executes an AdiPython (.ap) script file."""
        with open(filename, "r", encoding="utf-8") as f:
            code = f.read()
        return self.execute(code)
