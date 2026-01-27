#!/usr/bin/env python3
"""
Final Luraph Decompiler
Produces comprehensive decompilation output from Luraph v14.5.2 protected code
"""

import re
import struct
import json
from collections import defaultdict

class FinalDecompiler:
    def __init__(self):
        self.vm_code = None
        self.opcodes = {}
        self.bytecode_blocks = []
        self.constants = []
        self.handlers = {}

    def load(self, path='/home/user/deobluraph/deobfuscated.lua'):
        with open(path, 'r') as f:
            self.vm_code = f.read()
        print(f"[*] Loaded {len(self.vm_code)} bytes of VM code")

    def extract_all_opcodes(self):
        """Extract all opcodes using multiple methods"""
        # Find E8 interpreter
        start = self.vm_code.find('E8=function(z,V,B,L)')
        e8_body = self.vm_code[start:start+50000]

        # Method 1: Direct o== patterns
        for m in re.finditer(r'o==(0[xXbB][0-9a-fA-F_]+|\d+)\s*then\s*([^e][^l][^s][^e][^;]{1,150});', e8_body):
            opcode = self._parse_num(m.group(1))
            action = m.group(2)
            if opcode not in self.opcodes:
                self.opcodes[opcode] = self._classify_action(action)

        # Method 2: Range narrowing
        # Find all operation sites and trace back through conditions
        for m in re.finditer(r'(?:\(X\)|X)\[([^\]]+)\]=([^;]{1,80});', e8_body):
            pos = m.start()
            context = e8_body[max(0, pos-400):pos]
            dest, source = m.group(1), m.group(2)

            # Find controlling conditions
            opcode = self._find_opcode_from_context(context)
            if opcode is not None and opcode not in self.opcodes:
                self.opcodes[opcode] = {
                    'type': self._identify_op_type(source, dest),
                    'dest': dest[:30],
                    'source': source[:50]
                }

        # Method 3: Return/jump patterns
        for m in re.finditer(r'o==(0[xXbB][0-9a-fA-F_]+|\d+)\s*then.*?return\s+([^;]+);', e8_body):
            opcode = self._parse_num(m.group(1))
            if opcode not in self.opcodes:
                self.opcodes[opcode] = {'type': 'RETURN', 'action': m.group(2)[:50]}

        for m in re.finditer(r'o==(0[xXbB][0-9a-fA-F_]+|\d+)\s*then.*?w=([^;]+);', e8_body):
            opcode = self._parse_num(m.group(1))
            if opcode not in self.opcodes:
                self.opcodes[opcode] = {'type': 'JUMP', 'target': m.group(2)[:50]}

        print(f"[*] Extracted {len(self.opcodes)} opcodes")

    def _parse_num(self, s):
        s = s.replace('_', '')
        if s.startswith('0x') or s.startswith('0X'):
            return int(s, 16)
        if s.startswith('0b') or s.startswith('0B'):
            return int(s[2:], 2)
        return int(s)

    def _find_opcode_from_context(self, context):
        """Find opcode from surrounding condition context"""
        # Look for exact matches first
        eq_checks = list(re.finditer(r'o==(0[xXbB][0-9a-fA-F_]+|\d+)', context))
        if eq_checks:
            return self._parse_num(eq_checks[-1].group(1))

        # Try range narrowing
        ranges = list(re.finditer(r'o(>=|<=|>|<)(0[xXbB][0-9a-fA-F_]+|\d+)', context))
        min_v, max_v = 0, 255
        for m in ranges:
            op, val = m.group(1), self._parse_num(m.group(2))
            if op == '>=': min_v = max(min_v, val)
            elif op == '>': min_v = max(min_v, val + 1)
            elif op == '<=': max_v = min(max_v, val)
            elif op == '<': max_v = min(max_v, val - 1)

        if min_v == max_v:
            return min_v
        return None

    def _classify_action(self, action):
        """Classify an action string into operation type"""
        a = action.strip()
        return {'type': self._identify_op_type(a, ''), 'raw': a[:60]}

    def _identify_op_type(self, source, dest):
        """Identify Lua operation type"""
        s = source.strip()

        # Arithmetic
        if re.search(r'X\[.+?\]\s*\+\s*X\[', s): return 'ADD'
        if re.search(r'[UmS]\[.+?\]\s*\+', s): return 'ADDK'
        if re.search(r'X\[.+?\]\s*-\s*X\[', s): return 'SUB'
        if re.search(r'[UmS]\[.+?\]\s*-', s): return 'SUBK'
        if re.search(r'X\[.+?\]\s*\*\s*X\[', s): return 'MUL'
        if re.search(r'[UmS]\[.+?\]\s*\*', s): return 'MULK'
        if re.search(r'X\[.+?\]\s*//\s*X\[', s): return 'IDIV'
        if re.search(r'X\[.+?\]\s*/\s*X\[', s): return 'DIV'
        if re.search(r'X\[.+?\]\s*%\s*X\[', s): return 'MOD'
        if re.search(r'X\[.+?\]\s*%\s*[mUS]\[', s): return 'MODK'
        if re.search(r'X\[.+?\]\s*\^\s*X\[', s): return 'POW'

        # Comparison
        if re.search(r'X\[.+?\]\s*==\s*X\[', s): return 'EQ'
        if re.search(r'[UmS]\[.+?\]\s*==', s): return 'EQK'
        if re.search(r'X\[.+?\]\s*~=\s*X\[', s): return 'NE'
        if re.search(r'X\[.+?\]\s*~=\s*[UmS]\[', s): return 'NEK'
        if re.search(r'X\[.+?\]\s*<\s*X\[', s): return 'LT'
        if re.search(r'X\[.+?\]\s*<=\s*X\[', s): return 'LE'
        if re.search(r'X\[.+?\]\s*>\s*X\[', s): return 'GT'
        if re.search(r'X\[.+?\]\s*>=\s*X\[', s): return 'GE'
        if re.search(r'[mUS]\[.+?\]\s*>=', s): return 'GEK'
        if re.search(r'[mUS]\[.+?\]\s*<', s): return 'LTK'
        if re.search(r'[mUS]\[.+?\]\s*<=', s): return 'LEK'

        # Table
        if re.search(r'X\[.+?\]\[X\[.+?\]\]', s): return 'GETTABLE'
        if re.search(r'X\[.+?\]\[[UmS]\[', s): return 'GETTABLEK'
        if re.search(r'y\[.+?\]\[', s): return 'GETTABUP'
        if re.search(r'^\s*\{', s): return 'NEWTABLE'

        # String
        if '..' in s: return 'CONCAT'

        # Unary
        if re.search(r'^\s*-\s*X\[', s): return 'UNM'
        if re.search(r'^\s*-\s*[UmS]\[', s): return 'UNMK'
        if re.search(r'^\s*not\s+X\[', s): return 'NOT'
        if re.search(r'^\s*#\s*X\[', s): return 'LEN'

        # Load
        if s == 'nil': return 'LOADNIL'
        if s in ('true', 'false'): return 'LOADBOOL'
        if re.match(r'^\s*X\[[^\]]+\]\s*$', s): return 'MOVE'
        if re.match(r'^\s*[UmSN]\[', s): return 'LOADK'
        if re.match(r'^\s*y\[', s): return 'GETUPVAL'

        # Bitwise
        if 'band(' in s: return 'BAND'
        if 'bor(' in s: return 'BOR'
        if 'bxor(' in s: return 'BXOR'
        if 'bnot(' in s: return 'BNOT'
        if 'lshift(' in s: return 'SHL'
        if 'rshift(' in s: return 'SHR'

        return 'UNKNOWN'

    def extract_bytecode(self):
        """Extract and analyze bytecode blocks"""
        for m in re.finditer(r'\[=*\[(.*?)\]=*\]', self.vm_code, re.DOTALL):
            decoded = self._base85_decode(m.group(1))
            if decoded and len(decoded) > 50:
                self.bytecode_blocks.append({
                    'size': len(decoded),
                    'data': decoded,
                    'preview': m.group(1)[:30]
                })

        self.bytecode_blocks.sort(key=lambda x: x['size'], reverse=True)
        total = sum(b['size'] for b in self.bytecode_blocks)
        print(f"[*] Found {len(self.bytecode_blocks)} bytecode blocks ({total} bytes total)")

    def _base85_decode(self, data):
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

    def extract_vm_handlers(self):
        """Extract named VM handler functions"""
        # Find function definitions in the main table
        for m in re.finditer(r'([a-zA-Z][a-zA-Z0-9_]*)=function\(([^)]*)\)', self.vm_code[:50000]):
            name = m.group(1)
            args = m.group(2)
            self.handlers[name] = {'args': args}

        print(f"[*] Found {len(self.handlers)} VM handlers")

    def generate_output(self, output_path):
        """Generate comprehensive decompilation output"""
        lines = []

        # Header
        lines.append("--" + "=" * 78)
        lines.append("-- LURAPH v14.5.2 DECOMPILATION OUTPUT")
        lines.append("-- Generated by Luraph Decompiler")
        lines.append("--" + "=" * 78)
        lines.append("")

        # Summary
        lines.append("--[[ ANALYSIS SUMMARY")
        lines.append(f"  VM Code Size: {len(self.vm_code)} bytes")
        lines.append(f"  Opcodes Mapped: {len(self.opcodes)}")
        lines.append(f"  Bytecode Blocks: {len(self.bytecode_blocks)}")
        lines.append(f"  Total Bytecode: {sum(b['size'] for b in self.bytecode_blocks)} bytes")
        lines.append(f"  VM Handlers: {len(self.handlers)}")
        lines.append("]]")
        lines.append("")

        # Opcode Map
        lines.append("--[[ OPCODE MAP")
        by_type = defaultdict(list)
        for opcode, info in self.opcodes.items():
            by_type[info.get('type', 'UNKNOWN')].append(opcode)

        for op_type in sorted(by_type.keys()):
            codes = sorted(by_type[op_type])
            codes_str = ', '.join(f'0x{c:02X}' for c in codes)
            lines.append(f"  {op_type:12s}: {codes_str}")

        lines.append(f"\n  Total: {len(self.opcodes)} opcodes in {len(by_type)} categories")
        lines.append("]]")
        lines.append("")

        # Detailed opcode info
        lines.append("--[[ OPCODE DETAILS")
        for opcode in sorted(self.opcodes.keys()):
            info = self.opcodes[opcode]
            op_type = info.get('type', 'UNKNOWN')
            details = info.get('source', info.get('raw', info.get('action', info.get('target', ''))))
            lines.append(f"  0x{opcode:02X} ({opcode:3d}): {op_type:12s} | {details[:50]}")
        lines.append("]]")
        lines.append("")

        # VM Variables Reference
        lines.append("--[[ VM VARIABLE REFERENCE")
        lines.append("  q     = instruction array")
        lines.append("  w     = program counter (PC)")
        lines.append("  o     = current opcode (q[w])")
        lines.append("  X     = register stack")
        lines.append("  y     = upvalues array")
        lines.append("  U,m,S = constant arrays (numbers, strings)")
        lines.append("  N[w]  = instruction operand A")
        lines.append("  d[w]  = instruction operand B")
        lines.append("  _[w]  = instruction operand C")
        lines.append("  H     = open upvalue list (for closures)")
        lines.append("  I     = stack top / base")
        lines.append("  V     = VM state table")
        lines.append("]]")
        lines.append("")

        # Bytecode blocks
        lines.append("--[[ BYTECODE BLOCKS")
        for i, block in enumerate(self.bytecode_blocks[:20]):
            lines.append(f"  Block {i}: {block['size']:6d} bytes")
        if len(self.bytecode_blocks) > 20:
            lines.append(f"  ... and {len(self.bytecode_blocks) - 20} more blocks")
        lines.append("]]")
        lines.append("")

        # Disassembly of main block
        if self.bytecode_blocks:
            main_block = self.bytecode_blocks[0]
            lines.append(f"--[[ MAIN BYTECODE DISASSEMBLY ({main_block['size']} bytes)")
            lines.append("  Note: Bytecode is encrypted - showing raw instruction decode")
            lines.append("")

            data = main_block['data']
            for i in range(0, min(2000, len(data) - 3), 4):
                word = struct.unpack('<I', data[i:i+4])[0]
                opcode = word & 0xFF
                A = (word >> 8) & 0xFF
                B = (word >> 16) & 0xFF
                C = (word >> 24) & 0xFF

                op_name = self.opcodes.get(opcode, {}).get('type', f'OP_{opcode}')
                lines.append(f"  {i//4:4d}: {op_name:12s} A={A:3d} B={B:3d} C={C:3d}  ; 0x{word:08X}")

            if len(data) > 2000:
                lines.append(f"  ... ({(len(data) - 2000) // 4} more instructions)")
            lines.append("]]")
            lines.append("")

        # VM handlers
        lines.append("--[[ VM HANDLER FUNCTIONS")
        for name in sorted(self.handlers.keys())[:50]:
            info = self.handlers[name]
            lines.append(f"  {name}({info['args']})")
        if len(self.handlers) > 50:
            lines.append(f"  ... and {len(self.handlers) - 50} more handlers")
        lines.append("]]")
        lines.append("")

        # Pseudo-source reconstruction attempt
        lines.append("-- RECONSTRUCTED PSEUDO-SOURCE")
        lines.append("-- Note: Original source is protected; this is a structural approximation")
        lines.append("")

        # Generate pseudo-source from bytecode
        if self.bytecode_blocks:
            self._generate_pseudo_source(self.bytecode_blocks[0]['data'], lines)

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"[*] Saved output to {output_path}")
        return len(lines)

    def _generate_pseudo_source(self, data, output):
        """Generate pseudo-source from bytecode"""
        output.append("local function main()")
        indent = 1

        instructions = []
        for i in range(0, min(len(data) - 3, 4000), 4):
            word = struct.unpack('<I', data[i:i+4])[0]
            instructions.append({
                'pc': i // 4,
                'raw': word,
                'opcode': word & 0xFF,
                'A': (word >> 8) & 0xFF,
                'B': (word >> 16) & 0xFF,
                'C': (word >> 24) & 0xFF
            })

        for instr in instructions[:500]:
            opcode = instr['opcode']
            A, B, C = instr['A'], instr['B'], instr['C']
            pc = instr['pc']

            info = self.opcodes.get(opcode, {})
            op_type = info.get('type', f'OP_{opcode}')

            line = None

            if op_type == 'MOVE':
                line = f"R{A} = R{B}"
            elif op_type == 'LOADK':
                line = f"R{A} = K{B}"
            elif op_type == 'LOADNIL':
                line = f"R{A} = nil"
            elif op_type == 'LOADBOOL':
                line = f"R{A} = {'true' if B else 'false'}"
            elif op_type == 'ADD':
                line = f"R{A} = R{B} + R{C}"
            elif op_type == 'ADDK':
                line = f"R{A} = R{B} + K{C}"
            elif op_type == 'SUB':
                line = f"R{A} = R{B} - R{C}"
            elif op_type == 'SUBK':
                line = f"R{A} = R{B} - K{C}"
            elif op_type == 'MUL':
                line = f"R{A} = R{B} * R{C}"
            elif op_type == 'MULK':
                line = f"R{A} = R{B} * K{C}"
            elif op_type == 'DIV':
                line = f"R{A} = R{B} / R{C}"
            elif op_type == 'IDIV':
                line = f"R{A} = R{B} // R{C}"
            elif op_type == 'MOD':
                line = f"R{A} = R{B} % R{C}"
            elif op_type == 'MODK':
                line = f"R{A} = R{B} % K{C}"
            elif op_type == 'POW':
                line = f"R{A} = R{B} ^ R{C}"
            elif op_type == 'UNM':
                line = f"R{A} = -R{B}"
            elif op_type == 'NOT':
                line = f"R{A} = not R{B}"
            elif op_type == 'LEN':
                line = f"R{A} = #R{B}"
            elif op_type == 'CONCAT':
                line = f"R{A} = R{B} .. ... .. R{C}"
            elif op_type in ('EQ', 'NE', 'LT', 'LE', 'GT', 'GE'):
                ops = {'EQ': '==', 'NE': '~=', 'LT': '<', 'LE': '<=', 'GT': '>', 'GE': '>='}
                line = f"if R{B} {ops.get(op_type, '?')} R{C} then"
            elif op_type == 'JUMP':
                line = f"goto PC_{pc + B}"
            elif op_type == 'GETTABLE':
                line = f"R{A} = R{B}[R{C}]"
            elif op_type == 'GETTABLEK':
                line = f"R{A} = R{B}[K{C}]"
            elif op_type == 'NEWTABLE':
                line = f"R{A} = {{}}"
            elif op_type == 'GETUPVAL':
                line = f"R{A} = upvalue[{B}]"
            elif op_type == 'GETTABUP':
                line = f"R{A} = upvalue[{B}][R{C}]"
            elif op_type == 'RETURN':
                line = f"return R{A}, ... "
            elif op_type.startswith('OP_'):
                line = f"-- {op_type} A={A} B={B} C={C}"
            else:
                line = f"-- {op_type} A={A} B={B} C={C}"

            if line:
                output.append('    ' * indent + f"-- [{pc:4d}] " + line)

        output.append("    -- ... (truncated)")
        output.append("end")
        output.append("")
        output.append("return main")


def main():
    print("=" * 80)
    print("LURAPH FINAL DECOMPILER")
    print("=" * 80)
    print()

    decompiler = FinalDecompiler()
    decompiler.load()
    decompiler.extract_all_opcodes()
    decompiler.extract_bytecode()
    decompiler.extract_vm_handlers()

    print()
    num_lines = decompiler.generate_output('/home/user/deobluraph/final_decompiled.lua')
    print(f"[*] Generated {num_lines} lines of output")

    # Also save opcode map as JSON
    with open('/home/user/deobluraph/opcode_map.json', 'w') as f:
        json.dump({str(k): v for k, v in decompiler.opcodes.items()}, f, indent=2)
    print("[*] Saved opcode map to opcode_map.json")

    return decompiler


if __name__ == "__main__":
    main()
