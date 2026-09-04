#!/usr/bin/env python3
"""
AdiPython Lexer (Deepened Systems Architecture)
Tokenizes AdiPython source code into a clean, deterministic token stream.

Core Capabilities:
1. Indentation-based block syntax with explicit INDENT / DEDENT token emissions.
2. Nesting level tracking: parenthesized expressions ((), [], {}) suppress newlines
   and indentation changes according to standard Python lexical specifications.
3. Full compound assignment and arithmetic operator tokenization:
   +=, -=, *=, /=, %=, &=, |=, ^=, <<=, >>=, **=, //=, ==, !=, <=, >=, <<, >>, **, //
4. Multi-line triple-quoted string literals (''' and \"\"\") with full escape support
   including hex (\\xHH), unicode (\\uXXXX), and standard ASCII control escapes.
5. Numeric literals supporting decimal, hex (0x...), binary (0b...), octal (0o...),
   floating-point notation, and underscore separators (e.g. 1_000_000).
6. Rich diagnostic source tracking with line, column, and token width offsets.
"""

import sys

# -----------------------------------------------------------------------------
# Token Type Constants
# -----------------------------------------------------------------------------
TOK_EOF       = "EOF"
TOK_NEWLINE   = "NEWLINE"
TOK_INDENT    = "INDENT"
TOK_DEDENT    = "DEDENT"
TOK_NUMBER    = "NUMBER"
TOK_STRING    = "STRING"
TOK_IDENT     = "IDENT"
TOK_KEYWORD   = "KEYWORD"
TOK_OP        = "OP"
TOK_DELIM     = "DELIM"

# Reserved Language Keywords
KEYWORDS = {
    "def", "return", "if", "elif", "else", "while", "for", "in", "range",
    "break", "continue", "pass", "global", "and", "or", "not", "True", "False", "None",
    "try", "except", "finally", "raise", "is", "lambda", "assert", "import", "from",
    "as", "with", "yield", "class"
}

# Standard Ring-0 Hardware Primitives and Core Built-ins
BUILTINS = {
    "print", "peek", "poke", "pixel", "line", "rect", "clear", "cls",
    "sleep", "tone", "circle", "fill_circle", "len", "range", "abs",
    "min", "max", "sum", "enumerate", "zip", "reversed", "all", "any",
    "chr", "ord", "hex", "bin", "oct", "str", "int", "bool", "list", "dict"
}

# Three-character compound operators
TRI_OPS = {
    "<<=", ">>=", "**=", "//="
}

# Two-character compound operators
DUAL_OPS = {
    "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=",
    "&=", "|=", "^=", "<<", ">>", "**", "//", "->", ":="
}

# Single-character operators
SINGLE_OPS = set("+-*/%&|^<>=~!")

# Structural Delimiters
DELIMITERS = set("():,;[]{}@.")


class SourceLocation:
    """Represents a precise source coordinate for compilation diagnostics."""
    def __init__(self, line: int, col: int, length: int = 1):
        self.line = line
        self.col = col
        self.length = length

    def __repr__(self) -> str:
        return f"L{self.line}:{self.col}"


class Token:
    """Represents a lexical token emitted by the AdiPython Lexer."""
    def __init__(self, typ: str, value, line: int, col: int, length: int = 1):
        self.type = typ
        self.value = value
        self.line = line
        self.col = col
        self.length = length

    @property
    def loc(self) -> SourceLocation:
        return SourceLocation(self.line, self.col, self.length)

    def is_keyword(self, name: str = None) -> bool:
        if self.type != TOK_KEYWORD:
            return False
        return name is None or self.value == name

    def is_op(self, op: str = None) -> bool:
        if self.type != TOK_OP:
            return False
        return op is None or self.value == op

    def is_delim(self, d: str = None) -> bool:
        if self.type != TOK_DELIM:
            return False
        return d is None or self.value == d

    def __repr__(self) -> str:
        return f"Token({self.type}, {repr(self.value)}, L{self.line}:{self.col})"


class LexerError(Exception):
    """Raised when an unrecoverable lexical analysis error occurs."""
    def __init__(self, message: str, line: int, col: int, source_snippet: str = ""):
        super().__init__(f"LexerError [L{line}:{col}]: {message}")
        self.message = message
        self.line = line
        self.col = col
        self.source_snippet = source_snippet


