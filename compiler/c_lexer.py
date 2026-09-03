#!/usr/bin/env python3
"""
AdiOS C99 / AdiC Toolchain: Lexical Analyzer (c_lexer.py)
Tokenizes standard C source code into a structured token stream.
Supports keywords, identifiers, integer/hex literals, string/char literals,
and multi-character operators (++, --, ->, <<, >>, <=, >=, ==, !=, &&, ||).
Zero external dependencies.
"""

import re
from enum import Enum, auto

class TokenType(Enum):
    EOF             = auto()
    IDENTIFIER      = auto()
    INT_LITERAL     = auto()
    HEX_LITERAL     = auto()
    STRING_LITERAL  = auto()
    CHAR_LITERAL    = auto()

    # Keywords
    KW_VOID         = auto()
    KW_CHAR         = auto()
    KW_SHORT        = auto()
    KW_INT          = auto()
    KW_LONG         = auto()
    KW_FLOAT        = auto()
    KW_DOUBLE       = auto()
    KW_SIGNED       = auto()
    KW_UNSIGNED     = auto()
    KW_STRUCT       = auto()
    KW_UNION        = auto()
    KW_ENUM         = auto()
    KW_TYPEDEF      = auto()
    KW_CONST        = auto()
    KW_VOLATILE     = auto()
    KW_STATIC       = auto()
    KW_EXTERN       = auto()
    KW_INLINE       = auto()
    KW_SIZEOF       = auto()
    KW_IF           = auto()
    KW_ELSE         = auto()
    KW_SWITCH       = auto()
    KW_CASE         = auto()
    KW_DEFAULT      = auto()
    KW_FOR          = auto()
    KW_WHILE        = auto()
    KW_DO           = auto()
    KW_BREAK        = auto()
    KW_CONTINUE     = auto()
    KW_RETURN       = auto()
    KW_GOTO         = auto()

    # Operators & Punctuation
    PLUS            = auto()  # +
    MINUS           = auto()  # -
    STAR            = auto()  # *
    SLASH           = auto()  # /
    PERCENT         = auto()  # %
    INC             = auto()  # ++
    DEC             = auto()  # --
    ARROW           = auto()  # ->
    DOT             = auto()  # .
    ASSIGN          = auto()  # =
    PLUS_ASSIGN     = auto()  # +=
    MINUS_ASSIGN    = auto()  # -=
    MUL_ASSIGN      = auto()  # *=
    DIV_ASSIGN      = auto()  # /=
    EQ              = auto()  # ==
    NEQ             = auto()  # !=
    LT              = auto()  # <
    GT              = auto()  # >
    LE              = auto()  # <=
    GE              = auto()  # >=
    AMP             = auto()  # &
    PIPE            = auto()  # |
    CARET           = auto()  # ^
    TILDE           = auto()  # ~
    BANG            = auto()  # !
    LOG_AND         = auto()  # &&
    LOG_OR          = auto()  # ||
    LSHIFT          = auto()  # <<
    RSHIFT          = auto()  # >>
    QUESTION        = auto()  # ?
    COLON           = auto()  # :
    SEMICOLON       = auto()  # ;
    COMMA           = auto()  # ,
    LPAREN          = auto()  # (
    RPAREN          = auto()  # )
    LBRACKET        = auto()  # [
    RBRACKET        = auto()  # ]
    LBRACE          = auto()  # {
    RBRACE          = auto()  # }

KEYWORDS = {
    "void": TokenType.KW_VOID, "char": TokenType.KW_CHAR, "short": TokenType.KW_SHORT,
    "int": TokenType.KW_INT, "long": TokenType.KW_LONG, "float": TokenType.KW_FLOAT,
    "double": TokenType.KW_DOUBLE, "signed": TokenType.KW_SIGNED, "unsigned": TokenType.KW_UNSIGNED,
    "struct": TokenType.KW_STRUCT, "union": TokenType.KW_UNION, "enum": TokenType.KW_ENUM,
    "typedef": TokenType.KW_TYPEDEF, "const": TokenType.KW_CONST, "volatile": TokenType.KW_VOLATILE,
    "static": TokenType.KW_STATIC, "extern": TokenType.KW_EXTERN, "inline": TokenType.KW_INLINE,
    "sizeof": TokenType.KW_SIZEOF, "if": TokenType.KW_IF, "else": TokenType.KW_ELSE,
    "switch": TokenType.KW_SWITCH, "case": TokenType.KW_CASE, "default": TokenType.KW_DEFAULT,
    "for": TokenType.KW_FOR, "while": TokenType.KW_WHILE, "do": TokenType.KW_DO,
    "break": TokenType.KW_BREAK, "continue": TokenType.KW_CONTINUE, "return": TokenType.KW_RETURN,
    "goto": TokenType.KW_GOTO,
}

