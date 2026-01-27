#!/usr/bin/env python3
"""
Deep Luraph VM Parser
Properly parses the nested opcode dispatch tree
"""

import re
import json
from collections import defaultdict

class VMParser:
    def __init__(self):
        self.opcodes = {}
        self.operations = []

    def load_e8(self, filename):
        """Load and extract E8 function"""
        with open(filename, 'r') as f:
            code = f.read()

        # Find E8 - the main interpreter
        match = re.search(r'E8=function\(z,V,B,L\)(.*)', code, re.DOTALL)
        if match:
            self.e8 = match.group(1)[:50000]  # Get substantial chunk
            print(f"[*] Extracted E8: {len(self.e8)} chars")

    def parse_all_branches(self):
        """Parse all opcode branches in the E8 function"""
        # The structure is:
        # if o>=RANGE then
        #   if o>=SUBRANGE then
        #     if o==SPECIFIC then OPERATION
        #     else OTHER_OPERATION
        #   else ...

        # Strategy: Find ALL instances where operations happen
        # and trace back to find the opcode conditions

        # Find all X[...] assignments (stack operations)
        pattern = r'(X\[[^\]]+\])\s*=\s*([^;]+);'
        for match in re.finditer(pattern, self.e8):
            dest = match.group(1)
            source = match.group(2)
            pos = match.start()

            # Trace back to find controlling opcode
            opcodes = self._trace_opcodes(pos)
            op_type = self._identify_op(source, dest)

            self.operations.append({
                'dest': dest,
                'source': source[:80],
                'pos': pos,
                'opcodes': opcodes,
                'op_type': op_type
            })

        print(f"[*] Found {len(self.operations)} operations")

        # Build opcode map from operations
        self._build_opcode_map()

    def _trace_opcodes(self, pos):
        """Trace back from position to find controlling opcodes"""
        # Look at code before this position
        context = self.e8[max(0, pos-1000):pos]

        opcodes = []

        # Find all opcode checks in reverse order
        checks = list(re.finditer(
            r'o\s*(==|~=|>=|<=|>|<)\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)',
            context
        ))

        for check in checks[-5:]:  # Last 5 checks
            op = check.group(1)
            val = self._parse_num(check.group(2))
            if val is not None:
                opcodes.append((op, val))

        return opcodes

    def _parse_num(self, s):
        """Parse number literal"""
        s = s.replace('_', '')
        try:
            if 'x' in s.lower():
                return int(s, 16)
            elif 'b' in s.lower():
                return int(s.replace('0b', '').replace('0B', ''), 2)
            return int(s)
        except:
            return None

    def _identify_op(self, source, dest):
        """Identify operation type from source expression"""
        s = source.strip()

        # Arithmetic
        if re.search(r'X\[.*?\]\s*\+\s*X\[', s):
            return 'ADD'
        if re.search(r'[Um]\[.*?\]\s*\+\s*X\[', s) or re.search(r'X\[.*?\]\s*\+\s*[Um]\[', s):
            return 'ADDK'
        if re.search(r'X\[.*?\]\s*-\s*X\[', s):
            return 'SUB'
        if re.search(r'[Um]\[.*?\]\s*-\s*X\[', s):
            return 'SUBK'
        if re.search(r'X\[.*?\]\s*\*\s*X\[', s):
            return 'MUL'
        if re.search(r'X\[.*?\]\s*/\s*X\[', s):
            return 'DIV'
        if re.search(r'X\[.*?\]\s*%\s*X\[', s):
            return 'MOD'
        if re.search(r'X\[.*?\]\s*\^\s*X\[', s):
            return 'POW'

        # Comparison
        if re.search(r'X\[.*?\]\s*==\s*X\[', s):
            return 'EQ'
        if re.search(r'X\[.*?\]\s*~=\s*X\[', s):
            return 'NE'
        if re.search(r'X\[.*?\]\s*<\s*X\[', s):
            return 'LT'
        if re.search(r'X\[.*?\]\s*<=\s*X\[', s):
            return 'LE'
        if re.search(r'X\[.*?\]\s*>\s*X\[', s):
            return 'GT'
        if re.search(r'X\[.*?\]\s*>=\s*X\[', s):
            return 'GE'

        # Compare with constant
        if re.search(r'[Um]\[.*?\]\s*[<>=]', s):
            return 'CMPK'

        # String
        if '..' in s:
            return 'CONCAT'

        # Table
        if re.search(r'X\[.*?\]\[X\[.*?\]\]', s):
            return 'GETTABLE'
        if re.search(r'\{\s*\}', s):
            return 'NEWTABLE'

        # Unary
        if s.startswith('-X[') or s.startswith('- X['):
            return 'UNM'
        if s.startswith('not ') or s.startswith('not('):
            return 'NOT'
        if s.startswith('#X[') or s.startswith('# X['):
            return 'LEN'

        # Load
        if s == 'nil':
            return 'LOADNIL'
        if s in ('true', 'false'):
            return 'LOADBOOL'
        if re.match(r'^X\[[^\]]+\]$', s):
            return 'MOVE'
        if re.match(r'^[UmSN]\[', s):
            return 'LOADK'
        if re.match(r'^V\[', s):
            return 'GETGLOBAL'

        # Bitwise
        if '.band(' in s or 'band(' in s:
            return 'BAND'
        if '.bor(' in s or 'bor(' in s:
            return 'BOR'
        if '.bxor(' in s or 'bxor(' in s:
            return 'BXOR'
        if '.bnot(' in s:
            return 'BNOT'
        if '.lshift(' in s or 'lshift(' in s:
            return 'SHL'
        if '.rshift(' in s or 'rshift(' in s:
            return 'SHR'

        # Function
        if re.search(r'X\[.*?\]\(', s):
            return 'CALL'
        if 'function' in s:
            return 'CLOSURE'

        return 'UNKNOWN'

    def _build_opcode_map(self):
        """Build opcode map from traced operations"""
        # For operations with == checks, use that opcode
        for op in self.operations:
            for check_op, val in op['opcodes']:
                if check_op == '==' and op['op_type'] != 'UNKNOWN':
                    if val not in self.opcodes:
                        self.opcodes[val] = op['op_type']

        print(f"[*] Built opcode map with {len(self.opcodes)} entries")

    def parse_specific_opcodes(self):
        """Parse specific opcode == checks and their handlers"""
        # Find all if o==VALUE then patterns
        pattern = r'if\s+o\s*==\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)\s*then\s*([^;]+;)'

        for match in re.finditer(pattern, self.e8):
            val = self._parse_num(match.group(1))
            code = match.group(2)

            if val is not None and val not in self.opcodes:
                op_type = self._identify_op(code, '')
                if op_type != 'UNKNOWN':
                    self.opcodes[val] = op_type

        # Also find o~=VALUE (negated checks) - the else branch is the == case
        pattern2 = r'o\s*~=\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)'
        for match in re.finditer(pattern2, self.e8):
            val = self._parse_num(match.group(1))
            # These tell us what opcodes exist but need more context for the operation

        print(f"[*] After specific parsing: {len(self.opcodes)} opcodes")

    def analyze_instruction_format(self):
        """Analyze how instructions are decoded"""
        # Look for patterns that extract fields from instruction word
        # Common patterns: value % N, value / N, bit operations

        # Find instruction fetch
        fetch = re.search(r'local\s+o\s*=\s*\(?([^;)]+)', self.e8)
        if fetch:
            print(f"[*] Instruction fetch: {fetch.group(1)[:60]}")

        # Find field extractions
        # Pattern: varname = expr % N or expr / N
        extracts = re.findall(r'(\w+)\s*=\s*[^;]*?[%/]\s*(\d+)', self.e8[:5000])
        if extracts:
            print(f"[*] Field extractions: {extracts[:10]}")

    def generate_full_map(self):
        """Generate complete opcode map with Lua standard opcodes"""
        # Standard Lua 5.x opcodes for reference
        lua_opcodes = {
            0: 'MOVE', 1: 'LOADK', 2: 'LOADBOOL', 3: 'LOADNIL',
            4: 'GETUPVAL', 5: 'GETGLOBAL', 6: 'GETTABLE',
            7: 'SETGLOBAL', 8: 'SETUPVAL', 9: 'SETTABLE',
            10: 'NEWTABLE', 11: 'SELF', 12: 'ADD', 13: 'SUB',
            14: 'MUL', 15: 'DIV', 16: 'MOD', 17: 'POW',
            18: 'UNM', 19: 'NOT', 20: 'LEN', 21: 'CONCAT',
            22: 'JMP', 23: 'EQ', 24: 'LT', 25: 'LE',
            26: 'TEST', 27: 'TESTSET', 28: 'CALL', 29: 'TAILCALL',
            30: 'RETURN', 31: 'FORLOOP', 32: 'FORPREP',
            33: 'TFORLOOP', 34: 'SETLIST', 35: 'CLOSE',
            36: 'CLOSURE', 37: 'VARARG',
        }

        print("\n[*] Standard Lua opcodes for reference:")
        for op, name in lua_opcodes.items():
            print(f"    {op:2d}: {name}")

        return lua_opcodes

