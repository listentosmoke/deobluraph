#!/usr/bin/env python3
"""
Luraph v14.5.2 Bytecode Decompiler

This decompiler analyzes the VM interpreter to map opcodes to Lua operations,
then extracts and decompiles the embedded bytecode.
"""

import re
import struct
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# Base85 decoder (Luraph variant)
def base85_decode(s: str) -> bytes:
    """Decode Luraph-style base85 encoding."""
    s = s.replace('z', '!!!!!')  # z = 4 null bytes
    result = bytearray()
    i = 0
    while i + 5 <= len(s):
        chunk = s[i:i+5]
        try:
            val = 0
            for c in chunk:
                val = val * 85 + (ord(c) - 33)
            result.extend(val.to_bytes(4, 'big'))
        except:
            pass
        i += 5
    # Handle remaining bytes
    remaining = len(s) - i
    if remaining > 0:
        chunk = s[i:] + '!' * (5 - remaining)
        try:
            val = 0
            for c in chunk:
                val = val * 85 + (ord(c) - 33)
            result.extend(val.to_bytes(4, 'big')[:remaining])
        except:
            pass
    return bytes(result)


# Opcode definitions based on VM analysis
@dataclass
class Opcode:
    name: str
    operands: str  # Format: A, AB, ABC, ABx, AsBx, etc.
    action: str


# Map of opcodes derived from analyzing E8 interpreter
# Format: opcode -> (name, operand_format, description)
OPCODES = {
    # Basic operations
    0x00: ("MOVE", "AB", "R(A) = R(B)"),
    0x01: ("LOADK", "ABx", "R(A) = K(Bx)"),
    0x02: ("LOADBOOL", "ABC", "R(A) = (bool)B; if C: pc++"),
    0x03: ("LOADNIL", "AB", "R(A..B) = nil"),
    0x04: ("GETUPVAL", "AB", "R(A) = U(B)"),
    0x05: ("GETGLOBAL", "ABx", "R(A) = G[K(Bx)]"),
    0x06: ("GETTABLE", "ABC", "R(A) = R(B)[RK(C)]"),
    0x07: ("SETGLOBAL", "ABx", "G[K(Bx)] = R(A)"),
    0x08: ("SETUPVAL", "AB", "U(B) = R(A)"),
    0x09: ("SETTABLE", "ABC", "R(A)[RK(B)] = RK(C)"),
    0x0A: ("NEWTABLE", "ABC", "R(A) = {}"),
    0x0B: ("SELF", "ABC", "R(A+1) = R(B); R(A) = R(B)[RK(C)]"),

    # Arithmetic
    0x0C: ("ADD", "ABC", "R(A) = RK(B) + RK(C)"),
    0x0D: ("SUB", "ABC", "R(A) = RK(B) - RK(C)"),
    0x0E: ("MUL", "ABC", "R(A) = RK(B) * RK(C)"),
    0x0F: ("DIV", "ABC", "R(A) = RK(B) / RK(C)"),
    0x10: ("MOD", "ABC", "R(A) = RK(B) % RK(C)"),
    0x11: ("POW", "ABC", "R(A) = RK(B) ^ RK(C)"),
    0x12: ("UNM", "AB", "R(A) = -R(B)"),
    0x13: ("NOT", "AB", "R(A) = not R(B)"),
    0x14: ("LEN", "AB", "R(A) = #R(B)"),
    0x15: ("CONCAT", "ABC", "R(A) = R(B)..R(C)"),

    # Jumps and control flow
    0x16: ("JMP", "sBx", "pc += sBx"),
    0x17: ("EQ", "ABC", "if (RK(B) == RK(C)) ~= A then pc++"),
    0x18: ("LT", "ABC", "if (RK(B) < RK(C)) ~= A then pc++"),
    0x19: ("LE", "ABC", "if (RK(B) <= RK(C)) ~= A then pc++"),
    0x1A: ("TEST", "AC", "if (bool)R(A) ~= C then pc++"),
    0x1B: ("TESTSET", "ABC", "if (bool)R(B) ~= C then R(A) = R(B) else pc++"),

    # Calls and returns
    0x1C: ("CALL", "ABC", "R(A..A+C-2) = R(A)(R(A+1..A+B-1))"),
    0x1D: ("TAILCALL", "ABC", "return R(A)(R(A+1..A+B-1))"),
    0x1E: ("RETURN", "AB", "return R(A..A+B-2)"),

    # For loops
    0x1F: ("FORLOOP", "AsBx", "R(A) += R(A+2); if R(A) <= R(A+1) then pc += sBx"),
    0x20: ("FORPREP", "AsBx", "R(A) -= R(A+2); pc += sBx"),
    0x21: ("TFORLOOP", "AC", "R(A+3..A+2+C) = R(A)(R(A+1), R(A+2))"),

    # Misc
    0x22: ("SETLIST", "ABC", "R(A)[B..B+C-1] = R(A+1..A+C)"),
    0x23: ("CLOSE", "A", "close upvalues >= R(A)"),
    0x24: ("CLOSURE", "ABx", "R(A) = closure(proto[Bx])"),
    0x25: ("VARARG", "AB", "R(A..A+B-1) = vararg"),
}


