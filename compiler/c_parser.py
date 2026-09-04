#!/usr/bin/env python3
"""
AdiOS C99 / AdiC Toolchain: AST & Recursive-Descent Parser (c_parser.py)
Parses C token streams into typed Abstract Syntax Trees (ASTs).
Supports variables, pointers, arrays, structs, functions, loops, and expressions.
Zero external dependencies.
"""

from typing import List, Optional, Dict
from compiler.c_lexer import TokenType, Token, CLexer

class CType:
    """Represents a C type (primitive, pointer, array, struct, or function)."""
    def __init__(self, base: str, pointer_depth: int = 0, array_size: Optional[int] = None, struct_name: Optional[str] = None):
        self.base = base
        self.pointer_depth = pointer_depth
        self.array_size = array_size
        self.struct_name = struct_name

    def size(self) -> int:
        if self.pointer_depth > 0:
            return 4  # 32-bit RV32 pointers
        if self.base in ("char", "void"):
            return 1
        if self.base == "short":
            return 2
        if self.base in ("int", "long"):
            return 4
        return 4

    def is_pointer(self) -> bool:
        return self.pointer_depth > 0 or self.array_size is not None

    def __repr__(self):
        s = self.base
        if self.struct_name:
            s += f" {self.struct_name}"
        s += "*" * self.pointer_depth
        if self.array_size is not None:
            s += f"[{self.array_size}]"
        return s

# --- AST Nodes ---

class ASTNode:
    pass

class Expr(ASTNode):
    pass

class LiteralExpr(Expr):
    def __init__(self, value: any, val_type: str = "int"):
        self.value = value
        self.val_type = val_type

class VariableExpr(Expr):
    def __init__(self, name: str):
        self.name = name

class BinaryExpr(Expr):
    def __init__(self, op: str, left: Expr, right: Expr):
        self.op = op
        self.left = left
        self.right = right

class UnaryExpr(Expr):
    def __init__(self, op: str, operand: Expr, prefix: bool = True):
        self.op = op
        self.operand = operand
        self.prefix = prefix

class AssignExpr(Expr):
    def __init__(self, target: Expr, value: Expr, op: str = "="):
        self.target = target
        self.value = value
        self.op = op

class CallExpr(Expr):
    def __init__(self, callee: Expr, args: List[Expr]):
        self.callee = callee
        self.args = args

class MemberExpr(Expr):
    def __init__(self, obj: Expr, member: str, is_arrow: bool = False):
        self.obj = obj
        self.member = member
        self.is_arrow = is_arrow

class IndexExpr(Expr):
    def __init__(self, array: Expr, index: Expr):
        self.array = array
        self.index = index

class Stmt(ASTNode):
    pass

class BlockStmt(Stmt):
    def __init__(self, stmts: List[Stmt]):
        self.stmts = stmts

class ExprStmt(Stmt):
    def __init__(self, expr: Expr):
        self.expr = expr

class VarDecl(Stmt):
    def __init__(self, var_type: CType, name: str, init_expr: Optional[Expr] = None):
        self.var_type = var_type
        self.name = name
        self.init_expr = init_expr

class IfStmt(Stmt):
    def __init__(self, cond: Expr, then_stmt: Stmt, else_stmt: Optional[Stmt] = None):
        self.cond = cond
        self.then_stmt = then_stmt
        self.else_stmt = else_stmt

class WhileStmt(Stmt):
    def __init__(self, cond: Expr, body: Stmt):
        self.cond = cond
        self.body = body

class ForStmt(Stmt):
    def __init__(self, init: Optional[Stmt], cond: Optional[Expr], step: Optional[Expr], body: Stmt):
        self.init = init
        self.cond = cond
        self.step = step
        self.body = body

class ReturnStmt(Stmt):
    def __init__(self, expr: Optional[Expr] = None):
        self.expr = expr

class FunctionDecl(ASTNode):
    def __init__(self, ret_type: CType, name: str, params: List[VarDecl], body: Optional[BlockStmt] = None):
        self.ret_type = ret_type
        self.name = name
        self.params = params
        self.body = body

class StructDecl(ASTNode):
    def __init__(self, name: str, members: List[VarDecl]):
        self.name = name
        self.members = members

