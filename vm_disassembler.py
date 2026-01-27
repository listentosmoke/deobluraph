#!/usr/bin/env python3
"""
Luraph VM Disassembler
Fully reverse engineers the VM instruction set and disassembles bytecode
"""

import re
import struct
import json
from collections import defaultdict

class LuraphVM:
    def __init__(self):
        self.opcodes = {}
        self.constants = []
        self.bytecode = []
        self.instructions = []

    def load_vm_code(self, filename):
        """Load and parse the deobfuscated VM code"""
        with open(filename, 'r') as f:
            self.code = f.read()

        # Extract the main VM function body
        self._extract_vm_body()
        self._map_opcodes()

    def _extract_vm_body(self):
        """Extract the main bytecode interpreter function"""
        # Find E8 function - the main interpreter
        match = re.search(r'E8=function\([^)]*\)(.*?)(?=end,\w+=function)', self.code, re.DOTALL)
        if match:
            self.vm_body = match.group(1)
            print(f"[*] Extracted VM body: {len(self.vm_body)} chars")

    def _map_opcodes(self):
        """Map all opcodes by analyzing the switch-case structure"""
        if not hasattr(self, 'vm_body'):
            return

        # The VM uses nested if-else with opcode ranges
        # Pattern: if o>=VALUE then ... elseif o>=VALUE2 then ...

        # First, let's extract all the specific opcode checks and their code
        self.opcodes = {}

        # Find patterns like: if o==0xNN then CODE or o~=0xNN (for else branch)
        # Also handle: if o<0xNN, if o>=0xNN for range checks

        body = self.vm_body

        # Strategy: Find all lines with operations and trace back to find the opcode
        # The VM structure is: check opcode range -> check specific opcode -> execute

        # Let's find all the actual operations and their corresponding opcodes
        self._deep_parse_opcodes(body)

    def _deep_parse_opcodes(self, body):
        """Deep parse the opcode structure"""
        # Find all equality checks for opcodes
        eq_checks = list(re.finditer(r'if\s+o\s*==\s*(0x[0-9a-fA-F]+|0b[01_]+|\d+)\s*then', body))
        neq_checks = list(re.finditer(r'o\s*~=\s*(0x[0-9a-fA-F]+|0b[01_]+|\d+)', body))

        print(f"[*] Found {len(eq_checks)} direct opcode checks")

        # For each check, extract the operation that follows
        for match in eq_checks:
            op_str = match.group(1)
            opcode = self._parse_number(op_str)
            if opcode is None:
                continue

            # Get the code after this check until the next check or end
            start = match.end()
            # Find the end of this branch
            end = self._find_branch_end(body, start)
            branch_code = body[start:end]

            # Identify the operation
            operation = self._identify_vm_operation(branch_code)
            if operation:
                self.opcodes[opcode] = operation

        # Also check for operations in o~= branches (else cases)
        for match in neq_checks:
            op_str = match.group(1)
            opcode = self._parse_number(op_str)
            # These are exclusions, but can help identify other opcodes

        print(f"[*] Mapped {len(self.opcodes)} opcodes")

    def _parse_number(self, s):
        """Parse a number string (hex, binary, or decimal)"""
        s = s.replace('_', '')
        try:
            if s.startswith('0x') or s.startswith('0X'):
                return int(s, 16)
            elif s.startswith('0b') or s.startswith('0B'):
                return int(s[2:], 2)
            else:
                return int(s)
        except:
            return None

    def _find_branch_end(self, code, start):
        """Find the end of a code branch"""
        depth = 0
        i = start
        while i < len(code):
            # Look for keywords that change depth
            if code[i:i+4] == 'then' or code[i:i+2] == 'do':
                depth += 1
            elif code[i:i+6] == 'elseif' or code[i:i+4] == 'else':
                if depth <= 1:
                    return i
            elif code[i:i+3] == 'end':
                depth -= 1
                if depth < 0:
                    return i
            i += 1
        return len(code)

    def _identify_vm_operation(self, code):
        """Identify the VM operation from code"""
        ops = {
            # Arithmetic
            'ADD': r'X\[.+?\]\s*=.*?\+',
            'SUB': r'X\[.+?\]\s*=.*?-\s*[^-]',
            'MUL': r'X\[.+?\]\s*=.*?\*',
            'DIV': r'X\[.+?\]\s*=.*?/',
            'MOD': r'X\[.+?\]\s*=.*?%',
            'POW': r'X\[.+?\]\s*=.*?\^',
            'IDIV': r'X\[.+?\]\s*=.*?//',

            # Comparison
            'EQ': r'X\[.+?\]\s*==\s*[^=]',
            'NE': r'X\[.+?\]\s*~=',
            'LT': r'X\[.+?\]\s*<[^=]',
            'LE': r'X\[.+?\]\s*<=',
            'GT': r'X\[.+?\]\s*>[^=]',
            'GE': r'X\[.+?\]\s*>=',

            # Logical/Bitwise
            'NOT': r'=\s*not\s+X\[',
            'BAND': r'\.band\s*\(',
            'BOR': r'\.bor\s*\(',
            'BXOR': r'\.bxor\s*\(',
            'BNOT': r'\.bnot\s*\(',
            'SHL': r'\.lshift\s*\(',
            'SHR': r'\.rshift\s*\(',

            # Unary
            'UNM': r'=\s*-\s*X\[',
            'LEN': r'=\s*#\s*X\[',

            # String
            'CONCAT': r'X\[.+?\]\s*\.\.',

            # Table
            'NEWTABLE': r'=\s*\{\s*\}',
            'GETTABLE': r'X\[.+?\]\[X\[.+?\]\]',
            'SETTABLE': r'\[X\[.+?\]\]\s*=\s*X\[',
            'SETLIST': r'for.*?in.*?pairs',

            # Upvalues
            'GETUPVAL': r'=\s*c\[',
            'SETUPVAL': r'c\[\d+\]\s*=',

            # Functions
            'CALL': r'X\[.+?\]\s*\(',
            'TAILCALL': r'return\s+X\[.+?\]\s*\(',
            'RETURN': r'return\s+X\[',
            'VARARG': r'\.\.\..*select',

            # Control flow
            'JMP': r'w\s*=\s*[^;]+\[w\]',
            'FORPREP': r'G\s*=\s*X\[',
            'FORLOOP': r'G\s*<=',
            'TFORLOOP': r'for.*?in',

            # Loading
            'LOADK': r'X\[.+?\]\s*=\s*[UmSN]\[',
            'LOADNIL': r'X\[.+?\]\s*=\s*nil',
            'LOADBOOL': r'X\[.+?\]\s*=\s*(true|false)',
            'MOVE': r'X\[.+?\]\s*=\s*X\[.+?\][;,\s]',
            'GETGLOBAL': r'X\[.+?\]\s*=\s*V\[',
            'SETGLOBAL': r'V\[.+?\]\s*=\s*X\[',

            # Closures
            'CLOSURE': r'function\s*\(',
            'CLOSE': r'H\[.+?\]\s*=\s*nil',

            # Special
            'SELF': r'X\[.+?\]\s*=\s*X\[.+?\].*?X\[.+?\]\[',
            'TEST': r'if\s+X\[.+?\]\s*then',
            'TESTSET': r'if\s+X\[.+?\]\s*==',
        }

        found = []
        for name, pattern in ops.items():
            if re.search(pattern, code):
                found.append(name)

        if found:
            return found[0]  # Return most likely operation
        return None

    def decode_bytecode(self, data):
        """Decode bytecode from binary data"""
        instructions = []
        i = 0

        while i < len(data):
            if i + 4 > len(data):
                break

            # Read instruction word
            instr = struct.unpack('<I', data[i:i+4])[0]

            # Decode instruction fields (Lua 5.x format)
            opcode = instr & 0x3F  # 6 bits
            A = (instr >> 6) & 0xFF  # 8 bits
            B = (instr >> 23) & 0x1FF  # 9 bits
            C = (instr >> 14) & 0x1FF  # 9 bits
            Bx = (instr >> 14) & 0x3FFFF  # 18 bits
            sBx = Bx - 131071  # signed

            instruction = {
                'offset': i,
                'raw': instr,
                'opcode': opcode,
                'A': A,
                'B': B,
                'C': C,
                'Bx': Bx,
                'sBx': sBx,
            }

            # Try to identify the operation
            if opcode in self.opcodes:
                instruction['op_name'] = self.opcodes[opcode]
            else:
                instruction['op_name'] = f'OP_{opcode}'

            instructions.append(instruction)
            i += 4

        return instructions

    def disassemble(self, bytecode_file):
        """Disassemble a bytecode file"""
        with open(bytecode_file, 'rb') as f:
            data = f.read()

        print(f"[*] Disassembling {len(data)} bytes")

        instructions = self.decode_bytecode(data)
        return instructions

