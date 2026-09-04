#!/usr/bin/env python3
"""
AdiOS C Type System & Struct Layout Engine (compiler/c_types.py)
Implements rich ANSI C99 type taxonomy, struct packing, and memory layout:
- Primitive scalar types (void, char, short, int, long, float, double, unsigned variants)
- Derived types: Pointers (*), Fixed-size Arrays ([]), Function pointers with variadic ABI
- Compound types: Structs (natural RV32 4-byte alignment, padding, offsets), Bitfields, and Unions
- Enums with explicit and automatic value progression
- Type qualifiers (const, volatile, restrict)
- Standard C99 integer promotions and usual arithmetic conversions rank rules
- Pointer arithmetic scale resolution (sizeof pointee)
- Scalar type promotion and cast validity checker
- RISC-V Standard Calling Convention Argument Classifier (a0..a7 vs stack spill slots)
- C99 Type String Formatter and Pretty Printer

Zero external dependencies. Pure RV32IM toolchain component.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

from typing import Dict, List, Tuple, Optional, Any, Set

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
        self.is_const = False
        self.is_volatile = False
        self.is_restrict = False

    def is_integer(self) -> bool:
        return self.name in (
            "char", "unsigned char", "short", "unsigned short",
            "int", "unsigned int", "long", "unsigned long",
            "uint8", "uint16", "uint32", "int8_t", "int16_t", "int32_t",
            "uint8_t", "uint16_t", "uint32_t", "bool", "size_t"
        )

    def is_floating(self) -> bool:
        return self.name in ("float", "double")

    @property
    def conversion_rank(self) -> int:
        """C99 6.3.1.1 Integer conversion rank."""
        ranks = {
            "bool": 10,
            "char": 20, "unsigned char": 20, "int8_t": 20, "uint8_t": 20,
            "short": 30, "unsigned short": 30, "int16_t": 30, "uint16_t": 30,
            "int": 40, "unsigned int": 40, "int32_t": 40, "uint32_t": 40, "size_t": 40,
            "long": 50, "unsigned long": 50,
            "float": 60,
            "double": 70
        }
        return ranks.get(self.name, 0)

    def clone(self) -> 'CType':
        cloned = CType(self.name, self.size, self.alignment, self.is_signed)
        cloned.is_pointer = self.is_pointer
        cloned.is_array = self.is_array
        cloned.is_struct = self.is_struct
        cloned.is_union = self.is_union
        cloned.is_function = self.is_function
        cloned.is_enum = self.is_enum
        cloned.is_const = self.is_const
        cloned.is_volatile = self.is_volatile
        cloned.is_restrict = self.is_restrict
        return cloned

    def with_const(self) -> 'CType':
        c = self.clone()
        c.is_const = True
        return c

    def with_volatile(self) -> 'CType':
        c = self.clone()
        c.is_volatile = True
        return c

    def __repr__(self):
        prefix = ""
        if self.is_const:
            prefix += "const "
        if self.is_volatile:
            prefix += "volatile "
        return prefix + self.name

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
TYPE_BOOL       = CType("bool", 1, 1, is_signed=False)

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

class BitfieldMember:
    """Struct member occupying a fractional bit slice."""
    def __init__(self, name: str, member_type: CType, bit_width: int, bit_offset: int, byte_offset: int):
        self.name = name
        self.member_type = member_type
        self.bit_width = bit_width
        self.bit_offset = bit_offset
        self.byte_offset = byte_offset

class StructMember:
    def __init__(self, name: str, member_type: CType, offset: int):
        self.name = name
        self.member_type = member_type
        self.offset = offset

class StructType(CType):
    """
    C Struct with automatic field alignment padding according to RISC-V ABI.
    """
    def __init__(
        self,
        name: str,
        fields: Optional[List[Tuple[str, CType]]] = None,
        packed: bool = False
    ):
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

    def offset_of(self, name: str) -> int:
        member = self.get_member(name)
        if not member:
            raise KeyError(f"Member '{name}' not in struct")
        return member.offset

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

class EnumType(CType):
    """
    C Enumeration type representing an underlying int with named integer constants.
    """
    def __init__(self, name: str, enumerators: Optional[List[Tuple[str, Optional[int]]]] = None):
        super().__init__(f"enum {name}", 4, 4, is_signed=True)
        self.is_enum = True
        self.values: Dict[str, int] = {}
        next_val = 0

        if enumerators:
            for ename, evalue in enumerators:
                if evalue is not None:
                    next_val = evalue
                self.values[ename] = next_val
                next_val += 1

    def get_value(self, name: str) -> Optional[int]:
        return self.values.get(name)

class FunctionType(CType):
    """
    Function pointer or function signature type.
    """
    def __init__(self, return_type: CType, param_types: List[CType], is_variadic: bool = False):
        param_names = ", ".join(p.name for p in param_types)
        if is_variadic:
            param_names += ", ..." if param_names else "..."
        super().__init__(f"{return_type.name}(*)({param_names})", 4, 4)
        self.return_type = return_type
        self.param_types = param_types
        self.is_variadic = is_variadic
        self.is_function = True

    def classify_abi_arguments(self) -> List[Tuple[str, int]]:
        """
        Calculates RISC-V standard calling convention argument registers (a0-a7)
        and stack spill offsets.
        Returns list of (location_type, index_or_offset).
        """
        locations = []
        gpr_count = 8 # a0 (x10) .. a7 (x17)
        current_gpr = 0
        stack_offset = 0

        for param in self.param_types:
            words = (param.size + 3) // 4
            if current_gpr + words <= gpr_count:
                locations.append(("REG", 10 + current_gpr))
                current_gpr += words
            else:
                locations.append(("STACK", stack_offset))
                stack_offset += words * 4

        return locations

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
            "bool": TYPE_BOOL,
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
    def integer_promotion(ctype: CType) -> CType:
        """
        Applies C99 integer promotions: types smaller than int are promoted to int.
        """
        if ctype.is_integer() and ctype.size < 4:
            return TYPE_INT
        return ctype

    @staticmethod
    def usual_arithmetic_conversions(type1: CType, type2: CType) -> CType:
        """
        Determines the common type of two operands in binary arithmetic according to C99 6.3.1.8.
        """
        # 1. If either operand is double, common is double
        if type1.name == "double" or type2.name == "double":
            return TYPE_DOUBLE
        # 2. If either is float, common is float
        if type1.name == "float" or type2.name == "float":
            return TYPE_FLOAT

        # 3. Apply integer promotions
        t1 = TypeRegistry.integer_promotion(type1)
        t2 = TypeRegistry.integer_promotion(type2)

        # 4. If same type, return it
        if t1.name == t2.name:
            return t1

        # 5. If both signed or both unsigned, highest conversion rank wins
        if t1.is_signed == t2.is_signed:
            return t1 if t1.conversion_rank >= t2.conversion_rank else t2

        # 6. Unsigned operand has rank >= signed operand -> common is unsigned
        if not t1.is_signed and t1.conversion_rank >= t2.conversion_rank:
            return t1
        if not t2.is_signed and t2.conversion_rank >= t1.conversion_rank:
            return t2

        # 7. Signed type can represent all values of unsigned type
        if t1.is_signed and t1.size > t2.size:
            return t1
        if t2.is_signed and t2.size > t1.size:
            return t2

        # Default fallback to unsigned variant of signed type
        return TYPE_UINT

    @staticmethod
    def pointer_step(ctype: CType) -> int:
        """Returns byte step size for pointer arithmetic (e.g. ptr + 1)."""
        if isinstance(ctype, PointerType):
            return max(1, ctype.target_type.size)
        elif isinstance(ctype, ArrayType):
            return max(1, ctype.element_type.size)
        return 1

    @staticmethod
    def can_cast(src: CType, dst: CType) -> bool:
        """Determines if a cast between two C types is legal in C99."""
        if src == dst:
            return True
        # Scalar to scalar (integer / float)
        if (src.is_integer() or src.is_floating()) and (dst.is_integer() or dst.is_floating()):
            return True
        # Pointer to pointer, pointer to int, int to pointer
        if src.is_pointer and (dst.is_pointer or dst.is_integer()):
            return True
        if src.is_integer and dst.is_pointer:
            return True
        return False

if __name__ == "__main__":
    reg = TypeRegistry()
    # Test struct alignment
    fields = [("a", TYPE_CHAR), ("b", TYPE_INT), ("c", TYPE_SHORT)]
    st = StructType("Header", fields)
    assert st.members["a"].offset == 0
    assert st.members["b"].offset == 4  # 4-byte aligned
    assert st.members["c"].offset == 8
    assert st.size == 12                # Padded to multiple of 4
    assert st.offset_of("c") == 8

    # Test arithmetic conversions
    common = TypeRegistry.usual_arithmetic_conversions(TYPE_SHORT, TYPE_UINT)
    assert common.name == "unsigned int"

    # Test Enum
    e = EnumType("Status", [("INIT", 0), ("ACTIVE", None), ("ERROR", 100)])
    assert e.get_value("INIT") == 0
    assert e.get_value("ACTIVE") == 1
    assert e.get_value("ERROR") == 100

    # Test ABI classifier
    fn_type = FunctionType(TYPE_INT, [TYPE_INT, TYPE_INT, TYPE_INT])
    arg_locs = fn_type.classify_abi_arguments()
    assert len(arg_locs) == 3
    assert arg_locs[0] == ("REG", 10)  # a0 (x10)
    assert arg_locs[1] == ("REG", 11)  # a1 (x11)
    assert arg_locs[2] == ("REG", 12)  # a2 (x12)

    print("C99 type system, struct layout, conversions, enums, and ABI argument classification verified.")