def extract_all_operations_from_vm():
    """Extract all operations by parsing the full E8 body more carefully"""
    with open('/home/user/deobluraph/deobfuscated.lua', 'r') as f:
        code = f.read()

    # Find the h function inside E8 - this is the actual bytecode interpreter
    # Pattern: h=function(...)...end
    h_match = re.search(r'h=function\(\.\.\.\)(.*?)(?=local\s+\w+,\w+=V)', code, re.DOTALL)
    if h_match:
        h_body = h_match.group(1)
        print(f"[*] Found h (interpreter) function: {len(h_body)} chars")

        # Now parse the opcode dispatch within h
        opcodes = {}

        # The dispatch uses: if o>=VALUE then ... structure
        # Find all opcode-specific handlers

        # Pattern for direct opcode checks
        for match in re.finditer(r'if\s+o\s*==\s*(0x[0-9a-fA-F]+|0b[01]+|\d+)', h_body):
            opcode = int(match.group(1).replace('_', ''), 0)
            # Get the code that follows
            start = match.end()
            end = min(start + 200, len(h_body))
            handler_code = h_body[start:end]

            # Identify operation
            op_type = identify_operation(handler_code)
            if op_type:
                opcodes[opcode] = op_type

        print(f"[*] Extracted {len(opcodes)} opcodes from h function")
        return opcodes, h_body

    return {}, ""

