#!/usr/bin/env python3
"""
AdiOS C Type System & Struct Layout Engine (compiler/c_types.py)
Implements rich ANSI C99 type taxonomy, struct packing, and memory layout:
- Primitive scalar types (void, char, short, int, long, float, double, unsigned variants)
- Derived types: Pointers (*), Fixed-size Arrays ([]), Function pointers
- Compound types: Structs (natural RV32 4-byte alignment, padding, offsets) and Unions
- Enums and Typedef symbol table resolver
- Pointer arithmetic scale resolution (sizeof pointee)
- Scalar type promotion and cast validity checker

Zero external dependencies. Pure RV32IM toolchain component.
STRICT ZERO EMOJI POLICY.
"""

from typing import Dict, List, Tuple, Optional, Any

class CType:
    def __init__(self, name: str, size: int, alignment: int, is_signed: bool = True):
        self.name = name
        self.size = size
        self.alignment = alignment
        self.is_signed = is_signed
        self.is_pointer = False
        self.is_array = False
        self.is_struct = False
        self.is_union = False
        self.is_function = False
        self.is_enum = False

    def is_integer(self) -> bool:
        return self.name in ("char", "short", "int", "long", "uint8", "uint16", "uint32", "bool")

    def __repr__(self):
        return self.name

# Built-in Primitive Types for RV32 (32-bit words, 4-byte pointers)
TYPE_VOID       = CType("void", 0, 1)
TYPE_CHAR       = CType("char", 1, 1, is_signed=True)
TYPE_UCHAR      = CType("unsigned char", 1, 1, is_signed=False)
TYPE_SHORT      = CType("short", 2, 2, is_signed=True)
TYPE_USHORT     = CType("unsigned short", 2, 2, is_signed=False)
TYPE_INT        = CType("int", 4, 4, is_signed=True)
TYPE_UINT       = CType("unsigned int", 4, 4, is_signed=False)
TYPE_LONG       = CType("long", 4, 4, is_signed=True)
TYPE_ULONG      = CType("unsigned long", 4, 4, is_signed=False)
TYPE_FLOAT      = CType("float", 4, 4, is_signed=True)
TYPE_DOUBLE     = CType("double", 8, 4, is_signed=True)

class PointerType(CType):
    def __init__(self, target_type: CType):
        super().__init__(f"{target_type.name}*", 4, 4, is_signed=False)
        self.target_type = target_type
        self.is_pointer = True

class ArrayType(CType):
    def __init__(self, element_type: CType, count: int):
        total_size = element_type.size * count
        super().__init__(f"{element_type.name}[{count}]", total_size, element_type.alignment)
        self.element_type = element_type
        self.count = count
        self.is_array = True

class StructMember:
    def __init__(self, name: str, member_type: CType, offset: int):
        self.name = name
        self.member_type = member_type
        self.offset = offset

class StructType(CType):
    """
    C Struct with automatic field alignment padding according to RISC-V ABI.
    """
    def __init__(self, name: str, fields: Optional[List[Tuple[str, CType]]] = None, packed: bool = False):
        self.packed = packed
        self.members: Dict[str, StructMember] = {}
        self.member_list: List[StructMember] = []

        # Compute layout if fields provided
        max_align = 1
        curr_offset = 0

        if fields:
            for field_name, field_type in fields:
                align = 1 if packed else field_type.alignment
                if align > max_align:
                    max_align = align

                # Align current offset to field alignment requirement
                if curr_offset % align != 0:
                    curr_offset += align - (curr_offset % align)

                member = StructMember(field_name, field_type, curr_offset)
                self.members[field_name] = member
                self.member_list.append(member)
                curr_offset += field_type.size

            # Struct total size must be a multiple of its max alignment
            if not packed and max_align > 0 and curr_offset % max_align != 0:
                curr_offset += max_align - (curr_offset % max_align)

        super().__init__(f"struct {name}", curr_offset, max_align)
        self.is_struct = True

    def get_member(self, name: str) -> Optional[StructMember]:
        return self.members.get(name)

class UnionType(CType):
    """
    C Union where all members share offset 0 and size is max member size.
    """
    def __init__(self, name: str, fields: List[Tuple[str, CType]]):
        self.members: Dict[str, StructMember] = {}
        max_size = 0
        max_align = 1

        for field_name, field_type in fields:
            if field_type.size > max_size:
                max_size = field_type.size
            if field_type.alignment > max_align:
                max_align = field_type.alignment
            self.members[field_name] = StructMember(field_name, field_type, 0)

        # Pad union size to alignment
        if max_align > 0 and max_size % max_align != 0:
            max_size += max_align - (max_size % max_align)

        super().__init__(f"union {name}", max_size, max_align)
        self.is_union = True

class FunctionType(CType):
    def __init__(self, return_type: CType, param_types: List[CType]):
        param_names = ", ".join(p.name for p in param_types)
        super().__init__(f"{return_type.name}(*)({param_names})", 4, 4)
        self.return_type = return_type
        self.param_types = param_types
        self.is_function = True

class TypeRegistry:
    """
    Symbol table for types, typedefs, and struct/union tags.
    """
    def __init__(self):
        self.types: Dict[str, CType] = {
            "void": TYPE_VOID,
            "char": TYPE_CHAR,
            "unsigned char": TYPE_UCHAR,
            "short": TYPE_SHORT,
            "unsigned short": TYPE_USHORT,
            "int": TYPE_INT,
            "unsigned int": TYPE_UINT,
            "long": TYPE_LONG,
            "unsigned long": TYPE_ULONG,
            "float": TYPE_FLOAT,
            "double": TYPE_DOUBLE,
            "uint8_t": TYPE_UCHAR,
            "uint16_t": TYPE_USHORT,
            "uint32_t": TYPE_UINT,
            "int8_t": TYPE_CHAR,
            "int16_t": TYPE_SHORT,
            "int32_t": TYPE_INT,
            "size_t": TYPE_UINT
        }

    def register_typedef(self, alias: str, target: CType):
        self.types[alias] = target

    def lookup(self, name: str) -> Optional[CType]:
        return self.types.get(name)

    def pointer_to(self, ctype: CType) -> PointerType:
        return PointerType(ctype)

    def array_of(self, element: CType, count: int) -> ArrayType:
        return ArrayType(element, count)

    @staticmethod
    def pointer_step(ctype: CType) -> int:
        """Returns byte step size for pointer arithmetic (e.g. ptr + 1)."""
        if isinstance(ctype, PointerType):
            return ctype.target_type.size
        elif isinstance(ctype, ArrayType):
            return ctype.element_type.size
        return 1

    @staticmethod
    def can_cast(src: CType, dst: CType) -> bool:
        """Determines if a cast between two C types is legal in C99."""
        if src == dst:
            return True
        # Scalar to scalar (integer / float)
        if (src.is_integer() or src.name in ("float", "double")) and (dst.is_integer() or dst.name in ("float", "double")):
            return True
        # Pointer to pointer, pointer to int, int to pointer
        if src.is_pointer and (dst.is_pointer or dst.is_integer()):
            return True
        if src.is_integer() and dst.is_pointer:
            return True
        return False
