#!/usr/bin/env python3
"""
Luraph v14.5.2 Bytecode Decompiler

Extracts bytecode from the decompressed VM and decompiles it to readable Lua.
"""

import re
import struct
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field


def base85_decode(s: str) -> bytes:
    """Decode Luraph base85 (z = !!!!! shorthand)."""
    s = s.replace('z', '!!!!!')
    result = bytearray()
    i = 0
    while i + 5 <= len(s):
        chunk = s[i:i+5]
        try:
            # Luraph formula: (c5-33) + (c4-33)*85 + (c3-33)*7225 + (c2-33)*614125 + (c1-33)*52200625
            vals = [ord(c) - 33 for c in chunk]
            val = vals[4] + vals[3]*85 + vals[2]*7225 + vals[1]*614125 + vals[0]*52200625
            result.extend(struct.pack('>I', val))
        except:
            pass
        i += 5
    return bytes(result)


@dataclass
class Instruction:
    pc: int = 0
    opcode: int = 0
    a: int = 0  # operand A (W[5])
    b: int = 0  # operand B (W[4])
    c: int = 0  # operand C (W[9])
    d: int = 0  # operand D (W[7])
    e: int = 0  # operand E (W[8])


@dataclass
class FunctionProto:
    num_params: int = 0
    is_vararg: bool = False
    max_stack: int = 0
    num_upvalues: int = 0
    num_instructions: int = 0
    opcodes: List[int] = field(default_factory=list)      # W[10]
    operand_a: List[int] = field(default_factory=list)    # W[5]
    operand_b: List[int] = field(default_factory=list)    # W[4]
    operand_c: List[int] = field(default_factory=list)    # W[9]
    operand_d: List[int] = field(default_factory=list)    # W[7]
    operand_e: List[int] = field(default_factory=list)    # W[8]
    strings: List[str] = field(default_factory=list)      # W[11]
    constants: List[Any] = field(default_factory=list)    # W[1]
    protos: List['FunctionProto'] = field(default_factory=list)
    upvalue_info: List[Tuple[int, int]] = field(default_factory=list)
    source: str = ""