def extract_embedded_bytecode():
    """Extract bytecode embedded in the deobfuscated Lua file"""
    with open('/home/user/deobluraph/deobfuscated.lua', 'r') as f:
        code = f.read()

    # Find all long string literals (bytecode is often in these)
    long_strings = re.findall(r'\[=*\[(.*?)\]=*\]', code, re.DOTALL)

    print(f"[*] Found {len(long_strings)} embedded data blocks")

    # Decode each block
    decoded_blocks = []
    for i, block in enumerate(long_strings):
        # Try base85 decoding
        decoded = base85_decode(block)
        if decoded:
            decoded_blocks.append({
                'index': i,
                'size': len(decoded),
                'data': decoded
            })

    return decoded_blocks

def base85_decode(data):
    """Decode base85 encoded data (Luraph format)"""
    # Replace 'z' with '!!!!!' (Luraph uses this shorthand)
    data = data.replace('z', '!!!!!')

    result = bytearray()
    i = 0
    while i + 5 <= len(data):
        chunk = data[i:i+5]
        try:
            value = 0
            for c in chunk:
                value = value * 85 + (ord(c) - 33)
            result.extend(struct.pack('>I', value))
        except:
            pass
        i += 5

    return bytes(result)

def analyze_bytecode_structure(data):
    """Analyze the structure of decoded bytecode"""
    analysis = {
        'size': len(data),
        'header': data[:16].hex() if len(data) >= 16 else data.hex(),
        'patterns': {},
    }

    # Look for common patterns
    patterns = {
        'null_bytes': len(re.findall(b'\x00\x00', data)),
        '0fe0_marker': len(re.findall(b'\x0f\xe0', data)),
        'repeated_patterns': {},
    }

    # Find 4-byte repeated patterns (potential instructions)
    for i in range(0, len(data) - 3, 4):
        chunk = data[i:i+4]
        key = chunk.hex()
        if key not in patterns['repeated_patterns']:
            patterns['repeated_patterns'][key] = 0
        patterns['repeated_patterns'][key] += 1

    analysis['patterns'] = patterns
    return analysis