def identify_operation(code):
    """Identify Lua operation from code snippet"""
    code = code[:150]  # First part only

    patterns = [
        (r'X\[.*?\]\s*=\s*X\[.*?\]\s*\+\s*X\[', 'ADD'),
        (r'X\[.*?\]\s*=\s*X\[.*?\]\s*-\s*X\[', 'SUB'),
        (r'X\[.*?\]\s*=\s*X\[.*?\]\s*\*\s*X\[', 'MUL'),
        (r'X\[.*?\]\s*=\s*X\[.*?\]\s*/\s*X\[', 'DIV'),
        (r'X\[.*?\]\s*=\s*X\[.*?\]\s*%\s*X\[', 'MOD'),
        (r'X\[.*?\]\s*=\s*X\[.*?\]\s*\^\s*X\[', 'POW'),
        (r'X\[.*?\]\s*=\s*X\[.*?\]\s*\.\.\s*X\[', 'CONCAT'),
        (r'X\[.*?\]\s*=\s*-\s*X\[', 'UNM'),
        (r'X\[.*?\]\s*=\s*not\s+X\[', 'NOT'),
        (r'X\[.*?\]\s*=\s*#\s*X\[', 'LEN'),
        (r'X\[.*?\]\s*=\s*X\[.*?\]\[X\[', 'GETTABLE'),
        (r'\[X\[.*?\]\]\s*=\s*X\[', 'SETTABLE'),
        (r'X\[.*?\]\s*=\s*nil', 'LOADNIL'),
        (r'X\[.*?\]\s*=\s*true|X\[.*?\]\s*=\s*false', 'LOADBOOL'),
        (r'X\[.*?\]\s*=\s*X\[.*?\];', 'MOVE'),
        (r'X\[.*?\]\s*=\s*\{', 'NEWTABLE'),
        (r'X\[.*?\]\s*==\s*X\[', 'EQ'),
        (r'X\[.*?\]\s*<\s*X\[', 'LT'),
        (r'X\[.*?\]\s*<=\s*X\[', 'LE'),
        (r'X\[.*?\]\s*>\s*X\[', 'GT'),
        (r'X\[.*?\]\s*>=\s*X\[', 'GE'),
        (r'return\s+X\[', 'RETURN'),
        (r'X\[.*?\]\(', 'CALL'),
        (r'w\s*=\s*\w+\[\w+\]', 'JMP'),
    ]

    for pattern, op_type in patterns:
        if re.search(pattern, code):
            return op_type

    return None

def main():
    print("=" * 70)
    print("DEEP LURAPH VM PARSER")
    print("=" * 70)
    print()

    # Method 1: Parse E8 structure
    parser = VMParser()
    parser.load_e8('/home/user/deobluraph/deobfuscated.lua')
    parser.parse_all_branches()
    parser.parse_specific_opcodes()
    parser.analyze_instruction_format()

    # Method 2: Extract from h function directly
    print()
    print("[*] Trying direct h function extraction...")
    opcodes2, h_body = extract_all_operations_from_vm()

    # Merge results
    all_opcodes = {**parser.opcodes, **opcodes2}

    print()
    print("=" * 70)
    print("FINAL OPCODE MAP")
    print("=" * 70)

    # Group by operation
    by_op = defaultdict(list)
    for opcode, op_type in all_opcodes.items():
        by_op[op_type].append(opcode)

    for op_type in sorted(by_op.keys()):
        codes = sorted(by_op[op_type])
        print(f"{op_type:12s}: {', '.join(f'0x{c:02X}' for c in codes)}")

    print()
    print(f"Total opcodes mapped: {len(all_opcodes)}")

    # Save results
    with open('final_opcode_map.json', 'w') as f:
        json.dump({f"0x{k:02X}": v for k, v in sorted(all_opcodes.items())}, f, indent=2)

    # Generate standard Lua opcodes for reference
    parser.generate_full_map()

    return all_opcodes

if __name__ == "__main__":
    main()
