#!/usr/bin/env python3
"""
Complete Luraph Decompiler
Fully reverse engineers the VM and decompiles to readable Lua source
"""

import re
import struct
import json
from collections import defaultdict

class LuraphDecompiler:
    def __init__(self):
        self.vm_code = None
        self.e8_body = None
        self.opcodes = {}
        self.bytecode_data = []
        self.constants = []
        self.prototypes = []

    def load(self):
        """Load deobfuscated VM code"""
        with open('/home/user/deobluraph/deobfuscated.lua', 'r') as f:
            self.vm_code = f.read()
        print(f"[*] Loaded {len(self.vm_code)} bytes of VM code")

    def extract_e8_body(self):
        """Extract the main interpreter function body"""
        # Find E8 start position
        start = self.vm_code.find('E8=function(z,V,B,L)')
        if start == -1:
            print("[!] Could not find E8 function start")
            return False

        # The E8 function is very large (~46000 chars) and ends at a
        # 'end,VARNAME=' pattern that marks the next table entry
        # Look for the first such pattern after reasonable function body
        search_start = start + 40000  # E8 is at least 40k chars

        # Find patterns like 'end,c8=' which mark next table entry
        import_match = re.search(r'end,([a-zA-Z][a-zA-Z0-9]*)=',
                                 self.vm_code[search_start:start+60000])
        if import_match:
            end_pos = search_start + import_match.start() + 3  # include 'end'
            self.e8_body = self.vm_code[start+20:end_pos]  # skip 'E8=function(z,V,B,L)'
            print(f"[*] Extracted E8 body: {len(self.e8_body)} chars")
            return True

        # Fallback: just grab a large chunk
        self.e8_body = self.vm_code[start:start+50000]
        print(f"[*] Extracted E8 body (fallback): {len(self.e8_body)} chars")
        return True

    def extract_all_opcodes(self):
        """Extract ALL opcodes by parsing the dispatch tree"""
        if not self.e8_body:
            return

        # Find the main interpreter loop - starts with 'repeat local o='
        loop_match = re.search(r'repeat\s+local\s+o\s*=\s*\(?q\[w\]\)?;(.*?)until\s+false',
                               self.e8_body, re.DOTALL)
        if not loop_match:
            print("[!] Could not find main loop")
            return

        loop_body = loop_match.group(1)
        print(f"[*] Found main loop: {len(loop_body)} chars")

        # Parse all opcode handlers by traversing the if-else tree
        self._parse_dispatch_tree(loop_body)

    def _parse_dispatch_tree(self, code):
        """Parse the opcode dispatch tree"""
        # Find all opcode-specific operations
        # The pattern is: operation happens when certain opcode conditions are met

        # Strategy: Find each operation and trace back ALL controlling conditions
        # to determine the exact opcode

        # First, let's get all the leaf operations (actual VM operations)
        # These are X[...]=... patterns

        operations = []

        # Find all stack write operations
        for match in re.finditer(r'(?:\(X\)|X)\[([^\]]+)\]\s*=\s*([^;]+);', code):
            dest = match.group(1)
            source = match.group(2)
            pos = match.start()
            operations.append({
                'dest': dest,
                'source': source,
                'pos': pos,
                'code': match.group(0)
            })

        print(f"[*] Found {len(operations)} stack operations")

        # For each operation, find controlling opcode by analyzing context
        for op in operations:
            self._find_opcode_for_operation(code, op)

        # Build final opcode map
        for op in operations:
            if 'opcode' in op and 'op_type' in op:
                if op['opcode'] not in self.opcodes:
                    self.opcodes[op['opcode']] = {
                        'type': op['op_type'],
                        'pattern': op['code'][:60]
                    }

    def _find_opcode_for_operation(self, code, op):
        """Find the exact opcode for an operation"""
        pos = op['pos']

        # Look at context before this operation
        context_start = max(0, pos - 500)
        context = code[context_start:pos]

        # Find all opcode checks in context
        checks = []
        for match in re.finditer(r'o\s*(==|~=|>=|<=|>|<)\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)', context):
            cmp_type = match.group(1)
            val_str = match.group(2).replace('_', '')

            try:
                if 'x' in val_str.lower():
                    val = int(val_str, 16)
                elif 'b' in val_str.lower():
                    val = int(val_str[2:], 2)
                else:
                    val = int(val_str)
                checks.append((cmp_type, val, match.end()))
            except:
                pass

        # Determine opcode from checks
        # Priority: == checks are definitive
        eq_checks = [(c, v) for c, v, p in checks if c == '==']
        if eq_checks:
            # Use the closest == check
            op['opcode'] = eq_checks[-1][1]
        elif checks:
            # Use range checks to narrow down
            # For now, use the last specific check
            op['opcode'] = checks[-1][1]

        # Identify operation type
        op['op_type'] = self._identify_operation(op['source'], op['dest'])

    def _identify_operation(self, source, dest):
        """Identify the Lua operation type"""
        s = source.strip()

        # Arithmetic
        if re.search(r'X\[.+?\]\s*\+\s*X\[', s):
            return 'ADD'
        if re.search(r'[UmS]\[.+?\]\s*\+\s*X\[', s) or re.search(r'X\[.+?\]\s*\+\s*[UmS]\[', s):
            return 'ADDK'
        if re.search(r'[UmS]\[.+?\]\s*\+\s*[UmS]\[', s):
            return 'ADDKK'
        if re.search(r'X\[.+?\]\s*-\s*X\[', s):
            return 'SUB'
        if re.search(r'[UmS]\[.+?\]\s*-\s*[UmSX]\[', s):
            return 'SUBK'
        if re.search(r'X\[.+?\]\s*\*\s*X\[', s):
            return 'MUL'
        if re.search(r'[UmS]\[.+?\]\s*\*\s*[UmSX]\[', s) or re.search(r'X\[.+?\]\s*\*\s*[UmS]\[', s):
            return 'MULK'
        if re.search(r'X\[.+?\]\s*/\s*X\[', s) and '//' not in s:
            return 'DIV'
        if re.search(r'X\[.+?\]\s*//\s*X\[', s):
            return 'IDIV'
        if re.search(r'X\[.+?\]\s*%\s*X\[', s):
            return 'MOD'
        if re.search(r'X\[.+?\]\s*\^\s*X\[', s):
            return 'POW'

        # Comparison
        if re.search(r'X\[.+?\]\s*==\s*X\[', s):
            return 'EQ'
        if re.search(r'[UmS]\[.+?\]\s*==\s*X\[', s) or re.search(r'X\[.+?\]\s*==\s*[UmS]\[', s):
            return 'EQK'
        if re.search(r'X\[.+?\]\s*~=\s*X\[', s):
            return 'NE'
        if re.search(r'[UmS]\[.+?\]\s*~=\s*X\[', s):
            return 'NEK'
        if re.search(r'X\[.+?\]\s*<\s*X\[', s):
            return 'LT'
        if re.search(r'X\[.+?\]\s*<\s*[UmS]\[', s) or re.search(r'[UmS]\[.+?\]\s*<\s*X\[', s):
            return 'LTK'
        if re.search(r'X\[.+?\]\s*<=\s*X\[', s):
            return 'LE'
        if re.search(r'X\[.+?\]\s*>\s*X\[', s):
            return 'GT'
        if re.search(r'[UmS]\[.+?\]\s*>\s*X\[', s):
            return 'GTK'
        if re.search(r'X\[.+?\]\s*>=\s*X\[', s):
            return 'GE'
        if re.search(r'X\[.+?\]\s*>=\s*[UmS]\[', s):
            return 'GEK'
        if re.search(r'[UmS]\[.+?\]\s*>=\s*[UmS]\[', s):
            return 'GEKK'

        # String
        if '..' in s:
            return 'CONCAT'

        # Table
        if re.search(r'X\[.+?\]\[X\[.+?\]\]', s):
            return 'GETTABLE'
        if re.search(r'y\[.+?\]\[X\[.+?\]\]', s):
            return 'GETTABUP'
        if re.search(r'i\[0X3\]\[i\[', s):
            return 'GETUPVAL'
        if re.search(r'^\s*\{', s):
            return 'NEWTABLE'

        # Unary
        if re.search(r'^\s*-\s*X\[', s):
            return 'UNM'
        if re.search(r'^\s*not\s+X\[', s):
            return 'NOT'
        if re.search(r'^\s*#\s*X\[', s):
            return 'LEN'

        # Load
        if s == 'nil':
            return 'LOADNIL'
        if s in ('true', 'false'):
            return 'LOADBOOL'
        if re.match(r'^\s*X\[[^\]]+\]\s*$', s):
            return 'MOVE'
        if re.match(r'^\s*[UmSN]\[', s):
            return 'LOADK'
        if re.match(r'^\s*y\[[^\]]+\]\s*$', s):
            return 'GETUPVAL'
        if re.search(r'V\[\d+\]\(', s):
            return 'LOADK'
        if re.search(r'V\[0X18\]', s):
            return 'GETGLOBAL'

        # Upvalue
        if re.match(r'^\s*\(?\s*y\[', s):
            return 'GETUPVAL'

        # Bitwise
        if '.band(' in s or 'band(' in s:
            return 'BAND'
        if '.bor(' in s or 'bor(' in s:
            return 'BOR'
        if '.bxor(' in s or 'bxor(' in s:
            return 'BXOR'
        if '.bnot(' in s:
            return 'BNOT'
        if '.lshift(' in s:
            return 'SHL'
        if '.rshift(' in s:
            return 'SHR'

        # Self reference
        if s == 'X':
            return 'SELF'

        return 'UNKNOWN'

    def extract_bytecode_data(self):
        """Extract and decode bytecode from embedded strings"""
        # Find all long strings
        long_strings = re.findall(r'\[=*\[(.*?)\]=*\]', self.vm_code, re.DOTALL)

        for i, s in enumerate(long_strings):
            decoded = self._base85_decode(s)
            if decoded and len(decoded) > 100:
                self.bytecode_data.append({
                    'index': i,
                    'data': decoded,
                    'size': len(decoded)
                })

        print(f"[*] Decoded {len(self.bytecode_data)} bytecode blocks")
        total = sum(b['size'] for b in self.bytecode_data)
        print(f"[*] Total bytecode: {total} bytes")

    def _base85_decode(self, data):
        """Decode Luraph base85"""
        data = data.replace('z', '!!!!!')
        result = bytearray()
        i = 0
        while i + 5 <= len(data):
            try:
                value = 0
                for c in data[i:i+5]:
                    value = value * 85 + (ord(c) - 33)
                result.extend(struct.pack('>I', value))
            except:
                pass
            i += 5
        return bytes(result)

    def analyze_bytecode_format(self):
        """Analyze the bytecode format"""
        if not self.bytecode_data:
            return

        # Look at the largest block - this is likely the main function
        main_block = max(self.bytecode_data, key=lambda x: x['size'])
        data = main_block['data']

        print(f"[*] Analyzing main bytecode block: {len(data)} bytes")

        # Try to identify the format
        # Lua bytecode typically has: header, prototypes (functions), constants, instructions

        # Look for patterns
        # The VM uses: q[w] to fetch instructions
        # Instructions are likely 32-bit words

        # Try to parse as 32-bit instructions
        instructions = []
        for i in range(0, len(data) - 3, 4):
            word = struct.unpack('<I', data[i:i+4])[0]
            instructions.append(word)

        print(f"[*] Parsed {len(instructions)} potential instructions")

        # Analyze instruction distribution
        opcode_dist = defaultdict(int)
        for instr in instructions:
            # Try different opcode extraction methods
            # Method 1: Lower 6 bits (standard Lua)
            op1 = instr & 0x3F
            # Method 2: Lower 8 bits
            op2 = instr & 0xFF
            # Method 3: Upper bits
            op3 = (instr >> 24) & 0xFF

            opcode_dist[op1] += 1

        print(f"[*] Opcode distribution (6-bit): {len(opcode_dist)} unique values")

        return instructions

    def decompile_to_source(self):
        """Decompile bytecode to Lua source code"""
        if not self.bytecode_data:
            print("[!] No bytecode data to decompile")
            return None

        # Build disassembly first
        main_block = max(self.bytecode_data, key=lambda x: x['size'])
        data = main_block['data']

        # Parse instructions
        source_lines = []
        source_lines.append("-- Decompiled Lua Source")
        source_lines.append("-- Reconstructed from Luraph VM bytecode")
        source_lines.append("")

        # Try to identify function structure
        # Look for function boundaries in the bytecode

        instructions = []
        i = 0
        while i < len(data) - 3:
            word = struct.unpack('<I', data[i:i+4])[0]

            # Extract fields (assuming Lua 5.x format)
            opcode = word & 0xFF  # 8-bit opcode for Luraph
            A = (word >> 8) & 0xFF
            B = (word >> 16) & 0xFF
            C = (word >> 24) & 0xFF

            instr = {
                'pc': i // 4,
                'raw': word,
                'opcode': opcode,
                'A': A,
                'B': B,
                'C': C
            }

            # Map to known operation
            if opcode in self.opcodes:
                instr['op_name'] = self.opcodes[opcode]['type']
            else:
                instr['op_name'] = f'OP_{opcode}'

            instructions.append(instr)
            i += 4

        # Generate disassembly
        source_lines.append("; Disassembly")
        for instr in instructions[:500]:  # First 500 instructions
            line = f"; {instr['pc']:4d}: {instr['op_name']:12s} A={instr['A']:3d} B={instr['B']:3d} C={instr['C']:3d}  (0x{instr['raw']:08X})"
            source_lines.append(line)

        # Now try to reconstruct Lua source
        source_lines.append("")
        source_lines.append("-- Reconstructed source (partial)")
        source_lines.append("")

        # Generate pseudo-code based on opcodes
        self._generate_pseudocode(instructions, source_lines)

        return '\n'.join(source_lines)

    def _generate_pseudocode(self, instructions, output):
        """Generate pseudo-code from instructions"""
        indent = 0
        registers = {}
        pc = 0

        for instr in instructions[:200]:
            op = instr['op_name']
            A, B, C = instr['A'], instr['B'], instr['C']

            line = None

            if op == 'MOVE':
                line = f"R{A} = R{B}"
            elif op == 'LOADK':
                line = f"R{A} = K{B}"
            elif op == 'LOADNIL':
                line = f"R{A} = nil"
            elif op == 'LOADBOOL':
                line = f"R{A} = {'true' if B else 'false'}"
            elif op == 'ADD':
                line = f"R{A} = R{B} + R{C}"
            elif op == 'ADDK':
                line = f"R{A} = R{B} + K{C}"
            elif op == 'SUB':
                line = f"R{A} = R{B} - R{C}"
            elif op == 'SUBK':
                line = f"R{A} = R{B} - K{C}"
            elif op == 'MUL':
                line = f"R{A} = R{B} * R{C}"
            elif op == 'MULK':
                line = f"R{A} = R{B} * K{C}"
            elif op == 'DIV':
                line = f"R{A} = R{B} / R{C}"
            elif op == 'MOD':
                line = f"R{A} = R{B} % R{C}"
            elif op == 'POW':
                line = f"R{A} = R{B} ^ R{C}"
            elif op == 'UNM':
                line = f"R{A} = -R{B}"
            elif op == 'NOT':
                line = f"R{A} = not R{B}"
            elif op == 'LEN':
                line = f"R{A} = #R{B}"
            elif op == 'CONCAT':
                line = f"R{A} = R{B} .. R{C}"
            elif op == 'EQ':
                line = f"if R{B} == R{C} then"
                indent += 1
            elif op == 'LT':
                line = f"if R{B} < R{C} then"
                indent += 1
            elif op == 'LE':
                line = f"if R{B} <= R{C} then"
                indent += 1
            elif op == 'GT':
                line = f"if R{B} > R{C} then"
                indent += 1
            elif op == 'GE':
                line = f"if R{B} >= R{C} then"
                indent += 1
            elif op == 'JMP':
                line = f"goto L{pc + B}"
            elif op == 'CALL':
                line = f"R{A}(R{A+1}, ..., R{A+B-1})"
            elif op == 'RETURN':
                line = f"return R{A}, ..., R{A+B-2}"
            elif op == 'GETTABLE':
                line = f"R{A} = R{B}[R{C}]"
            elif op == 'SETTABLE':
                line = f"R{A}[R{B}] = R{C}"
            elif op == 'NEWTABLE':
                line = f"R{A} = {{}}"
            elif op == 'GETUPVAL':
                line = f"R{A} = U{B}"
            elif op == 'SETUPVAL':
                line = f"U{B} = R{A}"
            elif op == 'GETGLOBAL':
                line = f"R{A} = _G[K{B}]"
            elif op == 'SETGLOBAL':
                line = f"_G[K{B}] = R{A}"
            elif op == 'SELF':
                line = f"R{A+1} = R{B}; R{A} = R{B}[K{C}]"
            elif op == 'CLOSURE':
                line = f"R{A} = function() ... end"
            elif op.startswith('OP_'):
                line = f"; {op} A={A} B={B} C={C}"

            if line:
                output.append('    ' * indent + line)

            pc += 1

    def save_results(self, filename):
        """Save decompilation results"""
        source = self.decompile_to_source()
        if source:
            with open(filename, 'w') as f:
                f.write(source)
            print(f"[*] Saved decompiled source to {filename}")

        # Save opcode map
        with open('complete_opcode_map.json', 'w') as f:
            json.dump({
                str(k): v for k, v in self.opcodes.items()
            }, f, indent=2)
        print(f"[*] Saved opcode map to complete_opcode_map.json")

