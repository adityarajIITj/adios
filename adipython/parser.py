#!/usr/bin/env python3
"""
AdiPython Recursive-Descent Parser (Deepened Systems Architecture)
Builds an Abstract Syntax Tree (AST) from an AdiPython token stream.

Supported Grammar Productions:
- Functions, parameters, return statements, and recursion
- Control flow: if / elif / else, while / else, for / else
- Exception blocks: try / except / finally and raise statements
- Assertions: assert test, "message"
- Augmented assignments: +=, -=, *=, /=, %=, &=, |=, ^=, <<=, >>=, **=, //=
- Subscripts and Slicing: obj[index], obj[start:stop], obj[start:stop:step]
- Data structures: list literals [1, 2], dict literals {"k": v}, tuple literals (1, 2)
- Attributes & method invocation chaining: obj.method(arg).subfield
- Expression precedence climbing: ternary (x if c else y), logical, equality,
  relational, bitwise, shifts, arithmetic, unary, and exponentiation.
- AST Visitor and Transformer traversal frameworks.
"""

from .lexer import (
    TOK_EOF, TOK_NEWLINE, TOK_INDENT, TOK_DEDENT, TOK_NUMBER,
    TOK_STRING, TOK_IDENT, TOK_KEYWORD, TOK_OP, TOK_DELIM
)


# =============================================================================
# Abstract Syntax Tree (AST) Node Hierarchy
# =============================================================================

class ASTNode:
    """Base class for all AST nodes with source position metadata."""
    def __init__(self, lineno: int = 0, col_offset: int = 0):
        self.lineno = lineno
        self.col_offset = col_offset

    def __repr__(self) -> str:
        attrs = [f"{k}={repr(v)}" for k, v in self.__dict__.items()
                 if not k.startswith("_") and k not in ("lineno", "col_offset")]
        return f"{self.__class__.__name__}({', '.join(attrs)})"


