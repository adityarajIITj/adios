#!/usr/bin/env python3
"""
AdiPython Lexer
Tokenizes AdiPython source code into a clean token stream.
Supports both indentation-based blocks and semicolon/newline separators.
"""

import re

# Token Types
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

KEYWORDS = {
    "def", "return", "if", "elif", "else", "while", "for", "in", "range",
    "break", "continue", "pass", "global", "and", "or", "not", "True", "False", "None"
}

BUILTINS = {
    "print", "peek", "poke", "pixel", "line", "rect", "clear", "cls", "sleep", "tone"
}

class Token:
    def __init__(self, typ, value, line, col):
        self.type = typ
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)}, L{self.line}:{self.col})"

class Lexer:
    def __init__(self, source):
        self.source = source
        self.length = len(source)
        self.pos = 0
        self.line = 1
        self.col = 1
        self.indent_stack = [0]

    def peek(self, offset=0):
        idx = self.pos + offset
        return self.source[idx] if idx < self.length else "\0"

    def advance(self):
        ch = self.peek()
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self):
        tokens = []
        while self.pos < self.length:
            # Check indentation at beginning of line
            if self.col == 1:
                spaces = 0
                while self.peek() in (" ", "\t"):
                    spaces += 4 if self.advance() == "\t" else 1

                # If line is blank or comment, ignore indentation
                if self.peek() in ("\n", "\r", "#"):
                    if self.peek() == "#":
                        while self.peek() not in ("\n", "\0"):
                            self.advance()
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

            ch = self.peek()

            # Skip spaces inside line
            if ch in (" ", "\t"):
                self.advance()
                continue

            # Comments
            if ch == "#":
                while self.peek() not in ("\n", "\0"):
                    self.advance()
                continue

            # Newlines
            if ch in ("\n", "\r"):
                start_line, start_col = self.line, self.col
                if ch == "\r" and self.peek(1) == "\n":
                    self.advance()
                self.advance()
                # Don't emit consecutive newlines
                if tokens and tokens[-1].type != TOK_NEWLINE:
                    tokens.append(Token(TOK_NEWLINE, "\n", start_line, start_col))
                continue

            start_line, start_col = self.line, self.col

            # Numbers (Hex, Binary, Decimal)
            if ch.isdigit() or (ch == "-" and self.peek(1).isdigit() and (not tokens or tokens[-1].type in (TOK_OP, TOK_DELIM, TOK_NEWLINE))):
                num_str = self.advance()
                if num_str == "0" and self.peek() in ("x", "X"):
                    num_str += self.advance()
                    while self.peek() in "0123456789abcdefABCDEF_":
                        c = self.advance()
                        if c != "_": num_str += c
                    val = int(num_str, 16)
                elif num_str == "0" and self.peek() in ("b", "B"):
                    num_str += self.advance()
                    while self.peek() in "01_":
                        c = self.advance()
                        if c != "_": num_str += c
                    val = int(num_str, 2)
                else:
                    while self.peek().isdigit() or self.peek() == "_":
                        c = self.advance()
                        if c != "_": num_str += c
                    val = int(num_str)
                tokens.append(Token(TOK_NUMBER, val, start_line, start_col))
                continue

            # Strings
            if ch in ('"', "'"):
                quote = self.advance()
                s = []
                while self.peek() != quote and self.peek() != "\0":
                    c = self.advance()
                    if c == "\\" and self.peek() != "\0":
                        esc = self.advance()
                        if esc == "n": s.append("\n")
                        elif esc == "t": s.append("\t")
                        elif esc == "r": s.append("\r")
                        elif esc == "\\": s.append("\\")
                        elif esc == quote: s.append(quote)
                        else: s.append(esc)
                    else:
                        s.append(c)
                if self.peek() == quote:
                    self.advance()
                tokens.append(Token(TOK_STRING, "".join(s), start_line, start_col))
                continue

            # Identifiers and Keywords
            if ch.isalpha() or ch == "_":
                ident = []
                while self.peek().isalnum() or self.peek() == "_":
                    ident.append(self.advance())
                word = "".join(ident)
                if word in KEYWORDS:
                    tokens.append(Token(TOK_KEYWORD, word, start_line, start_col))
                elif word in BUILTINS:
                    tokens.append(Token(TOK_IDENT, word, start_line, start_col))
                else:
                    tokens.append(Token(TOK_IDENT, word, start_line, start_col))
                continue

            # Multi-char Operators
            two = self.peek() + self.peek(1)
            if two in ("==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "<<", ">>"):
                self.advance(); self.advance()
                tokens.append(Token(TOK_OP, two, start_line, start_col))
                continue

            # Single-char Operators
            if ch in "+-*/%&|^<>=":
                self.advance()
                tokens.append(Token(TOK_OP, ch, start_line, start_col))
                continue

            # Delimiters
            if ch in "():,;[]{}":
                self.advance()
                tokens.append(Token(TOK_DELIM, ch, start_line, start_col))
                continue

            # Unknown char
            self.advance()

        # Emit remaining DEDENT tokens at EOF
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token(TOK_DEDENT, 0, self.line, self.col))

        tokens.append(Token(TOK_EOF, "", self.line, self.col))
        return tokens
