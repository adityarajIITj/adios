#!/usr/bin/env python3
"""
AdiPython Recursive-Descent Parser
Builds an Abstract Syntax Tree (AST) from an AdiPython token stream.
"""

from .lexer import (
    TOK_EOF, TOK_NEWLINE, TOK_INDENT, TOK_DEDENT, TOK_NUMBER,
    TOK_STRING, TOK_IDENT, TOK_KEYWORD, TOK_OP, TOK_DELIM
)

# AST Nodes
class ASTNode: pass

class Program(ASTNode):
    def __init__(self, stmts):
        self.stmts = stmts

class Assign(ASTNode):
    def __init__(self, target, value):
        self.target = target
        self.value = value

class AugAssign(ASTNode):
    def __init__(self, target, op, value):
        self.target = target
        self.op = op
        self.value = value

class FunctionDef(ASTNode):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

class Return(ASTNode):
    def __init__(self, value):
        self.value = value

class If(ASTNode):
    def __init__(self, cond, then_body, elif_list=None, else_body=None):
        self.cond = cond
        self.then_body = then_body
        self.elif_list = elif_list or [] # list of (cond, body)
        self.else_body = else_body or []

class While(ASTNode):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class For(ASTNode):
    def __init__(self, var, start, end, step, body):
        self.var = var
        self.start = start
        self.end = end
        self.step = step
        self.body = body

class Break(ASTNode): pass
class Continue(ASTNode): pass

class ExprStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr

class Call(ASTNode):
    def __init__(self, name, args):
        self.name = name
        self.args = args

class BinaryOp(ASTNode):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

class UnaryOp(ASTNode):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

class Number(ASTNode):
    def __init__(self, value):
        self.value = value

class String(ASTNode):
    def __init__(self, value):
        self.value = value

class Identifier(ASTNode):
    def __init__(self, name):
        self.name = name

