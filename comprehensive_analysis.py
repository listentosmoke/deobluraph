#!/usr/bin/env python3
"""
Comprehensive Luraph Analysis
Extracts and documents all bytecode and VM structure
"""

import re
import struct
import json
from collections import defaultdict

class LuraphAnalyzer:
    def __init__(self):
        self.vm_code = None
        self.bytecode_blocks = []
        self.vm_handlers = {}
        self.opcodes = {}
        self.constants = []

    def load(self, path='deobfuscated.lua'):
        with open(path, 'r', errors='ignore') as f:
            self.vm_code = f.read()
        print(f"[*] Loaded {len(self.vm_code)} bytes")

    def base85_decode(self, data):
        """Decode Luraph base85"""
        data = data.replace('z', '!!!!!')
        result = bytearray()
        i = 0
        while i + 5 <= len(data):
            try:
                value = 0
                valid = True
                for c in data[i:i+5]:
                    code = ord(c) - 33
                    if code < 0 or code >= 85:
                        valid = False
                        break
                    value = value * 85 + code
                if valid and value <= 0xFFFFFFFF:
                    result.extend(struct.pack('>I', value))
            except:
                pass
            i += 5
        return bytes(result)

    def extract_bytecode(self):
        """Extract all bytecode blocks"""
        for m in re.finditer(r'\[=+\[(.*?)\]=+\]', self.vm_code, re.DOTALL):
            raw = m.group(1)
            if len(raw) < 50:
                continue
            decoded = self.base85_decode(raw)
            if len(decoded) > 50:
                self.bytecode_blocks.append({
                    'raw': raw,
                    'decoded': decoded,
                    'size': len(decoded)
                })

        self.bytecode_blocks.sort(key=lambda x: x['size'], reverse=True)
        print(f"[*] Found {len(self.bytecode_blocks)} bytecode blocks")
        print(f"[*] Total decoded: {sum(b['size'] for b in self.bytecode_blocks)} bytes")

    def analyze_vm_structure(self):
        """Analyze VM table structure"""
        # Find function definitions
        for m in re.finditer(r'(\w+)=function\(([^)]*)\)', self.vm_code[:100000]):
            name = m.group(1)
            args = m.group(2)
            self.vm_handlers[name] = {'args': args, 'pos': m.start()}

        print(f"[*] Found {len(self.vm_handlers)} VM handlers")

        # Find E8 (main interpreter)
        e8_start = self.vm_code.find('E8=function')
        if e8_start >= 0:
            print("[*] Found E8 interpreter function")

    def extract_opcodes(self):
        """Extract opcode mappings from E8"""
        e8_start = self.vm_code.find('E8=function')
        if e8_start < 0:
            return

        e8_body = self.vm_code[e8_start:e8_start+50000]

        # Find o== patterns (exact opcode matches)
        for m in re.finditer(r'o==(0[xXbB][0-9a-fA-F_]+|\d+)', e8_body):
            val_str = m.group(1).replace('_', '')
            if val_str.startswith('0x') or val_str.startswith('0X'):
                opcode = int(val_str, 16)
            elif val_str.startswith('0b') or val_str.startswith('0B'):
                opcode = int(val_str[2:], 2)
            else:
                opcode = int(val_str)

            # Get context after the check
            ctx_start = m.end()
            ctx = e8_body[ctx_start:ctx_start+100]

            # Identify operation type
            op_type = self._identify_op(ctx)
            if opcode not in self.opcodes:
                self.opcodes[opcode] = {'type': op_type, 'context': ctx[:50]}

        print(f"[*] Mapped {len(self.opcodes)} opcodes")

    def _identify_op(self, ctx):
        """Identify operation type from context"""
        if re.search(r'X\[.+?\]\s*\+\s*X\[', ctx): return 'ADD'
        if re.search(r'X\[.+?\]\s*-\s*X\[', ctx): return 'SUB'
        if re.search(r'X\[.+?\]\s*\*\s*X\[', ctx): return 'MUL'
        if re.search(r'X\[.+?\]\s*/\s*X\[', ctx): return 'DIV'
        if re.search(r'X\[.+?\]\s*%\s*X\[', ctx): return 'MOD'
        if re.search(r'X\[.+?\]\s*\^\s*X\[', ctx): return 'POW'
        if re.search(r'X\[.+?\]\s*==\s*X\[', ctx): return 'EQ'
        if re.search(r'X\[.+?\]\s*~=\s*X\[', ctx): return 'NE'
        if re.search(r'X\[.+?\]\s*<\s*X\[', ctx): return 'LT'
        if re.search(r'X\[.+?\]\s*<=\s*X\[', ctx): return 'LE'
        if re.search(r'X\[.+?\]\[X\[', ctx): return 'GETTABLE'
        if re.search(r'y\[.+?\]\[', ctx): return 'GETTABUP'
        if re.search(r'\breturn\b', ctx): return 'RETURN'
        if re.search(r'\bw=', ctx): return 'JUMP'
        if re.search(r'\.\.', ctx): return 'CONCAT'
        if re.search(r'\bnot\s+X', ctx): return 'NOT'
        if re.search(r'#\s*X', ctx): return 'LEN'
        if re.search(r'^\s*-\s*X', ctx): return 'UNM'
        if re.search(r'X\[.+?\]=\s*X\[', ctx): return 'MOVE'
        if re.search(r'X\[.+?\]=\s*[UmSN]\[', ctx): return 'LOADK'
        if re.search(r'X\[.+?\]=\s*y\[', ctx): return 'GETUPVAL'
        if re.search(r'X\[.+?\]=\s*nil', ctx): return 'LOADNIL'
        if re.search(r'X\[.+?\]=\s*\{', ctx): return 'NEWTABLE'
        return 'UNKNOWN'

    def analyze_bytecode_format(self):
        """Analyze the bytecode data format"""
        if not self.bytecode_blocks:
            return {}

        main = self.bytecode_blocks[0]['decoded']

        analysis = {
            'size': len(main),
            'entropy': self._calc_entropy(main),
            'byte_freq': self._byte_frequency(main),
            'patterns': self._find_patterns(main),
        }

        print(f"[*] Bytecode analysis:")
        print(f"    Size: {analysis['size']} bytes")
        print(f"    Entropy: {analysis['entropy']:.2f} bits/byte")

        return analysis

    def _calc_entropy(self, data):
        """Calculate Shannon entropy"""
        import math
        freq = defaultdict(int)
        for b in data:
            freq[b] += 1
        entropy = 0
        for count in freq.values():
            p = count / len(data)
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def _byte_frequency(self, data):
        """Get byte frequency distribution"""
        freq = defaultdict(int)
        for b in data:
            freq[b] += 1
        return dict(sorted(freq.items(), key=lambda x: -x[1])[:20])

    def _find_patterns(self, data):
        """Find repeating patterns in data"""
        patterns = {}
        # Look for 4-byte patterns
        for i in range(len(data) - 3):
            pat = data[i:i+4]
            key = pat.hex()
            patterns[key] = patterns.get(key, 0) + 1

        # Return most common
        return dict(sorted(patterns.items(), key=lambda x: -x[1])[:10])

    def generate_output(self, output_path):
        """Generate comprehensive output"""
        lines = []

        lines.append("--" + "=" * 78)
        lines.append("-- LURAPH COMPREHENSIVE ANALYSIS")
        lines.append("-- Generated by Luraph Analyzer")
        lines.append("--" + "=" * 78)
        lines.append("")

        # Summary
        lines.append("--[[ ANALYSIS SUMMARY")
        lines.append(f"  VM Code: {len(self.vm_code)} bytes")
        lines.append(f"  Bytecode Blocks: {len(self.bytecode_blocks)}")
        lines.append(f"  Total Bytecode: {sum(b['size'] for b in self.bytecode_blocks)} bytes")
        lines.append(f"  VM Handlers: {len(self.vm_handlers)}")
        lines.append(f"  Opcodes Mapped: {len(self.opcodes)}")
        lines.append("]]")
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

        # VM variable reference
        lines.append("--[[ VM VARIABLE REFERENCE")
        lines.append("  q     = instruction array (opcodes)")
        lines.append("  w     = program counter")
        lines.append("  o     = current opcode = q[w]")
        lines.append("  X     = register stack")
        lines.append("  y     = upvalues array")
        lines.append("  U,m,S = constant arrays")
        lines.append("  N[w]  = operand A")
        lines.append("  d[w]  = operand B")
        lines.append("  _[w]  = operand C")
        lines.append("  H     = open upvalues")
        lines.append("  I     = stack base")
        lines.append("  V     = VM state table")
        lines.append("]]")
        lines.append("")

        # Bytecode blocks info
        lines.append("--[[ BYTECODE BLOCKS")
        for i, block in enumerate(self.bytecode_blocks[:20]):
            lines.append(f"  Block {i}: {block['size']:6d} bytes")
        lines.append("]]")
        lines.append("")

        # Hex dump of main bytecode
        if self.bytecode_blocks:
            main = self.bytecode_blocks[0]['decoded']
            lines.append("--[[ MAIN BYTECODE (first 2000 bytes)")
            for i in range(0, min(2000, len(main)), 32):
                chunk = main[i:i+32]
                hex_str = ' '.join(f'{b:02X}' for b in chunk)
                lines.append(f"  {i:04X}: {hex_str}")
            lines.append("]]")
            lines.append("")

        # Raw bytecode as Lua table
        lines.append("-- RAW BYTECODE DATA (Lua tables)")
        lines.append("")

        for i, block in enumerate(self.bytecode_blocks[:5]):
            data = block['decoded']
            lines.append(f"bytecode_{i} = {{  -- {len(data)} bytes")
            for j in range(0, min(len(data), 1000), 20):
                chunk = data[j:j+20]
                nums = ', '.join(str(b) for b in chunk)
                lines.append(f"  {nums},")
            if len(data) > 1000:
                lines.append(f"  -- ... ({len(data) - 1000} more bytes)")
            lines.append("}")
            lines.append("")

        # Handler list
        lines.append("--[[ VM HANDLERS")
        for name in sorted(self.vm_handlers.keys())[:50]:
            info = self.vm_handlers[name]
            lines.append(f"  {name}({info['args']})")
        lines.append("]]")
        lines.append("")

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"[*] Output saved to {output_path}")

        # Also save JSON data
        json_data = {
            'opcodes': {str(k): v for k, v in self.opcodes.items()},
            'bytecode_sizes': [b['size'] for b in self.bytecode_blocks],
            'handler_count': len(self.vm_handlers),
        }
        with open(output_path.replace('.lua', '.json'), 'w') as f:
            json.dump(json_data, f, indent=2)


def main():
    print("=" * 70)
    print("LURAPH COMPREHENSIVE ANALYZER")
    print("=" * 70)
    print()

    analyzer = LuraphAnalyzer()
    analyzer.load()
    analyzer.extract_bytecode()
    analyzer.analyze_vm_structure()
    analyzer.extract_opcodes()
    analyzer.analyze_bytecode_format()
    analyzer.generate_output('comprehensive_output.lua')

    print()
    print("[*] Analysis complete!")


if __name__ == "__main__":
    main()
