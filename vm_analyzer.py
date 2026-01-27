#!/usr/bin/env python3
"""
Luraph VM Analyzer - Maps all opcodes and generates readable decompiled output
"""

import re
import struct
from collections import defaultdict

class LuraphVMAnalyzer:
    def __init__(self):
        self.vm_code = None
        self.e8_body = None
        self.opcodes = {}
        self.bytecode_blocks = []

        # VM variable meanings (from analysis):
        # q = instruction array
        # w = program counter
        # o = current opcode
        # X = registers (stack)
        # y = upvalues
        # U, m, S = different constant arrays
        # N[w], d[w], _[w] = instruction operands A, B, C
        # H = open upvalues for closure
        # i = intermediate/return value
        # h = comparison flag
        # V = main VM state table

    def load(self, filepath='/home/user/deobluraph/deobfuscated.lua'):
        with open(filepath, 'r') as f:
            self.vm_code = f.read()
        print(f"[*] Loaded {len(self.vm_code)} bytes")

    def extract_interpreter(self):
        """Extract the main interpreter loop"""
        start = self.vm_code.find('E8=function(z,V,B,L)')
        if start == -1:
            return False

        # Find end of E8
        search_start = start + 40000
        match = re.search(r'end,([a-zA-Z][a-zA-Z0-9]*)=',
                          self.vm_code[search_start:start+60000])
        if match:
            end_pos = search_start + match.start() + 3
            self.e8_body = self.vm_code[start:end_pos]
        else:
            self.e8_body = self.vm_code[start:start+50000]

        print(f"[*] Extracted interpreter: {len(self.e8_body)} chars")
        return True

    def analyze_opcode_tree(self):
        """Parse the opcode dispatch tree and map handlers"""
        # Find the main loop
        loop_match = re.search(r'repeat\s+local\s+o\s*=\s*\(?q\[w\]\)?;?(.*?)until\s+false',
                               self.e8_body, re.DOTALL)
        if not loop_match:
            print("[!] Could not find main loop")
            return

        loop_body = loop_match.group(1)
        print(f"[*] Main loop: {len(loop_body)} chars")

        # Extract all operations with their controlling conditions
        self._parse_dispatch_recursive(loop_body, [], 0)

        print(f"[*] Mapped {len(self.opcodes)} opcodes")

    def _parse_dispatch_recursive(self, code, conditions, depth):
        """Recursively parse if-else tree to find opcode handlers"""
        if depth > 50:  # Prevent infinite recursion
            return

        # Find if/elseif/else patterns
        # Pattern: if COND then CODE else CODE end
        # or: if COND then CODE end

        # Try to find operations at this level
        # Operations are like: X[...]=...; or (X)[...]=...;
        op_pattern = r'(?:\(X\)|X)\[([^\]]+)\]\s*=\s*([^;]+);'

        pos = 0
        while pos < len(code):
            # Look for conditional branches
            if_match = re.match(r'\s*if\s+(o[<>=~!]+[^t]+)\s*then\s*', code[pos:])
            elseif_match = re.match(r'\s*else\s*if\s+(o[<>=~!]+[^t]+)\s*then\s*', code[pos:])
            else_match = re.match(r'\s*else\s*', code[pos:])

            if if_match:
                cond = if_match.group(1).strip()
                new_conditions = conditions + [cond]
                pos += if_match.end()

                # Find the then block
                block, block_end = self._find_block(code[pos:])
                if block:
                    self._parse_dispatch_recursive(block, new_conditions, depth + 1)
                    pos += block_end

            elif elseif_match:
                cond = elseif_match.group(1).strip()
                new_conditions = conditions[:-1] + [f"not ({conditions[-1]})", cond] if conditions else [cond]
                pos += elseif_match.end()

                block, block_end = self._find_block(code[pos:])
                if block:
                    self._parse_dispatch_recursive(block, new_conditions, depth + 1)
                    pos += block_end

            elif else_match:
                pos += else_match.end()
                # Continue with inverted conditions

            else:
                # Look for operations at this level
                op_match = re.match(op_pattern, code[pos:])
                if op_match:
                    dest = op_match.group(1)
                    source = op_match.group(2)
                    self._record_operation(conditions, dest, source)
                    pos += op_match.end()
                else:
                    pos += 1

    def _find_block(self, code):
        """Find the extent of a then/else block"""
        depth = 1
        pos = 0
        start = 0

        while pos < len(code) and depth > 0:
            # Look for nested if/end
            if code[pos:pos+2] == 'if':
                depth += 1
            elif code[pos:pos+3] == 'end':
                depth -= 1
                if depth == 0:
                    return code[start:pos], pos + 3
            elif code[pos:pos+4] == 'else' and depth == 1:
                return code[start:pos], pos
            pos += 1

        return code[start:pos], pos

    def _record_operation(self, conditions, dest, source):
        """Record an operation with its controlling conditions"""
        # Try to determine exact opcode from conditions
        opcode = self._extract_opcode_from_conditions(conditions)
        if opcode is not None:
            op_type = self._identify_operation(source, dest)
            if opcode not in self.opcodes:
                self.opcodes[opcode] = {
                    'type': op_type,
                    'dest': dest[:30],
                    'source': source[:50],
                    'conditions': conditions[-2:] if len(conditions) > 2 else conditions
                }

    def _extract_opcode_from_conditions(self, conditions):
        """Extract exact opcode value from condition list"""
        eq_check = None
        ranges = []

        for cond in conditions:
            # Look for o==VALUE
            match = re.search(r'o\s*==\s*(0[xXbB][0-9a-fA-F_]+|\d+)', cond)
            if match:
                return self._parse_number(match.group(1))

            # Look for range checks
            match = re.search(r'o\s*(>=|<=|>|<|~=)\s*(0[xXbB][0-9a-fA-F_]+|\d+)', cond)
            if match:
                op, val = match.group(1), self._parse_number(match.group(2))
                ranges.append((op, val))

        # Try to narrow down from ranges
        min_val, max_val = 0, 255
        for op, val in ranges:
            if op == '>=':
                min_val = max(min_val, val)
            elif op == '>':
                min_val = max(min_val, val + 1)
            elif op == '<=':
                max_val = min(max_val, val)
            elif op == '<':
                max_val = min(max_val, val - 1)

        if min_val == max_val:
            return min_val

        return None

    def _parse_number(self, s):
        s = s.replace('_', '')
        if s.startswith('0x') or s.startswith('0X'):
            return int(s, 16)
        elif s.startswith('0b') or s.startswith('0B'):
            return int(s[2:], 2)
        else:
            return int(s)

    def _identify_operation(self, source, dest):
        """Identify Lua operation type from source expression"""
        s = source.strip()

        # Arithmetic
        if re.search(r'X\[.+?\]\s*\+\s*X\[', s): return 'ADD'
        if re.search(r'[UmS]\[.+?\]\s*\+', s) or re.search(r'\+\s*[UmS]\[', s): return 'ADDK'
        if re.search(r'X\[.+?\]\s*-\s*X\[', s): return 'SUB'
        if re.search(r'[UmS]\[.+?\]\s*-', s) or re.search(r'-\s*[UmS]\[', s): return 'SUBK'
        if re.search(r'X\[.+?\]\s*\*\s*X\[', s): return 'MUL'
        if re.search(r'[UmS]\[.+?\]\s*\*', s) or re.search(r'\*\s*[UmS]\[', s): return 'MULK'
        if re.search(r'X\[.+?\]\s*//\s*X\[', s): return 'IDIV'
        if re.search(r'X\[.+?\]\s*/\s*X\[', s): return 'DIV'
        if re.search(r'X\[.+?\]\s*%\s*X\[', s): return 'MOD'
        if re.search(r'X\[.+?\]\s*%\s*[mUS]\[', s): return 'MODK'
        if re.search(r'X\[.+?\]\s*\^\s*X\[', s): return 'POW'

        # Comparison (results to register)
        if re.search(r'X\[.+?\]\s*==\s*X\[', s): return 'EQ'
        if re.search(r'[UmS]\[.+?\]\s*==\s*[UmS]\[', s): return 'EQKK'
        if re.search(r'X\[.+?\]\s*~=\s*X\[', s): return 'NE'
        if re.search(r'X\[.+?\]\s*~=\s*[UmS]\[', s): return 'NEK'
        if re.search(r'X\[.+?\]\s*<\s*X\[', s): return 'LT'
        if re.search(r'X\[.+?\]\s*<=\s*X\[', s): return 'LE'
        if re.search(r'X\[.+?\]\s*>\s*X\[', s): return 'GT'
        if re.search(r'X\[.+?\]\s*>=\s*X\[', s): return 'GE'
        if re.search(r'[mUS]\[.+?\]\s*<\s*X\[', s): return 'LTK'
        if re.search(r'[mUS]\[.+?\]\s*<=\s*X\[', s): return 'LEK'

        # Table operations
        if re.search(r'X\[.+?\]\[X\[.+?\]\]', s): return 'GETTABLE'
        if re.search(r'X\[.+?\]\[[UmS]\[.+?\]\]', s): return 'GETTABLEK'
        if re.search(r'y\[.+?\]\[X\[.+?\]\]', s): return 'GETTABUP'
        if re.search(r'y\[.+?\]\[[UmS]\[.+?\]\]', s): return 'GETTABUPK'
        if re.search(r'^\s*\{', s): return 'NEWTABLE'

        # String
        if '..' in s: return 'CONCAT'

        # Unary
        if re.search(r'^\s*-\s*X\[', s): return 'UNM'
        if re.search(r'^\s*-\s*[UmS]\[', s): return 'UNMK'
        if re.search(r'^\s*not\s+X\[', s): return 'NOT'
        if re.search(r'^\s*#\s*X\[', s): return 'LEN'

        # Load operations
        if s == 'nil': return 'LOADNIL'
        if s in ('true', 'false'): return 'LOADBOOL'
        if re.match(r'^\s*X\[[^\]]+\]\s*$', s): return 'MOVE'
        if re.match(r'^\s*[UmSN]\[', s): return 'LOADK'
        if re.match(r'^\s*y\[', s): return 'GETUPVAL'

        # Bitwise
        if 'band(' in s or '.band(' in s: return 'BAND'
        if 'bor(' in s or '.bor(' in s: return 'BOR'
        if 'bxor(' in s or '.bxor(' in s: return 'BXOR'
        if 'bnot(' in s: return 'BNOT'
        if 'lshift(' in s: return 'SHL'
        if 'rshift(' in s: return 'SHR'

        return 'UNKNOWN'

    def extract_bytecode(self):
        """Extract embedded bytecode blocks"""
        # Find all long string literals
        for match in re.finditer(r'\[=*\[(.*?)\]=*\]', self.vm_code, re.DOTALL):
            data = self._base85_decode(match.group(1))
            if data and len(data) > 100:
                self.bytecode_blocks.append({
                    'raw': match.group(1)[:50],
                    'data': data,
                    'size': len(data)
                })

        print(f"[*] Found {len(self.bytecode_blocks)} bytecode blocks")
        total = sum(b['size'] for b in self.bytecode_blocks)
        print(f"[*] Total bytecode: {total} bytes")

    def _base85_decode(self, data):
        """Decode Luraph's base85 encoding"""
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

    def analyze_opcodes_from_patterns(self):
        """Extract opcodes by finding specific patterns in the code"""
        # Find all explicit opcode handlers (o==VALUE then ACTION)
        loop_start = self.vm_code.find('repeat local o=(q[w])')
        if loop_start == -1:
            loop_start = self.vm_code.find('repeat local o=')

        loop_body = self.vm_code[loop_start:loop_start+45000]

        # Pattern 1: o==VALUE then (X)[dest]=source;
        for m in re.finditer(r'o(?:==|~=)(0[xXbB][0-9a-fA-F_]+|\d+)\s*then\s*(?:\(X\)|X)\[([^\]]+)\]\s*=\s*([^;]+);', loop_body):
            val = self._parse_number(m.group(1))
            dest = m.group(2)
            source = m.group(3)
            op_type = self._identify_operation(source, dest)
            if val not in self.opcodes:
                self.opcodes[val] = {
                    'type': op_type,
                    'dest': dest[:30],
                    'source': source[:50]
                }

        # Pattern 2: o==VALUE then return/jump operations
        for m in re.finditer(r'o==\s*(0[xXbB][0-9a-fA-F_]+|\d+)\s*then\s*([^;]+return[^;]+);', loop_body):
            val = self._parse_number(m.group(1))
            if val not in self.opcodes:
                self.opcodes[val] = {
                    'type': 'RETURN',
                    'action': m.group(2)[:50]
                }

        # Pattern 3: Branch comparisons affecting w (PC)
        for m in re.finditer(r'o==\s*(0[xXbB][0-9a-fA-F_]+|\d+)\s*then[^;]*w\s*=\s*([^;]+);', loop_body):
            val = self._parse_number(m.group(1))
            if val not in self.opcodes:
                self.opcodes[val] = {
                    'type': 'JMP',
                    'target': m.group(2)[:50]
                }

        print(f"[*] Pattern analysis found {len(self.opcodes)} opcodes")

    def direct_opcode_scan(self):
        """Direct scan for all operation patterns"""
        loop_start = self.vm_code.find('repeat local o=(q[w])')
        if loop_start == -1:
            loop_start = self.vm_code.find('repeat local o=')
        loop_body = self.vm_code[loop_start:loop_start+45000]

        # Find all (X)[...]=... patterns and their context
        operations = []
        for m in re.finditer(r'(?:\(X\)|X)\[([^\]]+)\]=([^;]+);', loop_body):
            pos = m.start()
            # Look back for opcode checks
            context = loop_body[max(0,pos-200):pos]
            dest = m.group(1)
            source = m.group(2)

            # Find closest opcode check
            checks = list(re.finditer(r'o(==|~=|>=|<=|>|<)(0[xXbB][0-9a-fA-F_]+|\d+)', context))
            if checks:
                last_check = checks[-1]
                cmp_op = last_check.group(1)
                val = self._parse_number(last_check.group(2))
                if cmp_op == '==' and val not in self.opcodes:
                    op_type = self._identify_operation(source, dest)
                    self.opcodes[val] = {
                        'type': op_type,
                        'dest': dest[:30],
                        'source': source[:50]
                    }

        print(f"[*] Direct scan found {len(self.opcodes)} total opcodes")

    def generate_opcode_map(self):
        """Generate a complete opcode map"""
        by_type = defaultdict(list)
        for opcode, info in self.opcodes.items():
            by_type[info['type']].append(opcode)

        print("\n" + "="*70)
        print("COMPLETE OPCODE MAP")
        print("="*70)

        for op_type in sorted(by_type.keys()):
            codes = sorted(by_type[op_type])
            codes_str = ', '.join(f'0x{c:02X}' for c in codes)
            print(f"{op_type:12s}: {codes_str}")

        print(f"\nTotal: {len(self.opcodes)} opcodes, {len(by_type)} types")
        return by_type

    def disassemble_bytecode(self):
        """Disassemble the largest bytecode block"""
        if not self.bytecode_blocks:
            return []

        # Use largest block (main function)
        main_block = max(self.bytecode_blocks, key=lambda x: x['size'])
        data = main_block['data']

        print(f"\n[*] Disassembling {len(data)} bytes of bytecode")

        instructions = []
        i = 0
        while i < len(data) - 3:
            word = struct.unpack('<I', data[i:i+4])[0]

            # Luraph uses 8-bit opcodes
            opcode = word & 0xFF
            A = (word >> 8) & 0xFF
            B = (word >> 16) & 0xFF
            C = (word >> 24) & 0xFF

            # Alternative format: 6-bit opcode (standard Lua)
            opcode6 = word & 0x3F
            A6 = (word >> 6) & 0xFF

            op_name = self.opcodes.get(opcode, {}).get('type', f'OP_{opcode}')

            instructions.append({
                'pc': i // 4,
                'raw': word,
                'opcode': opcode,
                'op_name': op_name,
                'A': A,
                'B': B,
                'C': C
            })
            i += 4

        return instructions

    def generate_output(self, output_file):
        """Generate final decompiled output"""
        instructions = self.disassemble_bytecode()

        lines = []
        lines.append("--" + "="*68)
        lines.append("-- LURAPH DECOMPILED OUTPUT")
        lines.append("-- Deobfuscated from Luraph v14.5.2 protected script")
        lines.append("--" + "="*68)
        lines.append("")

        # Opcode map
        lines.append("--[[ OPCODE MAP")
        by_type = defaultdict(list)
        for opcode, info in self.opcodes.items():
            by_type[info['type']].append(opcode)
        for op_type in sorted(by_type.keys()):
            codes = sorted(by_type[op_type])
            codes_str = ', '.join(f'0x{c:02X}' for c in codes)
            lines.append(f"  {op_type:12s}: {codes_str}")
        lines.append("]]")
        lines.append("")

        # Disassembly
        lines.append("--[[ DISASSEMBLY")
        for instr in instructions[:1000]:
            line = f"  {instr['pc']:4d}: {instr['op_name']:12s} A={instr['A']:3d} B={instr['B']:3d} C={instr['C']:3d}  ; 0x{instr['raw']:08X}"
            lines.append(line)
        if len(instructions) > 1000:
            lines.append(f"  ... ({len(instructions) - 1000} more instructions)")
        lines.append("]]")
        lines.append("")

        # Pseudo-code reconstruction
        lines.append("-- RECONSTRUCTED SOURCE (partial)")
        lines.append("")
        self._generate_source(instructions[:500], lines)

        with open(output_file, 'w') as f:
            f.write('\n'.join(lines))

        print(f"[*] Saved output to {output_file}")
        return lines

    def _generate_source(self, instructions, output):
        """Generate pseudo-source from instructions"""
        indent = 0

        for instr in instructions:
            op = instr['op_name']
            A, B, C = instr['A'], instr['B'], instr['C']
            pc = instr['pc']

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
            elif op == 'DIV':
                line = f"R{A} = R{B} / R{C}"
            elif op == 'MOD':
                line = f"R{A} = R{B} % R{C}"
            elif op == 'MODK':
                line = f"R{A} = R{B} % K{C}"
            elif op == 'POW':
                line = f"R{A} = R{B} ^ R{C}"
            elif op == 'UNM':
                line = f"R{A} = -R{B}"
            elif op == 'NOT':
                line = f"R{A} = not R{B}"
            elif op == 'LEN':
                line = f"R{A} = #R{B}"
            elif op == 'CONCAT':
                line = f"R{A} = R{B} .. ... .. R{C}"
            elif op in ('EQ', 'NE', 'LT', 'LE', 'GT', 'GE'):
                ops = {'EQ': '==', 'NE': '~=', 'LT': '<', 'LE': '<=', 'GT': '>', 'GE': '>='}
                line = f"if R{B} {ops[op]} R{C} then  -- jump"
            elif op == 'JMP':
                line = f"goto L{pc + B + 1}"
            elif op == 'GETTABLE':
                line = f"R{A} = R{B}[R{C}]"
            elif op == 'GETTABLEK':
                line = f"R{A} = R{B}[K{C}]"
            elif op == 'SETTABLE':
                line = f"R{A}[R{B}] = R{C}"
            elif op == 'NEWTABLE':
                line = f"R{A} = {{}}"
            elif op == 'GETUPVAL':
                line = f"R{A} = U{B}"
            elif op == 'SETUPVAL':
                line = f"U{B} = R{A}"
            elif op == 'GETTABUP':
                line = f"R{A} = U{B}[R{C}]"
            elif op == 'GETTABUPK':
                line = f"R{A} = U{B}[K{C}]"
            elif op == 'RETURN':
                line = f"return R{A}, ..., R{A+B-2}"
            elif op.startswith('OP_'):
                line = f"-- {op} A={A} B={B} C={C}"
            else:
                line = f"-- {op} A={A} B={B} C={C}"

            if line:
                output.append('  ' * indent + line)


def main():
    print("="*70)
    print("LURAPH VM ANALYZER")
    print("="*70)

    analyzer = LuraphVMAnalyzer()
    analyzer.load()
    analyzer.extract_interpreter()

    # Multiple analysis passes
    analyzer.analyze_opcodes_from_patterns()
    analyzer.direct_opcode_scan()

    # Show results
    analyzer.generate_opcode_map()

    # Extract and analyze bytecode
    analyzer.extract_bytecode()

    # Generate output
    analyzer.generate_output('/home/user/deobluraph/decompiled_output.lua')

    return analyzer


if __name__ == "__main__":
    main()