class Program(ASTNode):
    def __init__(self, stmts, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.stmts = stmts


class Assign(ASTNode):
    def __init__(self, target, value, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.target = target  # str or Subscript / Attribute
        self.value = value


class AugAssign(ASTNode):
    def __init__(self, target, op, value, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.target = target  # str or Subscript / Attribute
        self.op = op          # "+=", "-=", "*=", etc. or "+", "-"
        self.value = value


class FunctionDef(ASTNode):
    def __init__(self, name, params, body, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.name = name
        self.params = params
        self.body = body


class Return(ASTNode):
    def __init__(self, value=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.value = value


class If(ASTNode):
    def __init__(self, cond, then_body, elif_list=None, else_body=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.cond = cond
        self.then_body = then_body
        self.elif_list = elif_list or []  # List of (cond, body) tuples
        self.else_body = else_body or []


class While(ASTNode):
    def __init__(self, cond, body, else_body=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.cond = cond
        self.body = body
        self.else_body = else_body or []


class For(ASTNode):
    def __init__(self, var, start, end, step, body, iter_expr=None, else_body=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.var = var
        self.start = start
        self.end = end
        self.step = step
        self.body = body
        self.iter_expr = iter_expr
        self.else_body = else_body or []


class Try(ASTNode):
    def __init__(self, body, handlers=None, else_body=None, finalbody=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.body = body
        self.handlers = handlers or []  # List of ExceptHandler nodes
        self.else_body = else_body or []
        self.finalbody = finalbody or []


class ExceptHandler(ASTNode):
    def __init__(self, exc_type=None, name=None, body=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.exc_type = exc_type  # str or None (catch-all)
        self.name = name          # variable name bound to exception or None
        self.body = body or []


class Raise(ASTNode):
    def __init__(self, exc=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.exc = exc


class Assert(ASTNode):
    def __init__(self, test, msg=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.test = test
        self.msg = msg


class Break(ASTNode):
    pass


class Continue(ASTNode):
    pass


class Pass(ASTNode):
    pass


class Global(ASTNode):
    def __init__(self, names, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.names = names


class ExprStmt(ASTNode):
    def __init__(self, expr, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.expr = expr


# -----------------------------------------------------------------------------
# Expression Nodes
# -----------------------------------------------------------------------------

class IfExp(ASTNode):
    """Ternary expression: body if cond else orelse"""
    def __init__(self, cond, body, orelse, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.cond = cond
        self.body = body
        self.orelse = orelse


class BinaryOp(ASTNode):
    def __init__(self, left, op, right, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.left = left
        self.op = op
        self.right = right


class UnaryOp(ASTNode):
    def __init__(self, op, operand, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.op = op
        self.operand = operand


class Call(ASTNode):
    def __init__(self, name, args, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.name = name  # str or callable expression
        self.args = args


class Subscript(ASTNode):
    """Array or dictionary subscript indexing: value[slice]"""
    def __init__(self, value, slice_node, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.value = value
        self.slice = slice_node


class Slice(ASTNode):
    """Slice specification: lower:upper:step"""
    def __init__(self, lower=None, upper=None, step=None, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.lower = lower
        self.upper = upper
        self.step = step


class Attribute(ASTNode):
    """Attribute access or method binding: value.attr"""
    def __init__(self, value, attr, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.value = value
        self.attr = attr


class ListLiteral(ASTNode):
    def __init__(self, elements, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.elements = elements


class DictLiteral(ASTNode):
    def __init__(self, keys, values, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.keys = keys
        self.values = values


class TupleLiteral(ASTNode):
    def __init__(self, elements, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.elements = elements


class Number(ASTNode):
    def __init__(self, value, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.value = value


class String(ASTNode):
    def __init__(self, value, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.value = value


class Identifier(ASTNode):
    def __init__(self, name, lineno=0, col_offset=0):
        super().__init__(lineno, col_offset)
        self.name = name


# =============================================================================
# AST Visitor & Transformer Base Classes
# =============================================================================

class NodeVisitor:
    """Recursively traverses an AST, invoking visit_<NodeName> methods."""
    def visit(self, node):
        if node is None:
            return None
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        for field, value in node.__dict__.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ASTNode):
                        self.visit(item)
            elif isinstance(value, ASTNode):
                self.visit(value)


class NodeTransformer(NodeVisitor):
    """Walks the AST and allows nodes to be replaced or modified in-place."""
    def generic_visit(self, node):
        for field, value in list(node.__dict__.items()):
            if isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, ASTNode):
                        new_node = self.visit(item)
                        if new_node is not None:
                            new_list.append(new_node)
                    else:
                        new_list.append(item)
                setattr(node, field, new_list)
            elif isinstance(value, ASTNode):
                new_node = self.visit(value)
                setattr(node, field, new_node)
        return node


# =============================================================================
# Recursive-Descent Parser Implementation
# =============================================================================

class Parser:
    """
    Syntactic Parser for AdiPython.
    Converts a stream of tokens into an Abstract Syntax Tree (AST).
    """
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0):
        """Returns the token at pos + offset."""
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def advance(self):
        """Consumes and returns the current token."""
        tok = self.peek()
        if self.pos < len(self.tokens):
            self.pos += 1
        return tok

    def match(self, typ: str, value=None):
        """Matches current token against typ and optional value; advances if matched."""
        tok = self.peek()
        if tok.type == typ and (value is None or tok.value == value):
            return self.advance()
        return None

    def expect(self, typ: str, value=None):
        """Demands that the current token match typ and value, or raises SyntaxError."""
        tok = self.match(typ, value)
        if not tok:
            curr = self.peek()
            val_str = f" '{value}'" if value else ""
            raise SyntaxError(
                f"Expected {typ}{val_str} at L{curr.line}:{curr.col}, "
                f"got {curr.type}('{curr.value}')"
            )
        return tok

    def skip_newlines(self):
        """Discards sequential newline tokens."""
        while self.match(TOK_NEWLINE):
            pass

    # -------------------------------------------------------------------------
    # Top-Level Program & Statement Parsing
    # -------------------------------------------------------------------------
    def parse(self) -> Program:
        """Parses an entire program into a Program AST node."""
        stmts = []
        self.skip_newlines()
        while self.peek().type != TOK_EOF:
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
            self.skip_newlines()
        return Program(stmts)

    def parse_statement(self):
        """Parses a single statement or declaration."""
        self.skip_newlines()
        tok = self.peek()

        if tok.type == TOK_KEYWORD:
            if tok.value == "def":
                return self.parse_function()
            if tok.value == "return":
                return self.parse_return()
            if tok.value == "if":
                return self.parse_if()
            if tok.value == "while":
                return self.parse_while()
            if tok.value == "for":
                return self.parse_for()
            if tok.value == "try":
                return self.parse_try()
            if tok.value == "raise":
                return self.parse_raise()
            if tok.value == "assert":
                return self.parse_assert()
            if tok.value == "pass":
                t = self.advance()
                return Pass(lineno=t.line, col_offset=t.col)
            if tok.value == "break":
                t = self.advance()
                return Break(lineno=t.line, col_offset=t.col)
            if tok.value == "continue":
                t = self.advance()
                return Continue(lineno=t.line, col_offset=t.col)
            if tok.value == "global":
                return self.parse_global()

        # Check for assignment: target = expr or target += expr
        # Lookahead to see if this is an assignment to identifier, subscript, or attribute
        expr = self.parse_expression()

        tok_next = self.peek()
        # Augmented assignment operators
        aug_ops = (
            "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
            "<<=", ">>=", "**=", "//="
        )
        if tok_next.type == TOK_OP and tok_next.value in aug_ops:
            op_tok = self.advance()
            val = self.parse_expression()
            # Normalize target: if identifier, pass string name; otherwise pass node
            target_name = expr.name if isinstance(expr, Identifier) else expr
            # Extract basic op: e.g. "+=" -> "+"
            clean_op = op_tok.value[:-1] if op_tok.value.endswith("=") else op_tok.value
            return AugAssign(target_name, clean_op, val, lineno=op_tok.line, col_offset=op_tok.col)

        if tok_next.type == TOK_OP and tok_next.value == "=":
            op_tok = self.advance()
            val = self.parse_expression()
            target_name = expr.name if isinstance(expr, Identifier) else expr
            return Assign(target_name, val, lineno=op_tok.line, col_offset=op_tok.col)

        return ExprStmt(expr, lineno=expr.lineno, col_offset=expr.col_offset)

    def parse_block(self):
        """Parses an indented block of statements, or a single-line statement."""
        self.expect(TOK_DELIM, ":")
        if self.peek().type != TOK_NEWLINE:
            # Single-line block: def f(): return 42
            stmt = self.parse_statement()
            return [stmt] if stmt else []

        self.expect(TOK_NEWLINE)
        self.expect(TOK_INDENT)
        stmts = []
        while self.peek().type not in (TOK_DEDENT, TOK_EOF):
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
            self.skip_newlines()
        self.expect(TOK_DEDENT)
        return stmts

    # -------------------------------------------------------------------------
    # Compound Statement Handlers
    # -------------------------------------------------------------------------
    def parse_function(self):
        tok = self.expect(TOK_KEYWORD, "def")
        name = self.expect(TOK_IDENT).value
        self.expect(TOK_DELIM, "(")
        params = []
        if not self.match(TOK_DELIM, ")"):
            while True:
                params.append(self.expect(TOK_IDENT).value)
                if self.match(TOK_DELIM, ","):
                    continue
                self.expect(TOK_DELIM, ")")
                break
        body = self.parse_block()
        return FunctionDef(name, params, body, lineno=tok.line, col_offset=tok.col)

    def parse_return(self):
        tok = self.expect(TOK_KEYWORD, "return")
        val = None
        if self.peek().type not in (TOK_NEWLINE, TOK_EOF, TOK_DEDENT):
            val = self.parse_expression()
        return Return(val, lineno=tok.line, col_offset=tok.col)

    def parse_if(self):
        tok = self.expect(TOK_KEYWORD, "if")
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

        return If(cond, then_body, elif_list, else_body, lineno=tok.line, col_offset=tok.col)

    def parse_while(self):
        tok = self.expect(TOK_KEYWORD, "while")
        cond = self.parse_expression()
        body = self.parse_block()
        else_body = []
        if self.peek().type == TOK_KEYWORD and self.peek().value == "else":
            self.advance()
            else_body = self.parse_block()
        return While(cond, body, else_body, lineno=tok.line, col_offset=tok.col)

    def parse_for(self):
        """
        Parses for loop:
        1. Range iteration: for i in range(start, end, step): ...
        2. Generic sequence iteration: for item in seq: ...
        """
        tok = self.expect(TOK_KEYWORD, "for")
        var = self.expect(TOK_IDENT).value
        self.expect(TOK_KEYWORD, "in")

        # Check if right-hand side is a range(...) call
        if (self.peek().type in (TOK_IDENT, TOK_KEYWORD) and self.peek().value == "range" and
            self.peek(1).type == TOK_DELIM and self.peek(1).value == "("):
            self.advance()  # 'range'
            self.advance()  # '('
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
            else_body = []
            if self.peek().type == TOK_KEYWORD and self.peek().value == "else":
                self.advance()
                else_body = self.parse_block()
            return For(var, start, end, step, body, else_body=else_body, lineno=tok.line, col_offset=tok.col)

        # Generic iterable expression
        iter_expr = self.parse_expression()
        body = self.parse_block()
        else_body = []
        if self.peek().type == TOK_KEYWORD and self.peek().value == "else":
            self.advance()
            else_body = self.parse_block()
        return For(var, Number(0), Number(0), Number(1), body, iter_expr=iter_expr,
                   else_body=else_body, lineno=tok.line, col_offset=tok.col)

    def parse_try(self):
        """Parses try / except [Exc as name] / else / finally construct."""
        tok = self.expect(TOK_KEYWORD, "try")
        body = self.parse_block()
        handlers = []
        else_body = []
        finalbody = []

        while self.peek().type == TOK_KEYWORD and self.peek().value == "except":
            h_tok = self.advance()
            exc_type = None
            name = None
            if self.peek().type not in (TOK_DELIM, TOK_NEWLINE) and self.peek().value != ":":
                exc_type = self.expect(TOK_IDENT).value
                if self.match(TOK_KEYWORD, "as"):
                    name = self.expect(TOK_IDENT).value
            h_body = self.parse_block()
            handlers.append(ExceptHandler(exc_type, name, h_body, lineno=h_tok.line, col_offset=h_tok.col))

        if self.peek().type == TOK_KEYWORD and self.peek().value == "else":
            self.advance()
            else_body = self.parse_block()

        if self.peek().type == TOK_KEYWORD and self.peek().value == "finally":
            self.advance()
            finalbody = self.parse_block()

        return Try(body, handlers, else_body, finalbody, lineno=tok.line, col_offset=tok.col)

    def parse_raise(self):
        tok = self.expect(TOK_KEYWORD, "raise")
        exc = None
        if self.peek().type not in (TOK_NEWLINE, TOK_EOF, TOK_DEDENT):
            exc = self.parse_expression()
        return Raise(exc, lineno=tok.line, col_offset=tok.col)

    def parse_assert(self):
        tok = self.expect(TOK_KEYWORD, "assert")
        test = self.parse_expression()
        msg = None
        if self.match(TOK_DELIM, ","):
            msg = self.parse_expression()
        return Assert(test, msg, lineno=tok.line, col_offset=tok.col)

    def parse_global(self):
        tok = self.expect(TOK_KEYWORD, "global")
        names = []
        while True:
            names.append(self.expect(TOK_IDENT).value)
            if self.match(TOK_DELIM, ","):
                continue
            break
        return Global(names, lineno=tok.line, col_offset=tok.col)

    # -------------------------------------------------------------------------
    # Expression Parsing with Precedence Climbing
    # -------------------------------------------------------------------------
    def parse_expression(self):
        """Parses expressions with ternary conditional operator support."""
        expr = self.parse_logical_or()
        if self.match(TOK_KEYWORD, "if"):
            cond = self.parse_logical_or()
            self.expect(TOK_KEYWORD, "else")
            orelse = self.parse_expression()
            return IfExp(cond, expr, orelse, lineno=expr.lineno, col_offset=expr.col_offset)
        return expr

    def parse_logical_or(self):
        left = self.parse_logical_and()
        while self.match(TOK_KEYWORD, "or"):
            right = self.parse_logical_and()
            left = BinaryOp(left, "or", right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_logical_and(self):
        left = self.parse_equality()
        while self.match(TOK_KEYWORD, "and"):
            right = self.parse_equality()
            left = BinaryOp(left, "and", right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_equality(self):
        left = self.parse_comparison()
        while self.peek().type == TOK_OP and self.peek().value in ("==", "!="):
            op = self.advance().value
            right = self.parse_comparison()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_comparison(self):
        left = self.parse_bitwise_or()
        while self.peek().type == TOK_OP and self.peek().value in ("<", "<=", ">", ">="):
            op = self.advance().value
            right = self.parse_bitwise_or()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_bitwise_or(self):
        left = self.parse_bitwise_xor()
        while self.peek().type == TOK_OP and self.peek().value == "|":
            op = self.advance().value
            right = self.parse_bitwise_xor()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_bitwise_xor(self):
        left = self.parse_bitwise_and()
        while self.peek().type == TOK_OP and self.peek().value == "^":
            op = self.advance().value
            right = self.parse_bitwise_and()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_bitwise_and(self):
        left = self.parse_shifts()
        while self.peek().type == TOK_OP and self.peek().value == "&":
            op = self.advance().value
            right = self.parse_shifts()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_shifts(self):
        left = self.parse_term()
        while self.peek().type == TOK_OP and self.peek().value in ("<<", ">>"):
            op = self.advance().value
            right = self.parse_term()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.peek().type == TOK_OP and self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_factor()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_factor(self):
        left = self.parse_power()
        while self.peek().type == TOK_OP and self.peek().value in ("*", "/", "//", "%"):
            op = self.advance().value
            right = self.parse_power()
            left = BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_power(self):
        left = self.parse_unary()
        if self.peek().type == TOK_OP and self.peek().value == "**":
            op = self.advance().value
            right = self.parse_power()  # Right-associative
            return BinaryOp(left, op, right, lineno=left.lineno, col_offset=left.col_offset)
        return left

    def parse_unary(self):
        if self.peek().type == TOK_OP and self.peek().value in ("-", "+", "~", "!"):
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryOp(op, operand, lineno=operand.lineno, col_offset=operand.col_offset)
        if self.match(TOK_KEYWORD, "not"):
            operand = self.parse_unary()
            return UnaryOp("not", operand, lineno=operand.lineno, col_offset=operand.col_offset)
        return self.parse_postfix()

    def parse_postfix(self):
        """
        Parses postfix operations: calls (), subscripts [], and attributes .
        """
        expr = self.parse_primary()

        while True:
            # 1. Function Call: expr(arg1, arg2, ...)
            if self.match(TOK_DELIM, "("):
                args = []
                if not self.match(TOK_DELIM, ")"):
                    while True:
                        args.append(self.parse_expression())
                        if self.match(TOK_DELIM, ","):
                            continue
                        self.expect(TOK_DELIM, ")")
                        break
                # If expr is an Identifier, keep simple string name for backwards compatibility
                call_target = expr.name if isinstance(expr, Identifier) else expr
                expr = Call(call_target, args, lineno=expr.lineno, col_offset=expr.col_offset)
                continue

            # 2. Subscript or Slice: expr[start:end:step]
            if self.match(TOK_DELIM, "["):
                slice_node = self.parse_subscript_slice()
                self.expect(TOK_DELIM, "]")
                expr = Subscript(expr, slice_node, lineno=expr.lineno, col_offset=expr.col_offset)
                continue

            # 3. Attribute Access: expr.name
            if self.match(TOK_DELIM, "."):
                attr_name = self.expect(TOK_IDENT).value
                expr = Attribute(expr, attr_name, lineno=expr.lineno, col_offset=expr.col_offset)
                continue

            break

        return expr

    def parse_subscript_slice(self):
        """
        Parses index or slice expressions inside brackets:
        - obj[i]
        - obj[start:stop]
        - obj[start:stop:step]
        - obj[:stop]
        - obj[start:]
        - obj[::step]
        """
        if self.match(TOK_DELIM, ":"):
            # Begins with colon: [:stop] or [:stop:step] or [:]
            upper = None
            step = None
            if self.peek().value not in (":", "]"):
                upper = self.parse_expression()
            if self.match(TOK_DELIM, ":"):
                if self.peek().value != "]":
                    step = self.parse_expression()
            return Slice(None, upper, step)

        # Starts with an expression
        first = self.parse_expression()
        if self.match(TOK_DELIM, ":"):
            # Slice: [start:stop:step]
            upper = None
            step = None
            if self.peek().value not in (":", "]"):
                upper = self.parse_expression()
            if self.match(TOK_DELIM, ":"):
                if self.peek().value != "]":
                    step = self.parse_expression()
            return Slice(first, upper, step)

        # Single index lookup
        return first

    def parse_primary(self):
        """Parses primary atoms: literals, variables, and grouped expressions."""
        tok = self.peek()

        if tok.type == TOK_NUMBER:
            t = self.advance()
            return Number(t.value, lineno=t.line, col_offset=t.col)

        if tok.type == TOK_STRING:
            t = self.advance()
            return String(t.value, lineno=t.line, col_offset=t.col)

        if tok.type == TOK_KEYWORD and tok.value == "True":
            t = self.advance()
            return Number(1, lineno=t.line, col_offset=t.col)

        if tok.type == TOK_KEYWORD and tok.value == "False":
            t = self.advance()
            return Number(0, lineno=t.line, col_offset=t.col)

        if tok.type == TOK_KEYWORD and tok.value == "None":
            t = self.advance()
            return Number(0, lineno=t.line, col_offset=t.col)

        if tok.type == TOK_IDENT:
            t = self.advance()
            return Identifier(t.value, lineno=t.line, col_offset=t.col)

        # List Literal: [elem1, elem2, ...]
        if self.match(TOK_DELIM, "["):
            elements = []
            if not self.match(TOK_DELIM, "]"):
                while True:
                    elements.append(self.parse_expression())
                    if self.match(TOK_DELIM, ","):
                        continue
                    self.expect(TOK_DELIM, "]")
                    break
            return ListLiteral(elements, lineno=tok.line, col_offset=tok.col)

        # Dict Literal: {k1: v1, k2: v2} or Set Literal
        if self.match(TOK_DELIM, "{"):
            keys = []
            values = []
            if not self.match(TOK_DELIM, "}"):
                while True:
                    k = self.parse_expression()
                    self.expect(TOK_DELIM, ":")
                    v = self.parse_expression()
                    keys.append(k)
                    values.append(v)
                    if self.match(TOK_DELIM, ","):
                        continue
                    self.expect(TOK_DELIM, "}")
                    break
            return DictLiteral(keys, values, lineno=tok.line, col_offset=tok.col)

        # Parenthesized grouping or Tuple: (expr) or (e1, e2)
        if self.match(TOK_DELIM, "("):
            if self.match(TOK_DELIM, ")"):
                return TupleLiteral([], lineno=tok.line, col_offset=tok.col)

            first = self.parse_expression()
            if self.match(TOK_DELIM, ","):
                elements = [first]
                if not self.match(TOK_DELIM, ")"):
                    while True:
                        elements.append(self.parse_expression())
                        if self.match(TOK_DELIM, ","):
                            continue
                        self.expect(TOK_DELIM, ")")
                        break
                return TupleLiteral(elements, lineno=tok.line, col_offset=tok.col)

            self.expect(TOK_DELIM, ")")
            return first

        raise SyntaxError(
            f"Unexpected token {tok.type}('{tok.value}') at L{tok.line}:{tok.col}"
        )
