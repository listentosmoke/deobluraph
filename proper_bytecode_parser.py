#!/usr/bin/env python3
"""
Proper Luraph bytecode parser based on VM deserialization logic.

The bytecode reader:
- B[20] = base85-decoded bytecode bytes
- B[11] = current position
- B[14] = string.byte (reads bytes)
- B[0X22]() = LEB128 varint reader

Magic number offsets discovered:
- 9816: subtracted from some counts
- 32325: subtracted from instruction count
- 41105: subtracted from another count
"""

import struct
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


def base85_decode(s: str) -> bytes:
    """Decode Luraph base85."""
    s = s.replace('z', '!!!!!')
    result = bytearray()
    i = 0
    while i + 5 <= len(s):
        chunk = s[i:i+5]
        try:
            vals = [ord(c) - 33 for c in chunk]
            val = vals[4] + vals[3]*85 + vals[2]*7225 + vals[1]*614125 + vals[0]*52200625
            result.extend(struct.pack('>I', val))
        except:
            pass
        i += 5
    return bytes(result)


class BytecodeReader:
    """Simulates the Luraph bytecode reader (B[20], B[11], B[14], B[0X22])."""

    def __init__(self, data: bytes):
        self.data = data  # B[20]
        self.pos = 1       # B[11] - starts at 1 in Lua (1-indexed)

    def read_byte(self) -> int:
        """B[14](B[20], B[11], B[11])"""
        if self.pos > len(self.data):
            return 0
        val = self.data[self.pos - 1]  # Convert to 0-indexed
        self.pos += 1
        return val

    def read_varint(self) -> int:
        """B[0X22]() - LEB128 unsigned varint reader."""
        result = 0
        multiplier = 1

        while True:
            byte = self.read_byte()
            if byte > 127:
                result += (byte - 128) * multiplier
            else:
                result += byte * multiplier
                break
            multiplier *= 128
            if multiplier > 2**35:  # Sanity check
                break

        return result

    def read_bytes(self, n: int) -> bytes:
        """Read n raw bytes."""
        result = self.data[self.pos - 1:self.pos - 1 + n]
        self.pos += n
        return result

    def read_string(self) -> str:
        """Read a length-prefixed string."""
        length = self.read_varint()
        if length == 0:
            return ""
        data = self.read_bytes(length)
        return data.decode('utf-8', errors='replace')

    def remaining(self) -> int:
        return len(self.data) - self.pos + 1

    def seek(self, pos: int):
        self.pos = pos


# Magic numbers from deserialization
MAGIC_UPVALUES = 9816
MAGIC_INSTRUCTIONS = 32325
MAGIC_OTHER = 41105


@dataclass
class LuraphFunction:
    """Luraph function prototype."""
    offset: int = 0
    num_params: int = 0
    is_vararg: bool = False
    max_stack: int = 0
    num_upvalues: int = 0
    num_instructions: int = 0

    opcodes: List[int] = field(default_factory=list)
    operand_a: List[int] = field(default_factory=list)
    operand_b: List[int] = field(default_factory=list)
    operand_c: List[int] = field(default_factory=list)
    operand_d: List[int] = field(default_factory=list)
    operand_e: List[int] = field(default_factory=list)

    strings: List[str] = field(default_factory=list)
    numbers: List[float] = field(default_factory=list)
    protos: List['LuraphFunction'] = field(default_factory=list)


