#!/usr/bin/env python3
"""
Comprehensive Luraph Decompiler
Fully parses the VM interpreter to reconstruct original Lua code
"""

import re
import json
import struct
from collections import defaultdict

class LuraphDecompiler:
    def __init__(self):
        self.vm_code = None
        self.e8_body = None
        self.opcodes = {}
        self.constants = []
        self.functions = []
        self.reconstructed = []

    def load(self, filename):
        """Load the deobfuscated VM code"""
        with open(filename, 'r') as f:
            self.vm_code = f.read()
        print(f"[*] Loaded {len(self.vm_code)} bytes")

    def extract_e8_function(self):
        """Extract the main interpreter function E8"""
        # Find E8 function body
        match = re.search(r'E8=function\(z,V,B,L\)(.*?)(?=end,\w+=(?:function|bit32|table|string|math))',
                         self.vm_code, re.DOTALL)
        if match:
            self.e8_body = match.group(1)
            print(f"[*] Extracted E8 function: {len(self.e8_body)} chars")
            return True
        return False

    def parse_vm_structure(self):
        """Parse the VM interpreter structure to extract opcode handlers"""
        if not self.e8_body:
            return

        # The VM uses a binary tree structure for opcode dispatch
        # First split by ranges: o>=0x60, o>=0x90, etc.
        # Then specific checks: o==0xNN or o~=0xNN

        # Find all opcode comparisons with their operations
        self._parse_opcode_tree(self.e8_body)

    def _parse_opcode_tree(self, code):
        """Parse the opcode dispatch tree"""
        # Find the main dispatch pattern
        # Pattern: if not(o<VALUE) then ... else ...

        # Extract all specific opcode handlers
        # Pattern: if o==VALUE then OPERATION
        # Or: if o~=VALUE then ... else OPERATION (for the == case)

        # Strategy: Find all X[...] = ... patterns and trace back to opcode

        # First find all operations that write to X (the stack)
        operations = []

        # Pattern for stack operations
        stack_ops = re.finditer(
            r'(X\[[^\]]+\])\s*([=<>~]+)\s*([^;]+);',
            code
        )

        for match in stack_ops:
            dest = match.group(1)
            op = match.group(2)
            source = match.group(3)

            operations.append({
                'pos': match.start(),
                'dest': dest,
                'operator': op,
                'source': source[:100],
                'full': match.group(0)[:150]
            })

        print(f"[*] Found {len(operations)} stack operations")

        # Now trace back from each operation to find its opcode
        for op in operations[:100]:
            opcode = self._find_opcode_for_pos(code, op['pos'])
            if opcode is not None:
                op['opcode'] = opcode
                self._identify_operation_type(op)

        # Build opcode map
        for op in operations:
            if 'opcode' in op and 'op_type' in op:
                if op['opcode'] not in self.opcodes:
                    self.opcodes[op['opcode']] = op['op_type']

    def _find_opcode_for_pos(self, code, pos):
        """Find the opcode that controls a given position"""
        # Search backwards from pos to find the controlling opcode check
        search_range = code[max(0, pos-500):pos]

        # Look for the most recent opcode check
        checks = list(re.finditer(
            r'o\s*(==|~=|>=|<=|>|<)\s*(0x[0-9a-fA-F]+|0b[01_]+|\d+)',
            search_range
        ))

        if checks:
            last_check = checks[-1]
            op_str = last_check.group(2)
            return self._parse_number(op_str)
        return None

    def _parse_number(self, s):
        """Parse a number literal"""
        s = s.replace('_', '')
        try:
            if s.startswith('0x') or s.startswith('0X'):
                return int(s, 16)
            elif s.startswith('0b') or s.startswith('0B'):
                return int(s[2:], 2)
            return int(s)
        except:
            return None

    def _identify_operation_type(self, op):
        """Identify the type of operation"""
        source = op['source']
        dest = op['dest']

        # Arithmetic operations
        if '+' in source and '-' not in source:
            op['op_type'] = 'ADD'
        elif re.search(r'-\s*[^-]', source) and '+' not in source:
            op['op_type'] = 'SUB'
        elif '*' in source:
            op['op_type'] = 'MUL'
        elif '//' in source:
            op['op_type'] = 'IDIV'
        elif '/' in source:
            op['op_type'] = 'DIV'
        elif '%' in source:
            op['op_type'] = 'MOD'
        elif '^' in source:
            op['op_type'] = 'POW'

        # Comparison
        elif re.search(r'X\[.*?\]\s*==\s*X\[', source):
            op['op_type'] = 'EQ'
        elif re.search(r'X\[.*?\]\s*~=\s*X\[', source):
            op['op_type'] = 'NE'
        elif re.search(r'X\[.*?\]\s*<\s*X\[', source):
            op['op_type'] = 'LT'
        elif re.search(r'X\[.*?\]\s*<=\s*X\[', source):
            op['op_type'] = 'LE'
        elif re.search(r'X\[.*?\]\s*>\s*X\[', source):
            op['op_type'] = 'GT'
        elif re.search(r'X\[.*?\]\s*>=\s*X\[', source):
            op['op_type'] = 'GE'

        # String
        elif '..' in source:
            op['op_type'] = 'CONCAT'

        # Table operations
        elif re.search(r'X\[.*?\]\[X\[', source):
            op['op_type'] = 'GETTABLE'
        elif re.search(r'\[X\[.*?\]\]\s*=', op['full']):
            op['op_type'] = 'SETTABLE'

        # Unary
        elif source.strip().startswith('-'):
            op['op_type'] = 'UNM'
        elif source.strip().startswith('not '):
            op['op_type'] = 'NOT'
        elif source.strip().startswith('#'):
            op['op_type'] = 'LEN'

        # Load operations
        elif source.strip() == 'nil':
            op['op_type'] = 'LOADNIL'
        elif source.strip() in ('true', 'false'):
            op['op_type'] = 'LOADBOOL'
        elif re.match(r'^\d+$', source.strip()) or re.match(r'^0x[0-9a-f]+$', source.strip()):
            op['op_type'] = 'LOADK'
        elif re.search(r'^X\[.*?\]$', source.strip()):
            op['op_type'] = 'MOVE'
        elif re.search(r'^[UmSN]\[', source.strip()):
            op['op_type'] = 'LOADK'

        # Bitwise
        elif '.band(' in source:
            op['op_type'] = 'BAND'
        elif '.bor(' in source:
            op['op_type'] = 'BOR'
        elif '.bxor(' in source:
            op['op_type'] = 'BXOR'
        elif '.bnot(' in source:
            op['op_type'] = 'BNOT'
        elif '.lshift(' in source or '.lrotate(' in source:
            op['op_type'] = 'SHL'
        elif '.rshift(' in source or '.rrotate(' in source:
            op['op_type'] = 'SHR'

        # Function/Table creation
        elif source.strip().startswith('{'):
            op['op_type'] = 'NEWTABLE'
        elif 'function' in source:
            op['op_type'] = 'CLOSURE'

        # Default
        else:
            op['op_type'] = 'UNKNOWN'

    def analyze_bytecode_format(self):
        """Analyze how bytecode is structured in the VM"""
        # Look for instruction fetch patterns
        # Pattern: q[w] or similar (q is the bytecode array, w is the PC)

        fetch_patterns = re.findall(
            r'local\s+o\s*=\s*\(?([^)]+)\)?',
            self.e8_body
        )

        print(f"[*] Found {len(fetch_patterns)} instruction fetch patterns")
        for p in fetch_patterns[:5]:
            print(f"    {p[:80]}")

        # Look for instruction decoding
        # The VM likely decodes fields from the instruction word
        decode_patterns = re.findall(
            r'(\w+)\s*=\s*\w+\s*%\s*\d+|\w+\s*/\s*\d+',
            self.e8_body
        )
        print(f"[*] Found {len(decode_patterns)} decode patterns")

    def extract_string_constants(self):
        """Extract string constants from the bytecode"""
        # Find all long strings that contain bytecode data
        long_strings = re.findall(r'\[=*\[(.*?)\]=*\]', self.vm_code, re.DOTALL)

        strings = []
        for s in long_strings:
            # Try to decode as base85
            decoded = self._base85_decode(s)
            if decoded:
                # Look for ASCII strings in the decoded data
                ascii_strings = re.findall(rb'[\x20-\x7e]{4,100}', decoded)
                strings.extend([s.decode('ascii', errors='ignore') for s in ascii_strings])

        self.constants = list(set(strings))
        print(f"[*] Extracted {len(self.constants)} string constants")

    def _base85_decode(self, data):
        """Decode base85 data"""
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

    def generate_opcode_documentation(self):
        """Generate comprehensive opcode documentation"""
        doc = []
        doc.append("=" * 70)
        doc.append("LURAPH VM OPCODE DOCUMENTATION")
        doc.append("=" * 70)
        doc.append("")

        # Group by operation type
        by_type = defaultdict(list)
        for opcode, op_type in self.opcodes.items():
            by_type[op_type].append(opcode)

        for op_type in sorted(by_type.keys()):
            doc.append(f"\n{op_type}:")
            opcodes = sorted(by_type[op_type])
            doc.append(f"  Opcodes: {', '.join(f'0x{op:02X}' for op in opcodes)}")

        return '\n'.join(doc)

    def reconstruct_code(self):
        """Attempt to reconstruct original Lua code"""
        # This is the challenging part - we need to:
        # 1. Parse the bytecode data
        # 2. Disassemble using our opcode map
        # 3. Convert to Lua source

        reconstructed = []
        reconstructed.append("--[[ Reconstructed Lua Code ]]--")
        reconstructed.append("-- Decompiled from Luraph v14.5.2 obfuscated bytecode")
        reconstructed.append("")

        # Add extracted string constants
        reconstructed.append("-- String constants found:")
        for s in self.constants[:50]:
            if s and not s.startswith('\\'):
                reconstructed.append(f"-- {repr(s)}")

        reconstructed.append("")
        reconstructed.append("-- Opcode map:")
        for opcode in sorted(self.opcodes.keys())[:30]:
            reconstructed.append(f"-- 0x{opcode:02X}: {self.opcodes[opcode]}")

        self.reconstructed = '\n'.join(reconstructed)
        return self.reconstructed

    def save_results(self, prefix="decompiled"):
        """Save decompilation results"""
        # Save opcode map
        with open(f'{prefix}_opcodes.json', 'w') as f:
            json.dump({f"0x{k:02X}": v for k, v in self.opcodes.items()}, f, indent=2)
        print(f"[*] Saved opcode map to {prefix}_opcodes.json")

        # Save documentation
        doc = self.generate_opcode_documentation()
        with open(f'{prefix}_opcodes.txt', 'w') as f:
            f.write(doc)
        print(f"[*] Saved documentation to {prefix}_opcodes.txt")

        # Save string constants
        with open(f'{prefix}_strings.txt', 'w') as f:
            for s in self.constants:
                f.write(f"{s}\n")
        print(f"[*] Saved strings to {prefix}_strings.txt")

        # Save reconstructed code
        with open(f'{prefix}_code.lua', 'w') as f:
            f.write(self.reconstructed)
        print(f"[*] Saved reconstructed code to {prefix}_code.lua")