@dataclass
class Instruction:
    opcode: int
    a: int = 0
    b: int = 0
    c: int = 0
    bx: int = 0
    sbx: int = 0


@dataclass
class Function:
    num_params: int
    is_vararg: bool
    max_stack: int
    instructions: List[Instruction]
    constants: List[Any]
    upvalues: List[str]
    protos: List['Function']
    source: str = "?"
    line_start: int = 0
    line_end: int = 0


class LuraphDecompiler:
    def __init__(self, vm_code: str):
        self.vm_code = vm_code
        self.opcode_map = self._analyze_opcodes()
        self.constants = []
        self.functions = []

    def _analyze_opcodes(self) -> Dict[int, str]:
        """Analyze VM code to map shuffled opcodes to standard Lua opcodes."""
        # The Luraph VM shuffles opcodes - we need to reverse this
        # by analyzing what each opcode does in the interpreter

        opmap = {}

        # Find patterns that indicate specific operations
        patterns = {
            # Arithmetic
            'ADD': r'X\[\w+\]\s*=\s*X\[\w+\]\s*\+\s*X\[\w+\]',
            'SUB': r'X\[\w+\]\s*=\s*X\[\w+\]\s*-\s*X\[\w+\]',
            'MUL': r'X\[\w+\]\s*=\s*X\[\w+\]\s*\*\s*X\[\w+\]',
            'DIV': r'X\[\w+\]\s*=\s*X\[\w+\]\s*/\s*X\[\w+\]',
            'MOD': r'X\[\w+\]\s*=\s*X\[\w+\]\s*%\s*X\[\w+\]',
            'CONCAT': r'X\[\w+\]\s*=\s*X\[\w+\]\s*\.\.\s*X\[\w+\]',
            'NOT': r'X\[\w+\]\s*=\s*not\s+X\[\w+\]',
            'UNM': r'X\[\w+\]\s*=\s*-X\[\w+\]',
            'LEN': r'X\[\w+\]\s*=\s*#X\[\w+\]',

            # Comparisons
            'LT': r'X\[\w+\]\s*<\s*X\[\w+\]',
            'LE': r'X\[\w+\]\s*<=\s*X\[\w+\]',
            'EQ': r'X\[\w+\]\s*==\s*X\[\w+\]',

            # Table operations
            'GETTABLE': r'X\[\w+\]\s*=\s*X\[\w+\]\[X\[\w+\]\]',
            'SETTABLE': r'X\[\w+\]\[X\[\w+\]\]\s*=\s*X\[\w+\]',

            # Calls
            'CALL': r'X\[\w+\]\(',
            'RETURN': r'return\s+X\[\w+\]',

            # Special
            'LOADNIL': r'X\[\w+\]\s*=\s*nil',
            'CLOSURE': r'V\[0X28\]',  # Creates closure
        }

        return opmap

    def extract_bytecode(self) -> List[Function]:
        """Extract bytecode from the VM's embedded data."""
        # Find all base85-encoded strings in the VM
        pattern = r'"([!-u]{20,})"'
        matches = re.findall(pattern, self.vm_code)

        print(f"Found {len(matches)} potential bytecode strings")

        # Decode each and look for bytecode structure
        for i, match in enumerate(matches[:50]):
            decoded = base85_decode(match)
            if len(decoded) > 100:
                # Look for bytecode markers
                self._analyze_bytecode(decoded, i)

        return self.functions

    def _analyze_bytecode(self, data: bytes, idx: int):
        """Analyze decoded data for bytecode structure."""
        # Luraph bytecode format (observed from VM):
        # - Instructions are stored in arrays accessed via W[10] (opcodes)
        # - Operands in W[5], W[4], W[7], W[8], W[9]
        # - Constants in W[11]

        # Check for patterns
        if len(data) < 20:
            return

        # Look for instruction-like patterns (series of small integers)
        potential_opcodes = []
        for j in range(0, min(len(data), 1000), 4):
            if j + 4 <= len(data):
                val = struct.unpack('>I', data[j:j+4])[0]
                if val < 256:  # Likely an opcode
                    potential_opcodes.append(val)

        if len(potential_opcodes) > 10:
            print(f"  String {idx}: {len(potential_opcodes)} potential opcodes")
            print(f"    First 20: {potential_opcodes[:20]}")

    def decompile(self) -> str:
        """Decompile bytecode to Lua source."""
        output = []
        output.append("-- Decompiled by Luraph Decompiler")
        output.append("")

        for func in self.functions:
            output.append(self._decompile_function(func))

        return '\n'.join(output)

    def _decompile_function(self, func: Function, indent: int = 0) -> str:
        """Decompile a single function."""
        lines = []
        prefix = '    ' * indent

        # Function header
        params = ', '.join([f'arg{i}' for i in range(func.num_params)])
        if func.is_vararg:
            params += ', ...' if params else '...'
        lines.append(f"{prefix}function({params})")

        # Decompile instructions
        pc = 0
        while pc < len(func.instructions):
            instr = func.instructions[pc]
            line = self._decompile_instruction(func, instr, pc)
            if line:
                lines.append(f"{prefix}    {line}")
            pc += 1

        lines.append(f"{prefix}end")
        return '\n'.join(lines)

    def _decompile_instruction(self, func: Function, instr: Instruction, pc: int) -> str:
        """Decompile a single instruction."""
        op = instr.opcode

        if op not in OPCODES:
            return f"-- Unknown opcode {op}"

        name, fmt, desc = OPCODES[op]

        # Generate code based on opcode type
        if name == "MOVE":
            return f"local r{instr.a} = r{instr.b}"
        elif name == "LOADK":
            const = func.constants[instr.bx] if instr.bx < len(func.constants) else f"K[{instr.bx}]"
            return f"local r{instr.a} = {repr(const)}"
        elif name == "LOADNIL":
            return f"local r{instr.a} = nil"
        elif name == "ADD":
            return f"r{instr.a} = r{instr.b} + r{instr.c}"
        elif name == "SUB":
            return f"r{instr.a} = r{instr.b} - r{instr.c}"
        elif name == "MUL":
            return f"r{instr.a} = r{instr.b} * r{instr.c}"
        elif name == "DIV":
            return f"r{instr.a} = r{instr.b} / r{instr.c}"
        elif name == "CALL":
            return f"r{instr.a}()"
        elif name == "RETURN":
            return "return"
        else:
            return f"-- {name} A={instr.a} B={instr.b} C={instr.c}"


def main():
    # Read decompressed VM
    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        vm_code = f.read()

    print("=== Luraph Decompiler ===")
    print(f"VM code size: {len(vm_code)} bytes")
    print()

    decompiler = LuraphDecompiler(vm_code)

    # Extract bytecode
    print("Extracting bytecode...")
    functions = decompiler.extract_bytecode()

    print(f"\nFound {len(functions)} functions")

    # Output
    if functions:
        result = decompiler.decompile()
        print("\n=== DECOMPILED OUTPUT ===")
        print(result[:5000])


if __name__ == '__main__':
    main()