def try_parse_at_offset(reader: BytecodeReader, start_pos: int) -> Optional[LuraphFunction]:
    """Try to parse a function prototype at the given offset."""
    reader.seek(start_pos)
    func = LuraphFunction(offset=start_pos)

    try:
        # Read potential header values
        v1 = reader.read_varint()
        v2 = reader.read_varint()
        v3 = reader.read_varint()
        v4 = reader.read_varint()
        v5 = reader.read_varint()

        # Try different interpretations with magic numbers

        # Interpretation 1: v1-MAGIC is instruction count
        instr_count_1 = v1 - MAGIC_INSTRUCTIONS
        if 1 <= instr_count_1 <= 50000:
            func.num_instructions = instr_count_1

            # Try reading opcodes
            opcodes = []
            for _ in range(min(instr_count_1, 1000)):
                if reader.remaining() < 1:
                    break
                op = reader.read_byte()
                opcodes.append(op)

            # Check if opcodes look valid
            known_count = sum(1 for op in opcodes if 0xA0 <= op <= 0xC0 or op < 0x24)
            if known_count > len(opcodes) * 0.1:  # At least 10% known
                func.opcodes = opcodes
                return func

        # Interpretation 2: Different structure
        reader.seek(start_pos)

        # Maybe header is: params, vararg, stack, upvalues, instructions
        params = reader.read_varint()
        if params > 255:
            return None

        vararg = reader.read_varint()
        if vararg > 1:
            return None

        stack = reader.read_varint()
        if stack > 255:
            return None

        upvalues_raw = reader.read_varint()
        upvalues = upvalues_raw - MAGIC_UPVALUES if upvalues_raw > MAGIC_UPVALUES else upvalues_raw

        if not (0 <= upvalues <= 255):
            return None

        instr_raw = reader.read_varint()
        instr_count = instr_raw - MAGIC_INSTRUCTIONS if instr_raw > MAGIC_INSTRUCTIONS else instr_raw

        if not (1 <= instr_count <= 50000):
            return None

        func.num_params = params
        func.is_vararg = vararg == 1
        func.max_stack = stack
        func.num_upvalues = upvalues
        func.num_instructions = instr_count

        # Try reading opcodes
        opcodes = []
        for _ in range(min(instr_count, 1000)):
            if reader.remaining() < 1:
                break
            op = reader.read_byte()
            opcodes.append(op)

        func.opcodes = opcodes
        return func

    except Exception as e:
        return None


def scan_for_functions(reader: BytecodeReader) -> List[LuraphFunction]:
    """Scan bytecode for function prototypes."""
    functions = []

    # Try parsing at various offsets
    for start in range(1, min(reader.remaining(), 10000), 1):
        func = try_parse_at_offset(reader, start)
        if func and len(func.opcodes) > 10:
            # Verify this looks like a real function
            functions.append(func)

            # Skip ahead past this function
            if len(functions) >= 20:
                break

    return functions


def analyze_function(func: LuraphFunction):
    """Analyze a parsed function."""
    print(f"\n=== Function at offset {func.offset} ===")
    print(f"  Parameters: {func.num_params}")
    print(f"  Vararg: {func.is_vararg}")
    print(f"  Max stack: {func.max_stack}")
    print(f"  Upvalues: {func.num_upvalues}")
    print(f"  Instructions: {func.num_instructions}")

    if func.opcodes:
        print(f"  Opcodes parsed: {len(func.opcodes)}")

        # Opcode distribution
        from collections import Counter
        counts = Counter(func.opcodes)

        print(f"  Top opcodes:")
        opcode_names = {
            0x00: "NOP", 0x01: "MOVE", 0xAA: "CLOSURE", 0xAB: "CALL0",
            0xAD: "CONCAT", 0xAE: "JMP", 0xAF: "FORPREP", 0xB4: "FORLOOP",
            0xB5: "GT", 0xB6: "DIV", 0xB7: "MUL", 0xB9: "VARARG",
            0xBA: "CALL_NORET", 0xBB: "SUBK", 0xBC: "SETTABLE",
            0xBD: "RETURN", 0xBE: "LOADNIL", 0xBF: "EQ_JMP", 0xC0: "LOADK"
        }

        for op, count in counts.most_common(10):
            name = opcode_names.get(op, f"0x{op:02X}")
            print(f"    {name}: {count}")


def main():
    print("=== Proper Luraph Bytecode Parser ===\n")

    # Read VM code
    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        vm_code = f.read()

    # Extract bytecode
    bytecode = None
    pos = 0
    while True:
        start = vm_code.find('[=[', pos)
        if start == -1:
            break
        end = vm_code.find(']=]', start + 3)
        if end == -1:
            break

        content = vm_code[start + 3:end].replace('\n', '').replace('\r', '').replace(' ', '')
        if len(content) > 100:
            decoded = base85_decode(content)
            if bytecode is None or len(decoded) > len(bytecode):
                bytecode = decoded

        pos = end + 3

    if not bytecode:
        print("No bytecode found!")
        return

    print(f"Bytecode size: {len(bytecode)} bytes")

    reader = BytecodeReader(bytecode)

    # Read first few varints to understand structure
    print("\nFirst 30 varints:")
    reader.seek(1)
    for i in range(30):
        pos = reader.pos
        val = reader.read_varint()
        adjusted = val - MAGIC_INSTRUCTIONS if val > MAGIC_INSTRUCTIONS else val
        print(f"  [{i:2d}] @{pos:5d}: {val:10d} (adjusted: {adjusted})")

    # Scan for functions
    print("\n\nScanning for functions...")
    functions = scan_for_functions(reader)
    print(f"Found {len(functions)} potential functions")

    for func in functions[:10]:
        analyze_function(func)


if __name__ == '__main__':
    main()