class Lexer:
    """
    Deterministic Lexical Analyzer for AdiPython.
    Converts raw character streams into structured tokens with indentation tracking.
    """
    def __init__(self, source: str):
        self.source = source
        self.length = len(source)
        self.pos = 0
        self.line = 1
        self.col = 1
        self.indent_stack = [0]
        self.bracket_depth = 0  # Nesting depth: (), [], {}

    def peek(self, offset: int = 0) -> str:
        """Returns character at pos + offset without advancing the cursor."""
        idx = self.pos + offset
        return self.source[idx] if idx < self.length else "\0"

    def advance(self) -> str:
        """Consumes and returns the current character, updating line and col."""
        ch = self.peek()
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match_char(self, expected: str) -> bool:
        """Advances and returns True if the current character matches expected."""
        if self.peek() == expected:
            self.advance()
            return True
        return False

    def skip_comment(self):
        """Consumes a single-line comment beginning with '#' until newline or EOF."""
        while self.peek() not in ("\n", "\0"):
            self.advance()

    def parse_escape(self) -> str:
        """Parses a backslash escape sequence inside a string literal."""
        esc = self.advance()
        if esc == "n":  return "\n"
        if esc == "t":  return "\t"
        if esc == "r":  return "\r"
        if esc == "b":  return "\b"
        if esc == "f":  return "\f"
        if esc == "0":  return "\0"
        if esc == "\\": return "\\"
        if esc == '"':  return '"'
        if esc == "'":  return "'"
        if esc == "x":
            # 2-digit hexadecimal byte escape: \xHH
            h1 = self.advance()
            h2 = self.advance()
            try:
                return chr(int(h1 + h2, 16))
            except ValueError:
                return "\\x" + h1 + h2
        if esc == "u":
            # 4-digit unicode escape: \uXXXX
            u_digits = "".join(self.advance() for _ in range(4))
            try:
                return chr(int(u_digits, 16))
            except ValueError:
                return "\\u" + u_digits
        return esc

    def lex_string(self, quote: str, start_line: int, start_col: int) -> Token:
        """
        Parses single, double, or triple-quoted string literals.
        Supports embedded escapes and multi-line span.
        """
        is_triple = False
        if self.peek() == quote and self.peek(1) == quote:
            # Triple-quoted string literal
            self.advance()
            self.advance()
            is_triple = True

        buf = []
        while self.pos < self.length:
            if is_triple:
                if (self.peek() == quote and
                    self.peek(1) == quote and
                    self.peek(2) == quote):
                    self.advance()
                    self.advance()
                    self.advance()
                    break
            else:
                if self.peek() == quote:
                    self.advance()
                    break
                if self.peek() in ("\n", "\r", "\0"):
                    raise LexerError("Unterminated single-line string literal",
                                     start_line, start_col)

            ch = self.advance()
            if ch == "\\" and self.peek() != "\0":
                buf.append(self.parse_escape())
            else:
                buf.append(ch)
        else:
            if is_triple:
                raise LexerError("Unterminated triple-quoted string literal",
                                 start_line, start_col)

        content = "".join(buf)
        return Token(TOK_STRING, content, start_line, start_col, len(content) + 2)

    def lex_number(self, start_line: int, start_col: int, initial_neg: bool = False) -> Token:
        """
        Parses numeric literals in hex (0x), binary (0b), octal (0o),
        or standard decimal format with underscore separators and floating point.
        """
        buf = []
        ch = self.advance()  # Consumes '-' if initial_neg is True, or first digit
        buf.append(ch)

        # If negative, advance to read first digit for prefix checks
        if initial_neg:
            ch = self.advance()
            buf.append(ch)

        # Hexadecimal literal: 0x...
        if ch == "0" and self.peek() in ("x", "X"):
            buf.append(self.advance())
            while self.peek() in "0123456789abcdefABCDEF_":
                c = self.advance()
                if c != "_":
                    buf.append(c)
            raw = "".join(buf)
            val = int(raw, 16) if not initial_neg else -int(raw[1:], 16)
            return Token(TOK_NUMBER, val, start_line, start_col, len(raw))

        # Binary literal: 0b...
        if ch == "0" and self.peek() in ("b", "B"):
            buf.append(self.advance())
            while self.peek() in "01_":
                c = self.advance()
                if c != "_":
                    buf.append(c)
            raw = "".join(buf)
            val = int(raw, 2) if not initial_neg else -int(raw[1:], 2)
            return Token(TOK_NUMBER, val, start_line, start_col, len(raw))

        # Octal literal: 0o...
        if ch == "0" and self.peek() in ("o", "O"):
            buf.append(self.advance())
            while self.peek() in "01234567_":
                c = self.advance()
                if c != "_":
                    buf.append(c)
            raw = "".join(buf)
            val = int(raw, 8) if not initial_neg else -int(raw[1:], 8)
            return Token(TOK_NUMBER, val, start_line, start_col, len(raw))

        # Decimal integer or floating point
        is_float = False
        while self.peek().isdigit() or self.peek() in (".", "_"):
            if self.peek() == ".":
                # Ensure next char after dot is a digit (not a method call like 42.to_bytes)
                if not self.peek(1).isdigit():
                    break
                if is_float:
                    break  # Second dot terminates number
                is_float = True
                buf.append(self.advance())
            elif self.peek() == "_":
                self.advance()  # Skip underscore
            else:
                buf.append(self.advance())

        # Scientific notation: 1e-4, 2E+8
        if self.peek() in ("e", "E"):
            is_float = True
            buf.append(self.advance())
            if self.peek() in ("+", "-"):
                buf.append(self.advance())
            while self.peek().isdigit():
                buf.append(self.advance())

        raw_str = "".join(buf)
        if is_float:
            val = float(raw_str)
        else:
            val = int(raw_str)
        return Token(TOK_NUMBER, val, start_line, start_col, len(raw_str))

    def tokenize(self):
        """
        Executes complete lexical tokenization of source code.
        Returns a list of Token objects ending with TOK_EOF.
        """
        tokens = []

        while self.pos < self.length:
            # 1. Check indentation at line origin (column 1)
            if self.col == 1 and self.bracket_depth == 0:
                spaces = 0
                while self.peek() in (" ", "\t"):
                    spaces += 4 if self.advance() == "\t" else 1

                # If line is blank or comment-only, do not trigger indent / dedent
                if self.peek() in ("\n", "\r", "#"):
                    if self.peek() == "#":
                        self.skip_comment()
                    if self.peek() in ("\n", "\r"):
                        if self.peek() == "\r" and self.peek(1) == "\n":
                            self.advance()
                        self.advance()
                    continue

                curr_indent = self.indent_stack[-1]
                if spaces > curr_indent:
                    self.indent_stack.append(spaces)
                    tokens.append(Token(TOK_INDENT, spaces, self.line, self.col))
                elif spaces < curr_indent:
                    while self.indent_stack and spaces < self.indent_stack[-1]:
                        self.indent_stack.pop()
                        tokens.append(Token(TOK_DEDENT, spaces, self.line, self.col))
                    if self.indent_stack and spaces != self.indent_stack[-1]:
                        raise LexerError(f"Inconsistent unindent: {spaces} spaces does not match any outer indentation level",
                                         self.line, self.col)

            ch = self.peek()

            # Skip horizontal whitespace within a line
            if ch in (" ", "\t"):
                self.advance()
                continue

            # Line comments
            if ch == "#":
                self.skip_comment()
                continue

            # Newlines
            if ch in ("\n", "\r"):
                start_line, start_col = self.line, self.col
                if ch == "\r" and self.peek(1) == "\n":
                    self.advance()
                self.advance()

                # If inside brackets/parentheses, newlines are ignored (implicit line continuation)
                if self.bracket_depth > 0:
                    continue

                # Avoid duplicate back-to-back newlines
                if tokens and tokens[-1].type != TOK_NEWLINE:
                    tokens.append(Token(TOK_NEWLINE, "\n", start_line, start_col))
                continue

            start_line, start_col = self.line, self.col

            # Numbers: digits, or negative numeric literal
            is_neg_num = (
                ch == "-" and
                self.peek(1).isdigit() and
                (not tokens or tokens[-1].type in (TOK_OP, TOK_DELIM, TOK_NEWLINE, TOK_INDENT))
            )
            if ch.isdigit() or is_neg_num:
                tokens.append(self.lex_number(start_line, start_col, initial_neg=is_neg_num))
                continue

            # Raw strings: r"..." or r'...'
            if ch in ("r", "R") and self.peek(1) in ('"', "'"):
                self.advance()  # consume 'r'
                quote = self.advance()
                s_buf = []
                while self.peek() != quote and self.peek() != "\0":
                    s_buf.append(self.advance())
                if self.peek() == quote:
                    self.advance()
                tokens.append(Token(TOK_STRING, "".join(s_buf), start_line, start_col))
                continue

            # Strings
            if ch in ('"', "'"):
                quote = self.advance()
                tokens.append(self.lex_string(quote, start_line, start_col))
                continue

            # Identifiers and Keywords
            if ch.isalpha() or ch == "_":
                ident = []
                while self.peek().isalnum() or self.peek() == "_":
                    ident.append(self.advance())
                word = "".join(ident)

                if word in KEYWORDS:
                    tokens.append(Token(TOK_KEYWORD, word, start_line, start_col, len(word)))
                else:
                    tokens.append(Token(TOK_IDENT, word, start_line, start_col, len(word)))
                continue

            # Triple-character operators (<<=, >>=, **=, //=)
            three = self.peek() + self.peek(1) + self.peek(2)
            if three in TRI_OPS:
                self.advance()
                self.advance()
                self.advance()
                tokens.append(Token(TOK_OP, three, start_line, start_col, 3))
                continue

            # Dual-character operators (==, !=, <=, >=, +=, -=, *=, /=, %=, &=, |=, ^=, <<, >>, **, //, ->)
            two = self.peek() + self.peek(1)
            if two in DUAL_OPS:
                self.advance()
                self.advance()
                tokens.append(Token(TOK_OP, two, start_line, start_col, 2))
                continue

            # Single-character operators (+, -, *, /, %, &, |, ^, <, >, =, ~, !)
            if ch in SINGLE_OPS:
                self.advance()
                tokens.append(Token(TOK_OP, ch, start_line, start_col, 1))
                continue

            # Delimiters and Brackets
            if ch in DELIMITERS:
                self.advance()
                if ch in "([{":
                    self.bracket_depth += 1
                elif ch in ")]}":
                    if self.bracket_depth > 0:
                        self.bracket_depth -= 1
                tokens.append(Token(TOK_DELIM, ch, start_line, start_col, 1))
                continue

            # Unrecognized character fallback
            self.advance()

        # Emit remaining DEDENT tokens at EOF to close open blocks
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token(TOK_DEDENT, 0, self.line, self.col))

        tokens.append(Token(TOK_EOF, "", self.line, self.col))
        return tokens