class Token:
    def __init__(self, typ: TokenType, value: any, line: int, col: int):
        self.type = typ
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type.name}, {repr(self.value)}, L{self.line}:{self.col})"

class CLexer:
    """
    Stateful lexical analyzer for C99 source files.
    """
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    def tokenize(self) -> list:
        while self.pos < len(self.source):
            c = self.source[self.pos]

            # Whitespace
            if c == '\n':
                self.pos += 1
                self.line += 1
                self.col = 1
                continue
            if c in ' \t\r':
                self.pos += 1
                self.col += 1
                continue

            # Comments
            if c == '/' and self.peek(1) == '/':
                # Single-line comment
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self.pos += 1
                continue
            if c == '/' and self.peek(1) == '*':
                # Multi-line comment
                self.pos += 2
                self.col += 2
                while self.pos < len(self.source) - 1 and not (self.source[self.pos] == '*' and self.source[self.pos + 1] == '/'):
                    if self.source[self.pos] == '\n':
                        self.line += 1
                        self.col = 1
                    else:
                        self.col += 1
                    self.pos += 1
                self.pos += 2
                self.col += 2
                continue

            start_col = self.col

            # Identifiers and Keywords
            if c.isalpha() or c == '_':
                ident = self.consume_ident()
                kw_type = KEYWORDS.get(ident, TokenType.IDENTIFIER)
                self.tokens.append(Token(kw_type, ident, self.line, start_col))
                continue

            # Numeric Literals (Hex and Decimal)
            if c.isdigit():
                if c == '0' and self.peek(1) in ('x', 'X'):
                    hex_val = self.consume_hex()
                    self.tokens.append(Token(TokenType.HEX_LITERAL, hex_val, self.line, start_col))
                else:
                    dec_val = self.consume_dec()
                    self.tokens.append(Token(TokenType.INT_LITERAL, dec_val, self.line, start_col))
                continue

            # String Literals
            if c == '"':
                s = self.consume_string()
                self.tokens.append(Token(TokenType.STRING_LITERAL, s, self.line, start_col))
                continue

            # Char Literals
            if c == "'":
                ch = self.consume_char()
                self.tokens.append(Token(TokenType.CHAR_LITERAL, ch, self.line, start_col))
                continue

            # Multi-character Operators
            two = self.source[self.pos:self.pos + 2]
            if two == "++":
                self.advance(2); self.tokens.append(Token(TokenType.INC, "++", self.line, start_col)); continue
            if two == "--":
                self.advance(2); self.tokens.append(Token(TokenType.DEC, "--", self.line, start_col)); continue
            if two == "->":
                self.advance(2); self.tokens.append(Token(TokenType.ARROW, "->", self.line, start_col)); continue
            if two == "==":
                self.advance(2); self.tokens.append(Token(TokenType.EQ, "==", self.line, start_col)); continue
            if two == "!=":
                self.advance(2); self.tokens.append(Token(TokenType.NEQ, "!=", self.line, start_col)); continue
            if two == "<=":
                self.advance(2); self.tokens.append(Token(TokenType.LE, "<=", self.line, start_col)); continue
            if two == ">=":
                self.advance(2); self.tokens.append(Token(TokenType.GE, ">=", self.line, start_col)); continue
            if two == "&&":
                self.advance(2); self.tokens.append(Token(TokenType.LOG_AND, "&&", self.line, start_col)); continue
            if two == "||":
                self.advance(2); self.tokens.append(Token(TokenType.LOG_OR, "||", self.line, start_col)); continue
            if two == "<<":
                self.advance(2); self.tokens.append(Token(TokenType.LSHIFT, "<<", self.line, start_col)); continue
            if two == ">>":
                self.advance(2); self.tokens.append(Token(TokenType.RSHIFT, ">>", self.line, start_col)); continue
            if two == "+=":
                self.advance(2); self.tokens.append(Token(TokenType.PLUS_ASSIGN, "+=", self.line, start_col)); continue
            if two == "-=":
                self.advance(2); self.tokens.append(Token(TokenType.MINUS_ASSIGN, "-=", self.line, start_col)); continue
            if two == "*=":
                self.advance(2); self.tokens.append(Token(TokenType.MUL_ASSIGN, "*=", self.line, start_col)); continue
            if two == "/=":
                self.advance(2); self.tokens.append(Token(TokenType.DIV_ASSIGN, "/=", self.line, start_col)); continue

            # Single-character Operators
            singles = {
                '+': TokenType.PLUS, '-': TokenType.MINUS, '*': TokenType.STAR, '/': TokenType.SLASH,
                '%': TokenType.PERCENT, '=': TokenType.ASSIGN, '<': TokenType.LT, '>': TokenType.GT,
                '&': TokenType.AMP, '|': TokenType.PIPE, '^': TokenType.CARET, '~': TokenType.TILDE,
                '!': TokenType.BANG, '?': TokenType.QUESTION, ':': TokenType.COLON, ';': TokenType.SEMICOLON,
                ',': TokenType.COMMA, '.': TokenType.DOT, '(': TokenType.LPAREN, ')': TokenType.RPAREN,
                '[': TokenType.LBRACKET, ']': TokenType.RBRACKET, '{': TokenType.LBRACE, '}': TokenType.RBRACE,
            }
            if c in singles:
                self.advance(1)
                self.tokens.append(Token(singles[c], c, self.line, start_col))
                continue

            raise SyntaxError(f"Unexpected character '{c}' at line {self.line}, col {self.col}")

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    def advance(self, n: int = 1):
        self.pos += n
        self.col += n

    def peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ''

    def consume_ident(self) -> str:
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            self.pos += 1
            self.col += 1
        return self.source[start:self.pos]

    def consume_dec(self) -> int:
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            self.pos += 1
            self.col += 1
        return int(self.source[start:self.pos])

    def consume_hex(self) -> int:
        self.advance(2) # Skip 0x
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] in "0123456789abcdefABCDEF":
            self.pos += 1
            self.col += 1
        return int(self.source[start:self.pos], 16)

    def consume_string(self) -> str:
        self.advance(1) # Skip opening quote
        chars = []
        while self.pos < len(self.source) and self.source[self.pos] != '"':
            if self.source[self.pos] == '\\':
                self.advance(1)
                esc = self.source[self.pos]
                if esc == 'n': chars.append('\n')
                elif esc == 'r': chars.append('\r')
                elif esc == 't': chars.append('\t')
                elif esc == '0': chars.append('\0')
                else: chars.append(esc)
            else:
                chars.append(self.source[self.pos])
            self.advance(1)
        self.advance(1) # Skip closing quote
        return "".join(chars)

    def consume_char(self) -> int:
        self.advance(1) # Skip opening '
        if self.source[self.pos] == '\\':
            self.advance(1)
            esc = self.source[self.pos]
            val = ord('\n') if esc == 'n' else (ord('\0') if esc == '0' else ord(esc))
        else:
            val = ord(self.source[self.pos])
        self.advance(1)
        self.advance(1) # Skip closing '
        return val

if __name__ == "__main__":
    src = """
    int main(int argc, char** argv) {
        int x = 42 + 0x2A;
        if (x == 84 && x != 0) {
            return x;
        }
        return 0;
    }
    """
    lexer = CLexer(src)
    toks = lexer.tokenize()
    print(f"Tokenized {len(toks)} tokens.")
    assert toks[0].type == TokenType.KW_INT
    assert toks[1].value == "main"
    print("C Lexer verified.")