class BytecodeReader:
    """Read values from bytecode buffer."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def read_byte(self) -> int:
        if self.pos >= len(self.data):
            return 0
        val = self.data[self.pos]
        self.pos += 1
        return val

    def read_uint16(self) -> int:
        return self.read_byte() | (self.read_byte() << 8)

    def read_uint32(self) -> int:
        return (self.read_byte() |
                (self.read_byte() << 8) |
                (self.read_byte() << 16) |
                (self.read_byte() << 24))

    def read_int32(self) -> int:
        val = self.read_uint32()
        if val >= 0x80000000:
            val -= 0x100000000
        return val

    def read_double(self) -> float:
        data = self.data[self.pos:self.pos+8]
        self.pos += 8
        if len(data) < 8:
            return 0.0
        return struct.unpack('<d', data)[0]

    def read_bytes(self, n: int) -> bytes:
        data = self.data[self.pos:self.pos+n]
        self.pos += n
        return data

    def read_string(self, length: int = None) -> str:
        if length is None:
            length = self.read_varint()
        if length == 0:
            return ""
        data = self.data[self.pos:self.pos+length]
        self.pos += length
        return data.decode('utf-8', errors='replace')

    def read_varint(self) -> int:
        """Read variable-length integer (LEB128)."""
        result = 0
        shift = 0
        while True:
            byte = self.read_byte()
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result

    def peek_bytes(self, n: int) -> bytes:
        return self.data[self.pos:self.pos+n]


# Opcode definitions for Luraph VM (from E8 interpreter analysis)
# These are shuffled from standard Lua opcodes
OPCODES = {
    # Analyzed from E8 interpreter opcode dispatch
    0xBD: ("RETURN", "Returns values from function"),
    0xBC: ("SETTABLE", "X[B][X[D]] = X[A]"),
    0xBB: ("SUBK", "X[D] = C - E (constants)"),
    0xBA: ("CALL_NORET", "Call without return"),
    0xB9: ("VARARG", "Load vararg values"),
    0xB8: ("GE_K", "X[D] = X[B] >= C"),
    0xB7: ("MUL", "X[B] = X[A] * X[D]"),
    0xB6: ("DIV", "X[D] = X[A] / X[B]"),
    0xB5: ("GT", "X[D] = X[B] > X[A]"),
    0xB4: ("FORLOOP", "Numeric for loop"),
    0xB3: ("GETUPVAL_TAB", "Get upvalue table"),
    0xB2: ("LOADSELF", "Load self"),
    0xB1: ("TFORLOOP", "Generic for loop iterator"),
    0xB0: ("LT_K_JMP", "Less than with jump"),
    0xAF: ("FORPREP", "For loop preparation"),
    0xAE: ("JMP_IF", "Conditional jump"),
    0xAD: ("CONCAT", "X[D] = X[B] .. X[A]"),
    0xAC: ("FOR_INIT", "For loop initialization"),
    0xAB: ("CALL0", "Call with 0 args"),
    0xAA: ("CLOSURE", "Create closure"),
    0xA9: ("GT_K", "X[D] = E > X[A]"),
    0xC0: ("LOADK", "Load constant/string"),
    0xBE: ("LOADNIL", "X[B] = nil"),
    0xBF: ("JMP_EQ", "Jump if equal"),

    # Additional opcodes from analysis
    0x00: ("NOP", "No operation"),
    0x01: ("MOVE", "X[D] = X[A]"),
    0x02: ("LOADBOOL", "Load boolean"),
    0x03: ("GETGLOBAL", "Get global"),
    0x04: ("SETGLOBAL", "Set global"),
    0x05: ("GETUPVAL", "Get upvalue"),
    0x06: ("SETUPVAL", "Set upvalue"),
    0x07: ("GETTABLE", "Get table value"),
    0x08: ("NEWTABLE", "Create table"),
    0x09: ("SELF", "Self method call"),
    0x0A: ("ADD", "Addition"),
    0x0B: ("SUB", "Subtraction"),
    0x0C: ("POW", "Power"),
    0x0D: ("UNM", "Unary minus"),
    0x0E: ("NOT", "Logical not"),
    0x0F: ("LEN", "Length operator"),
    0x10: ("EQ", "Equal comparison"),
    0x11: ("LT", "Less than"),
    0x12: ("LE", "Less or equal"),
    0x13: ("TEST", "Test boolean"),
    0x14: ("TESTSET", "Test and set"),
    0x15: ("CALL", "Function call"),
    0x16: ("TAILCALL", "Tail call"),
    0x17: ("SETLIST", "Set list"),
    0x18: ("CLOSE", "Close upvalues"),
}


class LuraphDecompiler:
    def __init__(self, vm_code: str):
        self.vm_code = vm_code
        self.bytecode_strings: List[bytes] = []
        self.main_bytecode: bytes = b''
        self.functions: List[FunctionProto] = []
        self.output_lines: List[str] = []
        self.indent = 0

    def extract_bytecode(self):
        """Extract all bytecode strings from the VM."""
        # Find all [=[...]=] strings (main bytecode format)
        pos = 0
        while True:
            start_marker = self.vm_code.find('[=[', pos)
            if start_marker == -1:
                break
            start = start_marker + 3
            end_marker = self.vm_code.find(']=]', start)
            if end_marker == -1:
                break

            content = self.vm_code[start:end_marker]
            # Remove newlines and whitespace
            content = content.replace('\n', '').replace('\r', '').replace(' ', '')

            if len(content) > 100:
                decoded = base85_decode(content)
                if len(decoded) > 50:
                    self.bytecode_strings.append(decoded)
                    if len(decoded) > len(self.main_bytecode):
                        self.main_bytecode = decoded

            pos = end_marker + 3

        # Also try [[...]] format
        pos = 0
        while True:
            start_marker = self.vm_code.find('[[', pos)
            if start_marker == -1:
                break
            # Skip if it's actually [=[
            if start_marker > 0 and self.vm_code[start_marker-1:start_marker+2] == '[=[':
                pos = start_marker + 2
                continue
            start = start_marker + 2
            end_marker = self.vm_code.find(']]', start)
            if end_marker == -1:
                break

            content = self.vm_code[start:end_marker]
            content = content.replace('\n', '').replace('\r', '').replace(' ', '')

            if len(content) > 100 and '=' not in content[:10]:
                decoded = base85_decode(content)
                if len(decoded) > 50:
                    self.bytecode_strings.append(decoded)
                    if len(decoded) > len(self.main_bytecode):
                        self.main_bytecode = decoded

            pos = end_marker + 2

        print(f"Extracted {len(self.bytecode_strings)} bytecode segments")
        print(f"Main bytecode size: {len(self.main_bytecode)} bytes")
        print(f"Total bytecode size: {sum(len(b) for b in self.bytecode_strings)} bytes")

    def analyze_bytecode_header(self):
        """Analyze the main bytecode header structure."""
        if not self.main_bytecode:
            print("No main bytecode found!")
            return

        reader = BytecodeReader(self.main_bytecode)

        print("\n=== Bytecode Header Analysis ===")

        # Read first few bytes to understand structure
        print(f"First 64 bytes (hex):")
        hex_dump = ' '.join(f'{b:02X}' for b in self.main_bytecode[:64])
        for i in range(0, len(hex_dump), 48):
            print(f"  {hex_dump[i:i+48]}")

        # Try to identify structure
        print(f"\nFirst 16 values as uint8:")
        for i in range(min(16, len(self.main_bytecode))):
            print(f"  [{i}] = {self.main_bytecode[i]} (0x{self.main_bytecode[i]:02X})")

        # Try varint reading
        reader.pos = 0
        print(f"\nTrying varint reads:")
        for i in range(8):
            pos_before = reader.pos
            val = reader.read_varint()
            print(f"  varint[{i}] at pos {pos_before}: {val} (0x{val:X})")
            if reader.pos > 50:
                break

    def analyze_instruction_patterns(self):
        """Look for patterns that indicate instruction boundaries."""
        if not self.main_bytecode:
            return

        print("\n=== Instruction Pattern Analysis ===")

        # Count byte frequencies
        freq = {}
        for b in self.main_bytecode[:2000]:
            freq[b] = freq.get(b, 0) + 1

        sorted_freq = sorted(freq.items(), key=lambda x: -x[1])[:20]
        print(f"Most common bytes in first 2000:")
        for byte, count in sorted_freq:
            print(f"  0x{byte:02X}: {count} times")

        # Look for known opcode patterns
        known_ops = [0xBD, 0xBC, 0xBB, 0xBA, 0xB9, 0xB8, 0xB7, 0xB6, 0xB5,
                     0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF, 0xC0, 0xBE, 0xBF]

        print(f"\nKnown opcode occurrences in bytecode:")
        for op in known_ops:
            count = self.main_bytecode.count(bytes([op]))
            if count > 0:
                name = OPCODES.get(op, ("UNKNOWN",))[0]
                print(f"  0x{op:02X} ({name}): {count} times")

    def try_parse_function(self, reader: BytecodeReader) -> Optional[FunctionProto]:
        """Try to parse a function prototype from bytecode."""
        proto = FunctionProto()

        try:
            # Try different header formats
            # Format 1: Standard Lua-like
            proto.source = ""

            # Read function metadata
            first_byte = reader.read_byte()

            # Could be: num_params, flags, or version marker
            if first_byte < 32:  # Likely num_params
                proto.num_params = first_byte
                proto.is_vararg = reader.read_byte() != 0
                proto.max_stack = reader.read_byte()
                proto.num_upvalues = reader.read_byte()

            # Read instruction count
            num_instr = reader.read_varint()
            if num_instr > 100000:  # Sanity check
                return None

            proto.num_instructions = num_instr
            print(f"  Parsing function with {num_instr} instructions")

            # Read opcodes array
            for _ in range(num_instr):
                proto.opcodes.append(reader.read_byte())

            # Read operand arrays (each has num_instr entries)
            for _ in range(num_instr):
                proto.operand_a.append(reader.read_varint())
            for _ in range(num_instr):
                proto.operand_b.append(reader.read_varint())
            for _ in range(num_instr):
                proto.operand_c.append(reader.read_varint())
            for _ in range(num_instr):
                proto.operand_d.append(reader.read_varint())
            for _ in range(num_instr):
                proto.operand_e.append(reader.read_varint())

            # Read string constants
            num_strings = reader.read_varint()
            for _ in range(num_strings):
                str_len = reader.read_varint()
                s = reader.read_string(str_len)
                proto.strings.append(s)

            return proto

        except Exception as e:
            print(f"  Parse error: {e}")
            return None

    def disassemble_function(self, proto: FunctionProto) -> List[str]:
        """Disassemble a function to pseudo-assembly."""
        lines = []

        for pc in range(proto.num_instructions):
            op = proto.opcodes[pc] if pc < len(proto.opcodes) else 0
            a = proto.operand_a[pc] if pc < len(proto.operand_a) else 0
            b = proto.operand_b[pc] if pc < len(proto.operand_b) else 0
            c = proto.operand_c[pc] if pc < len(proto.operand_c) else 0
            d = proto.operand_d[pc] if pc < len(proto.operand_d) else 0
            e = proto.operand_e[pc] if pc < len(proto.operand_e) else 0

            op_info = OPCODES.get(op, ("UNKNOWN", ""))
            op_name = op_info[0]

            # Format instruction
            line = f"[{pc:4d}] {op_name:12s} A={a:4d} B={b:4d} C={c:4d} D={d:4d} E={e:4d}"

            # Add interpretation based on opcode
            comment = ""
            if op == 0xBD:  # RETURN
                comment = f"; return R{a}..."
            elif op == 0xBC:  # SETTABLE
                comment = f"; R{b}[R{d}] = R{a}"
            elif op == 0xB7:  # MUL
                comment = f"; R{b} = R{a} * R{d}"
            elif op == 0xB6:  # DIV
                comment = f"; R{d} = R{a} / R{b}"
            elif op == 0xAD:  # CONCAT
                comment = f"; R{d} = R{b} .. R{a}"
            elif op == 0xAA:  # CLOSURE
                comment = f"; R{d} = closure(proto[{a}])"
            elif op == 0xC0:  # LOADK
                if b < len(proto.strings):
                    s = proto.strings[b]
                    if len(s) > 30:
                        s = s[:30] + "..."
                    comment = f'; R{b} = "{s}"'
                else:
                    comment = f"; R{b} = K[{a}]"
            elif op == 0xBE:  # LOADNIL
                comment = f"; R{b} = nil"

            lines.append(line + comment)

        return lines

    def decompile_to_lua(self, proto: FunctionProto, indent: int = 0) -> List[str]:
        """Attempt to decompile function to Lua source."""
        lines = []
        prefix = "    " * indent

        # Function header
        params = [f"a{i}" for i in range(proto.num_params)]
        if proto.is_vararg:
            params.append("...")
        lines.append(f"{prefix}function({', '.join(params)})")

        # For now, output as comments with disassembly
        lines.append(f"{prefix}    -- Disassembly ({proto.num_instructions} instructions):")

        disasm = self.disassemble_function(proto)
        for line in disasm[:50]:  # Limit output
            lines.append(f"{prefix}    -- {line}")

        if proto.num_instructions > 50:
            lines.append(f"{prefix}    -- ... ({proto.num_instructions - 50} more instructions)")

        lines.append(f"{prefix}end")
        return lines

    def decompile(self) -> str:
        """Main decompilation entry point."""
        self.extract_bytecode()
        self.analyze_bytecode_header()
        self.analyze_instruction_patterns()

        output = []
        output.append("-- Decompiled from Luraph v14.5.2 bytecode")
        output.append("-- WARNING: This is a partial decompilation")
        output.append("")

        # Try to parse functions from main bytecode
        if self.main_bytecode:
            reader = BytecodeReader(self.main_bytecode)

            print("\n=== Attempting to parse functions ===")

            # Try at different offsets
            for offset in [0, 4, 8, 16]:
                reader.pos = offset
                print(f"\nTrying at offset {offset}:")
                proto = self.try_parse_function(reader)
                if proto and proto.num_instructions > 0:
                    output.append(f"-- Function at offset {offset}")
                    output.extend(self.decompile_to_lua(proto))
                    output.append("")

        # Output string constants found
        output.append("-- String constants found in bytecode:")
        strings_found = set()
        for bc in self.bytecode_strings:
            # Look for readable strings
            i = 0
            while i < len(bc) - 4:
                # Check for printable sequences
                j = i
                while j < len(bc) and 32 <= bc[j] <= 126:
                    j += 1
                if j - i >= 4:
                    s = bc[i:j].decode('ascii', errors='ignore')
                    if s and not s.isdigit():
                        strings_found.add(s)
                i = max(i + 1, j)

        for s in sorted(strings_found)[:100]:
            if len(s) > 60:
                s = s[:60] + "..."
            output.append(f'--   "{s}"')

        return "\n".join(output)


def main():
    print("=== Luraph v14.5.2 Bytecode Decompiler ===")

    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        vm_code = f.read()

    print(f"VM code size: {len(vm_code)} bytes")
    print()

    decompiler = LuraphDecompiler(vm_code)
    result = decompiler.decompile()

    # Save output
    output_file = '/home/user/deobluraph/decompiled_output.lua'
    with open(output_file, 'w') as f:
        f.write(result)

    print(f"\n=== Output saved to {output_file} ===")
    print("\nFirst 100 lines of output:")
    for line in result.split('\n')[:100]:
        print(line)


if __name__ == '__main__':
    main()