# Parser Implementation
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0):
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def advance(self):
        tok = self.peek()
        if self.pos < len(self.tokens):
            self.pos += 1
        return tok

    def match(self, typ, value=None):
        tok = self.peek()
        if tok.type == typ and (value is None or tok.value == value):
            return self.advance()
        return None

    def expect(self, typ, value=None):
        tok = self.match(typ, value)
        if not tok:
            curr = self.peek()
            raise SyntaxError(f"Expected {typ} {value or ''} at L{curr.line}:{curr.col}, got {curr.type}({curr.value})")
        return tok

    def skip_newlines(self):
        while self.match(TOK_NEWLINE): pass

    def parse(self):
        stmts = []
        self.skip_newlines()
        while self.peek().type != TOK_EOF:
            stmt = self.parse_statement()
            if stmt:
                stmts.append(stmt)
            self.skip_newlines()
        return Program(stmts)

    def parse_statement(self):
        self.skip_newlines()
        tok = self.peek()

        if tok.type == TOK_KEYWORD:
            if tok.value == "def":
                return self.parse_function()
            if tok.value == "return":
                self.advance()
                val = self.parse_expression() if self.peek().type not in (TOK_NEWLINE, TOK_EOF) else None
                return Return(val)
            if tok.value == "if":
                return self.parse_if()
            if tok.value == "while":
                return self.parse_while()
            if tok.value == "for":
                return self.parse_for()
            if tok.value == "pass":
                self.advance()
                return None
            if tok.value == "global":
                self.advance()
                while True:
                    self.expect(TOK_IDENT)
                    if self.match(TOK_DELIM, ","): continue
                    break
                return None
            if tok.value == "break":
                self.advance()
                return Break()
            if tok.value == "continue":
                self.advance()
                return Continue()

        # Check for assignment: ident = expr or ident += expr
        if tok.type == TOK_IDENT and self.peek(1).type == TOK_OP and self.peek(1).value in ("=", "+=", "-="):
            name = self.advance().value
            op = self.advance().value
            val = self.parse_expression()
            if op == "=":
                return Assign(name, val)
            else:
                return AugAssign(name, op[0], val)

        # Expression statement
        expr = self.parse_expression()
        return ExprStmt(expr)

    def parse_block(self):
        """Parses a block of statements (indented or single-line)."""
        self.expect(TOK_DELIM, ":")
        if self.peek().type != TOK_NEWLINE:
            # Single-line statement, e.g. if cond: return 0
            stmt = self.parse_statement()
            return [stmt] if stmt else []

        self.expect(TOK_NEWLINE)
        self.expect(TOK_INDENT)
        stmts = []
        while self.peek().type not in (TOK_DEDENT, TOK_EOF):
            stmt = self.parse_statement()
            if stmt:
                stmts.append(stmt)
            self.skip_newlines()
        self.expect(TOK_DEDENT)
        return stmts

    def parse_function(self):
        self.expect(TOK_KEYWORD, "def")
        name = self.expect(TOK_IDENT).value
        self.expect(TOK_DELIM, "(")
        params = []
        if not self.match(TOK_DELIM, ")"):
            while True:
                params.append(self.expect(TOK_IDENT).value)
                if self.match(TOK_DELIM, ","): continue
                self.expect(TOK_DELIM, ")")
                break
        body = self.parse_block()
        return FunctionDef(name, params, body)

    def parse_if(self):
        self.expect(TOK_KEYWORD, "if")
        cond = self.parse_expression()
        then_body = self.parse_block()
        elif_list = []
        else_body = []

        while self.peek().type == TOK_KEYWORD and self.peek().value == "elif":
            self.advance()
            e_cond = self.parse_expression()
            e_body = self.parse_block()
            elif_list.append((e_cond, e_body))

        if self.peek().type == TOK_KEYWORD and self.peek().value == "else":
            self.advance()
            else_body = self.parse_block()

        return If(cond, then_body, elif_list, else_body)

    def parse_while(self):
        self.expect(TOK_KEYWORD, "while")
        cond = self.parse_expression()
        body = self.parse_block()
        return While(cond, body)

    def parse_for(self):
        # Syntax: for i in range(start, end): ...
        self.expect(TOK_KEYWORD, "for")
        var = self.expect(TOK_IDENT).value
        self.expect(TOK_KEYWORD, "in")
        if not (self.match(TOK_IDENT, "range") or self.match(TOK_KEYWORD, "range")):
            raise SyntaxError("Expected 'range' in for loop")
        self.expect(TOK_DELIM, "(")
        first = self.parse_expression()
        second = None
        step = Number(1)

        if self.match(TOK_DELIM, ","):
            second = self.parse_expression()
            if self.match(TOK_DELIM, ","):
                step = self.parse_expression()
        self.expect(TOK_DELIM, ")")

        if second is None:
            start = Number(0)
            end = first
        else:
            start = first
            end = second

        body = self.parse_block()
        return For(var, start, end, step, body)

    # -------------------------------------------------------------------------
    # Expression Parsing with Precedence Climbing
    # -------------------------------------------------------------------------
    def parse_expression(self):
        return self.parse_logical_or()

    def parse_logical_or(self):
        left = self.parse_logical_and()
        while self.match(TOK_KEYWORD, "or"):
            right = self.parse_logical_and()
            left = BinaryOp(left, "or", right)
        return left

    def parse_logical_and(self):
        left = self.parse_equality()
        while self.match(TOK_KEYWORD, "and"):
            right = self.parse_equality()
            left = BinaryOp(left, "and", right)
        return left

    def parse_equality(self):
        left = self.parse_comparison()
        while self.peek().type == TOK_OP and self.peek().value in ("==", "!="):
            op = self.advance().value
            right = self.parse_comparison()
            left = BinaryOp(left, op, right)
        return left

    def parse_comparison(self):
        left = self.parse_bitwise()
        while self.peek().type == TOK_OP and self.peek().value in ("<", "<=", ">", ">="):
            op = self.advance().value
            right = self.parse_bitwise()
            left = BinaryOp(left, op, right)
        return left

    def parse_bitwise(self):
        left = self.parse_term()
        while self.peek().type == TOK_OP and self.peek().value in ("&", "|", "^", "<<", ">>"):
            op = self.advance().value
            right = self.parse_term()
            left = BinaryOp(left, op, right)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.peek().type == TOK_OP and self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_factor()
            left = BinaryOp(left, op, right)
        return left

    def parse_factor(self):
        left = self.parse_unary()
        while self.peek().type == TOK_OP and self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.parse_unary()
            left = BinaryOp(left, op, right)
        return left

    def parse_unary(self):
        if self.peek().type == TOK_OP and self.peek().value in ("-", "~", "!"):
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryOp(op, operand)
        if self.match(TOK_KEYWORD, "not"):
            operand = self.parse_unary()
            return UnaryOp("not", operand)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()

        if tok.type == TOK_NUMBER:
            return Number(self.advance().value)
        if tok.type == TOK_STRING:
            return String(self.advance().value)
        if tok.type == TOK_KEYWORD and tok.value == "True":
            self.advance()
            return Number(1)
        if tok.type == TOK_KEYWORD and tok.value == "False":
            self.advance()
            return Number(0)

        if tok.type == TOK_IDENT:
            name = self.advance().value
            # Check for function call
            if self.match(TOK_DELIM, "("):
                args = []
                if not self.match(TOK_DELIM, ")"):
                    while True:
                        args.append(self.parse_expression())
                        if self.match(TOK_DELIM, ","): continue
                        self.expect(TOK_DELIM, ")")
                        break
                return Call(name, args)
            return Identifier(name)

        if self.match(TOK_DELIM, "("):
            expr = self.parse_expression()
            self.expect(TOK_DELIM, ")")
            return expr

        raise SyntaxError(f"Unexpected token {tok.type}({tok.value}) at L{tok.line}:{tok.col}")