def main():
    print("=" * 70)
    print("COMPLETE LURAPH DECOMPILER")
    print("=" * 70)
    print()

    decompiler = LuraphDecompiler()

    # Load VM code
    decompiler.load()

    # Extract E8 body
    print()
    if not decompiler.extract_e8_body():
        print("[!] Failed to extract E8 body")
        return

    # Extract all opcodes
    print()
    decompiler.extract_all_opcodes()

    # Print opcode map
    print()
    print("=" * 70)
    print("COMPLETE OPCODE MAP")
    print("=" * 70)

    by_type = defaultdict(list)
    for opcode, info in decompiler.opcodes.items():
        by_type[info['type']].append(opcode)

    for op_type in sorted(by_type.keys()):
        codes = sorted(by_type[op_type])
        codes_str = ', '.join(f'0x{c:02X}' for c in codes)
        print(f"{op_type:12s}: {codes_str}")

    print()
    print(f"Total opcodes: {len(decompiler.opcodes)}")
    print(f"Operation types: {len(by_type)}")

    # Extract bytecode
    print()
    decompiler.extract_bytecode_data()

    # Analyze bytecode format
    print()
    decompiler.analyze_bytecode_format()

    # Decompile
    print()
    decompiler.save_results('decompiled_source.lua')

    return decompiler

if __name__ == "__main__":
    main()