def main():
    print("=" * 60)
    print("LURAPH VM DISASSEMBLER")
    print("=" * 60)
    print()

    # Create VM instance
    vm = LuraphVM()

    # Load VM code
    print("[*] Loading deobfuscated VM code...")
    vm.load_vm_code('/home/user/deobluraph/deobfuscated.lua')

    # Print opcode map
    print()
    print("=== OPCODE MAP ===")
    for opcode in sorted(vm.opcodes.keys()):
        print(f"  0x{opcode:02X} ({opcode:3d}): {vm.opcodes[opcode]}")

    # Save opcode map
    with open('full_opcode_map.json', 'w') as f:
        json.dump({str(k): v for k, v in vm.opcodes.items()}, f, indent=2)

    print()
    print(f"[*] Saved opcode map to full_opcode_map.json")

    # Extract and analyze embedded bytecode
    print()
    print("[*] Extracting embedded bytecode...")
    blocks = extract_embedded_bytecode()

    total_size = sum(b['size'] for b in blocks)
    print(f"[*] Extracted {len(blocks)} blocks, total {total_size} bytes")

    # Analyze each block
    print()
    print("=== BYTECODE ANALYSIS ===")
    for block in blocks[:5]:
        print(f"\nBlock {block['index']}:")
        analysis = analyze_bytecode_structure(block['data'])
        print(f"  Size: {analysis['size']} bytes")
        print(f"  Header: {analysis['header']}")
        print(f"  Null byte pairs: {analysis['patterns']['null_bytes']}")
        print(f"  0FE0 markers: {analysis['patterns']['0fe0_marker']}")

        # Save decoded block
        with open(f'bytecode_block_{block["index"]}.bin', 'wb') as f:
            f.write(block['data'])

    return vm

if __name__ == "__main__":
    main()