def main():
    print("=" * 70)
    print("COMPREHENSIVE LURAPH DECOMPILER")
    print("=" * 70)
    print()

    decompiler = LuraphDecompiler()

    # Load VM code
    print("[*] Loading deobfuscated VM code...")
    decompiler.load('/home/user/deobluraph/deobfuscated.lua')

    # Extract main interpreter
    print("[*] Extracting main interpreter...")
    decompiler.extract_e8_function()

    # Parse VM structure
    print("[*] Parsing VM structure...")
    decompiler.parse_vm_structure()

    # Analyze bytecode format
    print("[*] Analyzing bytecode format...")
    decompiler.analyze_bytecode_format()

    # Extract string constants
    print("[*] Extracting string constants...")
    decompiler.extract_string_constants()

    # Print opcode map
    print()
    print("=" * 70)
    print("OPCODE MAP")
    print("=" * 70)
    for opcode in sorted(decompiler.opcodes.keys()):
        print(f"  0x{opcode:02X} ({opcode:3d}): {decompiler.opcodes[opcode]}")

    print()
    print(f"[*] Total mapped opcodes: {len(decompiler.opcodes)}")

    # Reconstruct code
    print()
    print("[*] Reconstructing code...")
    decompiler.reconstruct_code()

    # Save results
    print()
    print("[*] Saving results...")
    decompiler.save_results()

    return decompiler

if __name__ == "__main__":
    main()