class TranslationUnit(ASTNode):
    def __init__(self, decls: List[ASTNode]):
        self.decls = decls

class CParser:
    """
    Recursive-descent C parser with operator precedence.
    """
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> TranslationUnit:
        decls = []
        while not self.is_at_end():
            decl = self.parse_declaration()
            if decl:
                decls.append(decl)
        return TranslationUnit(decls)

    def parse_declaration(self) -> Optional[ASTNode]:
        if self.match(TokenType.KW_STRUCT) and self.peek(1).type == TokenType.LBRACE:
            # struct definition
            name = self.advance().value
            self.consume(TokenType.LBRACE, "Expected '{'")
            members = []
            while not self.check(TokenType.RBRACE) and not self.is_at_end():
                members.append(self.parse_var_decl_stmt())
            self.consume(TokenType.RBRACE, "Expected '}'")
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return StructDecl(name, members)

        # Type specifier
        var_type = self.parse_type()
        if not var_type:
            # Skip unrecognized
            self.advance()
            return None

        name = self.consume(TokenType.IDENTIFIER, "Expected identifier").value

        # Check if function declaration
        if self.check(TokenType.LPAREN):
            self.consume(TokenType.LPAREN, "Expected '('")
            params = []
            if not self.check(TokenType.RPAREN):
                while True:
                    if self.match(TokenType.KW_VOID) and self.check(TokenType.RPAREN):
                        break
                    p_type = self.parse_type()
                    p_name = self.consume(TokenType.IDENTIFIER, "Expected parameter name").value
                    if self.match(TokenType.LBRACKET):
                        p_type.pointer_depth += 1
                        if self.match(TokenType.INT_LITERAL): pass
                        self.consume(TokenType.RBRACKET, "Expected ']'")
                    params.append(VarDecl(p_type, p_name))
                    if not self.match(TokenType.COMMA):
                        break
            self.consume(TokenType.RPAREN, "Expected ')'")

            if self.check(TokenType.LBRACE):
                body = self.parse_block()
                return FunctionDecl(var_type, name, params, body)
            else:
                self.consume(TokenType.SEMICOLON, "Expected ';'")
                return FunctionDecl(var_type, name, params, None)
        else:
            # Global variable declaration
            init_expr = None
            if self.match(TokenType.ASSIGN):
                init_expr = self.parse_expression()
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return VarDecl(var_type, name, init_expr)

    def parse_type(self) -> Optional[CType]:
        base = "int"
        struct_name = None

        if self.match(TokenType.KW_VOID): base = "void"
        elif self.match(TokenType.KW_CHAR): base = "char"
        elif self.match(TokenType.KW_SHORT): base = "short"
        elif self.match(TokenType.KW_INT): base = "int"
        elif self.match(TokenType.KW_LONG): base = "long"
        elif self.match(TokenType.KW_STRUCT):
            base = "struct"
            struct_name = self.consume(TokenType.IDENTIFIER, "Expected struct name").value
        else:
            return None

        ptr_depth = 0
        while self.match(TokenType.STAR):
            ptr_depth += 1

        return CType(base, pointer_depth=ptr_depth, struct_name=struct_name)

    def parse_block(self) -> BlockStmt:
        self.consume(TokenType.LBRACE, "Expected '{'")
        stmts = []
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            stmts.append(self.parse_statement())
        self.consume(TokenType.RBRACE, "Expected '}'")
        return BlockStmt(stmts)

    def parse_statement(self) -> Stmt:
        if self.check(TokenType.LBRACE):
            return self.parse_block()
        if self.match(TokenType.KW_IF):
            self.consume(TokenType.LPAREN, "Expected '('")
            cond = self.parse_expression()
            self.consume(TokenType.RPAREN, "Expected ')'")
            then_s = self.parse_statement()
            else_s = self.parse_statement() if self.match(TokenType.KW_ELSE) else None
            return IfStmt(cond, then_s, else_s)
        if self.match(TokenType.KW_WHILE):
            self.consume(TokenType.LPAREN, "Expected '('")
            cond = self.parse_expression()
            self.consume(TokenType.RPAREN, "Expected ')'")
            body = self.parse_statement()
            return WhileStmt(cond, body)
        if self.match(TokenType.KW_FOR):
            self.consume(TokenType.LPAREN, "Expected '('")
            init = self.parse_statement() if not self.match(TokenType.SEMICOLON) else None
            cond = self.parse_expression() if not self.check(TokenType.SEMICOLON) else None
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            step = self.parse_expression() if not self.check(TokenType.RPAREN) else None
            self.consume(TokenType.RPAREN, "Expected ')'")
            body = self.parse_statement()
            return ForStmt(init, cond, step, body)
        if self.match(TokenType.KW_RETURN):
            expr = self.parse_expression() if not self.check(TokenType.SEMICOLON) else None
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return ReturnStmt(expr)

        # Check if local variable declaration
        t = self.parse_type()
        if t:
            name = self.consume(TokenType.IDENTIFIER, "Expected variable name").value
            init_expr = self.parse_expression() if self.match(TokenType.ASSIGN) else None
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return VarDecl(t, name, init_expr)

        # Expression statement
        expr = self.parse_expression()
        self.consume(TokenType.SEMICOLON, "Expected ';'")
        return ExprStmt(expr)

    def parse_var_decl_stmt(self) -> VarDecl:
        t = self.parse_type()
        name = self.consume(TokenType.IDENTIFIER, "Expected variable name").value
        init = self.parse_expression() if self.match(TokenType.ASSIGN) else None
        self.consume(TokenType.SEMICOLON, "Expected ';'")
        return VarDecl(t, name, init)

    # --- Expression Parser (Precedence Climbing) ---

    def parse_expression(self) -> Expr:
        return self.parse_assignment()

    def parse_assignment(self) -> Expr:
        expr = self.parse_logical_or()
        if self.match(TokenType.ASSIGN):
            val = self.parse_assignment()
            return AssignExpr(expr, val, "=")
        if self.match(TokenType.PLUS_ASSIGN):
            val = self.parse_assignment()
            return AssignExpr(expr, val, "+=")
        if self.match(TokenType.MINUS_ASSIGN):
            val = self.parse_assignment()
            return AssignExpr(expr, val, "-=")
        if self.match(TokenType.MUL_ASSIGN):
            val = self.parse_assignment()
            return AssignExpr(expr, val, "*=")
        if self.match(TokenType.DIV_ASSIGN):
            val = self.parse_assignment()
            return AssignExpr(expr, val, "/=")
        return expr

    def parse_logical_or(self) -> Expr:
        expr = self.parse_logical_and()
        while self.match(TokenType.LOG_OR):
            expr = BinaryExpr("||", expr, self.parse_logical_and())
        return expr

    def parse_logical_and(self) -> Expr:
        expr = self.parse_equality()
        while self.match(TokenType.LOG_AND):
            expr = BinaryExpr("&&", expr, self.parse_equality())
        return expr

    def parse_equality(self) -> Expr:
        expr = self.parse_relational()
        while True:
            if self.match(TokenType.EQ):
                expr = BinaryExpr("==", expr, self.parse_relational())
            elif self.match(TokenType.NEQ):
                expr = BinaryExpr("!=", expr, self.parse_relational())
            else:
                break
        return expr

    def parse_relational(self) -> Expr:
        expr = self.parse_additive()
        while True:
            if self.match(TokenType.LT): expr = BinaryExpr("<", expr, self.parse_additive())
            elif self.match(TokenType.GT): expr = BinaryExpr(">", expr, self.parse_additive())
            elif self.match(TokenType.LE): expr = BinaryExpr("<=", expr, self.parse_additive())
            elif self.match(TokenType.GE): expr = BinaryExpr(">=", expr, self.parse_additive())
            else: break
        return expr

    def parse_additive(self) -> Expr:
        expr = self.parse_multiplicative()
        while True:
            if self.match(TokenType.PLUS): expr = BinaryExpr("+", expr, self.parse_multiplicative())
            elif self.match(TokenType.MINUS): expr = BinaryExpr("-", expr, self.parse_multiplicative())
            else: break
        return expr

    def parse_multiplicative(self) -> Expr:
        expr = self.parse_unary()
        while True:
            if self.match(TokenType.STAR): expr = BinaryExpr("*", expr, self.parse_unary())
            elif self.match(TokenType.SLASH): expr = BinaryExpr("/", expr, self.parse_unary())
            elif self.match(TokenType.PERCENT): expr = BinaryExpr("%", expr, self.parse_unary())
            else: break
        return expr

    def parse_unary(self) -> Expr:
        if self.match(TokenType.MINUS): return UnaryExpr("-", self.parse_unary())
        if self.match(TokenType.BANG): return UnaryExpr("!", self.parse_unary())
        if self.match(TokenType.TILDE): return UnaryExpr("~", self.parse_unary())
        if self.match(TokenType.STAR): return UnaryExpr("*", self.parse_unary())  # Dereference
        if self.match(TokenType.AMP): return UnaryExpr("&", self.parse_unary())  # Address-of
        if self.match(TokenType.INC): return UnaryExpr("++", self.parse_unary(), prefix=True)
        if self.match(TokenType.DEC): return UnaryExpr("--", self.parse_unary(), prefix=True)
        return self.parse_postfix()

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.match(TokenType.LPAREN):
                args = []
                if not self.check(TokenType.RPAREN):
                    while True:
                        args.append(self.parse_expression())
                        if not self.match(TokenType.COMMA):
                            break
                self.consume(TokenType.RPAREN, "Expected ')'")
                expr = CallExpr(expr, args)
            elif self.match(TokenType.DOT):
                member = self.consume(TokenType.IDENTIFIER, "Expected member name").value
                expr = MemberExpr(expr, member, is_arrow=False)
            elif self.match(TokenType.ARROW):
                member = self.consume(TokenType.IDENTIFIER, "Expected member name").value
                expr = MemberExpr(expr, member, is_arrow=True)
            elif self.match(TokenType.LBRACKET):
                idx = self.parse_expression()
                self.consume(TokenType.RBRACKET, "Expected ']'")
                expr = IndexExpr(expr, idx)
            elif self.match(TokenType.INC):
                expr = UnaryExpr("++", expr, prefix=False)
            elif self.match(TokenType.DEC):
                expr = UnaryExpr("--", expr, prefix=False)
            else:
                break
        return expr

    def parse_primary(self) -> Expr:
        if self.match(TokenType.INT_LITERAL):
            return LiteralExpr(self.previous().value, "int")
        if self.match(TokenType.HEX_LITERAL):
            return LiteralExpr(self.previous().value, "int")
        if self.match(TokenType.STRING_LITERAL):
            return LiteralExpr(self.previous().value, "str")
        if self.match(TokenType.CHAR_LITERAL):
            return LiteralExpr(self.previous().value, "char")
        if self.match(TokenType.IDENTIFIER):
            return VariableExpr(self.previous().value)
        if self.match(TokenType.LPAREN):
            expr = self.parse_expression()
            self.consume(TokenType.RPAREN, "Expected ')'")
            return expr

        tok = self.peek()
        raise SyntaxError(f"Unexpected token {tok.type.name} ('{tok.value}') at line {tok.line}:{tok.col}")

    # Helper routines
    def match(self, typ: TokenType) -> bool:
        if self.check(typ):
            self.advance()
            return True
        return False

    def check(self, typ: TokenType) -> bool:
        return self.peek().type == typ if not self.is_at_end() else False

    def consume(self, typ: TokenType, err_msg: str) -> Token:
        if self.check(typ):
            return self.advance()
        tok = self.peek()
        raise SyntaxError(f"{err_msg} at line {tok.line}:{tok.col}, got {tok.type.name}")

    def advance(self) -> Token:
        if not self.is_at_end():
            self.pos += 1
        return self.previous()

    def previous(self) -> Token:
        return self.tokens[self.pos - 1]

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

if __name__ == "__main__":
    src = """
    int square(int x) {
        return x * x;
    }
    int main() {
        int val = 5;
        int res = square(val);
        return res;
    }
    """
    lexer = CLexer(src)
    parser = CParser(lexer.tokenize())
    ast = parser.parse()
    print(f"Parsed {len(ast.decls)} top-level declarations.")
    assert isinstance(ast.decls[0], FunctionDecl)
    assert ast.decls[0].name == "square"
    print("C Parser verified.")
