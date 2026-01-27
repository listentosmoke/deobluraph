#!/usr/bin/env python3
"""
Luraph VM Opcode Analyzer
Extracts and maps VM opcodes to Lua operations
"""

import re
import json

def parse_vm_code():
    with open('/home/user/deobluraph/deobfuscated.lua', 'r') as f:
        code = f.read()

    # Find the main VM execution function (E8)
    e8_match = re.search(r'E8=function\([^)]*\)(.*?)end,\w+=', code, re.DOTALL)
    if not e8_match:
        print("Could not find E8 function")
        return None

    body = e8_match.group(1)
    return body, code

def extract_opcode_handlers(body):
    """Extract opcode -> handler mappings"""
    handlers = {}

    # Pattern to match opcode checks and their operations
    # Look for patterns like: if o==0xNN then ... end or o~=0xNN

    # Split by opcode checks
    segments = re.split(r'(if\s+o[=<>~]+\s*0[xXbB][0-9a-fA-F_]+|elseif\s+o[=<>~]+\s*0[xXbB][0-9a-fA-F_]+|else)', body)

    current_opcode = None
    for segment in segments:
        # Check if this segment is an opcode check
        op_match = re.search(r'o(==|~=|>=|<=|>|<)\s*(0[xXbB][0-9a-fA-F_]+)', segment)
        if op_match:
            op_str = op_match.group(2)
            try:
                if 'x' in op_str.lower():
                    opcode = int(op_str.replace('_', ''), 16)
                elif 'b' in op_str.lower():
                    opcode = int(op_str.replace('_', '').lower().replace('0b', ''), 2)
                else:
                    opcode = int(op_str)
                current_opcode = opcode
            except:
                pass
        elif current_opcode is not None and 'X[' in segment:
            # This segment contains operations
            # Extract the operation pattern
            ops = extract_operations(segment)
            if ops and current_opcode not in handlers:
                handlers[current_opcode] = ops

    return handlers

def extract_operations(segment):
    """Extract Lua operations from a code segment"""
    operations = []

    # Common patterns for VM operations
    patterns = {
        'MOVE': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]',
        'LOADK': r'X\[(\w+\[\w+\])\]\s*=\s*(\w+\[\w+\])',
        'LOADNIL': r'X\[(\w+\[\w+\])\]\s*=\s*nil',
        'LOADBOOL': r'X\[(\w+\[\w+\])\]\s*=\s*(true|false)',
        'ADD': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*\+\s*X\[(\w+\[\w+\])\]',
        'SUB': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*-\s*X\[(\w+\[\w+\])\]',
        'MUL': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*\*\s*X\[(\w+\[\w+\])\]',
        'DIV': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*/\s*X\[(\w+\[\w+\])\]',
        'MOD': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*%\s*X\[(\w+\[\w+\])\]',
        'POW': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*\^\s*X\[(\w+\[\w+\])\]',
        'UNM': r'X\[(\w+\[\w+\])\]\s*=\s*-X\[(\w+\[\w+\])\]',
        'NOT': r'X\[(\w+\[\w+\])\]\s*=\s*not\s+X\[(\w+\[\w+\])\]',
        'LEN': r'X\[(\w+\[\w+\])\]\s*=\s*#X\[(\w+\[\w+\])\]',
        'CONCAT': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*\.\.\s*X\[(\w+\[\w+\])\]',
        'EQ': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*==\s*X\[(\w+\[\w+\])\]',
        'LT': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*<\s*X\[(\w+\[\w+\])\]',
        'LE': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*<=\s*X\[(\w+\[\w+\])\]',
        'GT': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*>\s*X\[(\w+\[\w+\])\]',
        'GE': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\s*>=\s*X\[(\w+\[\w+\])\]',
        'GETTABLE': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\]\[X\[(\w+\[\w+\])\]\]',
        'SETTABLE': r'X\[(\w+\[\w+\])\]\[X\[(\w+\[\w+\])\]\]\s*=\s*X\[(\w+\[\w+\])\]',
        'CALL': r'X\[(\w+\[\w+\])\]\s*\(',
        'RETURN': r'return\s+X\[',
        'JUMP': r'w\s*=\s*\w+\[\w+\]',
        'FORLOOP': r'for\s+',
        'NEWTABLE': r'X\[(\w+\[\w+\])\]\s*=\s*\{\}',
        'CLOSURE': r'X\[(\w+\[\w+\])\]\s*=\s*function',
        'GETUPVAL': r'X\[(\w+\[\w+\])\]\s*=\s*(\w+)\[',
        'SETUPVAL': r'(\w+)\[\s*=\s*X\[',
        'GETGLOBAL': r'X\[(\w+\[\w+\])\]\s*=\s*V\[',
        'SETGLOBAL': r'V\[\s*=\s*X\[',
        'SELF': r'X\[(\w+\[\w+\])\]\s*=\s*X\[(\w+\[\w+\])\];\s*X\[.*?\]\s*=\s*X\[.*?\]\[',
    }

    for name, pattern in patterns.items():
        if re.search(pattern, segment):
            operations.append(name)

    # Also extract the raw operation text
    raw_ops = []
    for match in re.finditer(r'X\[[^\]]+\][^;]+;', segment):
        raw_ops.append(match.group(0)[:100])

    return {'types': operations, 'raw': raw_ops[:3]}

def analyze_specific_opcodes(body):
    """Analyze specific opcode implementations"""
    opcode_map = {}

    # Find exact opcode == value patterns and extract their operations
    # Pattern: if o==VALUE then OPERATION or o~=VALUE

    lines = body.replace(';', ';\n').split('\n')
    current_check = None

    for line in lines:
        # Check for opcode comparison
        eq_match = re.search(r'o\s*==\s*(0x[0-9a-fA-F]+|0b[01]+|\d+)', line)
        neq_match = re.search(r'o\s*~=\s*(0x[0-9a-fA-F]+|0b[01]+|\d+)', line)

        if eq_match:
            op_str = eq_match.group(1)
            try:
                if op_str.startswith('0x'):
                    opcode = int(op_str, 16)
                elif op_str.startswith('0b'):
                    opcode = int(op_str, 2)
                else:
                    opcode = int(op_str)
                current_check = ('eq', opcode)
            except:
                pass

        # Extract operation if we have a current check
        if current_check and 'X[' in line:
            op_type, opcode = current_check

            # Try to identify the operation
            operation = identify_operation(line)
            if operation and opcode not in opcode_map:
                opcode_map[opcode] = operation

            current_check = None

    return opcode_map

def identify_operation(line):
    """Identify the type of Lua operation from code line"""

    # Arithmetic operations
    if re.search(r'X\[.+\]\s*\+\s*X\[.+\]', line):
        return 'ADD'
    if re.search(r'X\[.+\]\s*-\s*X\[.+\]', line):
        return 'SUB'
    if re.search(r'X\[.+\]\s*\*\s*X\[.+\]', line):
        return 'MUL'
    if re.search(r'X\[.+\]\s*/\s*X\[.+\]', line):
        return 'DIV'
    if re.search(r'X\[.+\]\s*%\s*X\[.+\]', line):
        return 'MOD'
    if re.search(r'X\[.+\]\s*\^\s*X\[.+\]', line):
        return 'POW'

    # Comparison operations
    if re.search(r'X\[.+\]\s*==\s*X\[.+\]', line):
        return 'EQ'
    if re.search(r'X\[.+\]\s*~=\s*X\[.+\]', line):
        return 'NE'
    if re.search(r'X\[.+\]\s*<\s*X\[.+\]', line):
        return 'LT'
    if re.search(r'X\[.+\]\s*<=\s*X\[.+\]', line):
        return 'LE'
    if re.search(r'X\[.+\]\s*>\s*X\[.+\]', line):
        return 'GT'
    if re.search(r'X\[.+\]\s*>=\s*X\[.+\]', line):
        return 'GE'

    # String concat
    if re.search(r'X\[.+\]\s*\.\.\s*X\[.+\]', line):
        return 'CONCAT'

    # Table operations
    if re.search(r'X\[.+\]\[X\[.+\]\]', line):
        if '=' in line and line.index('=') < line.index('[X['):
            return 'GETTABLE'
        else:
            return 'SETTABLE'

    # Unary operations
    if re.search(r'=\s*-X\[', line):
        return 'UNM'
    if re.search(r'=\s*not\s+X\[', line):
        return 'NOT'
    if re.search(r'=\s*#X\[', line):
        return 'LEN'

    # Nil/Bool
    if re.search(r'=\s*nil\s*;', line):
        return 'LOADNIL'
    if re.search(r'=\s*true\s*;', line) or re.search(r'=\s*false\s*;', line):
        return 'LOADBOOL'

    # Function call
    if re.search(r'X\[.+\]\(', line):
        return 'CALL'

    # Return
    if re.search(r'return\s+X\[', line):
        return 'RETURN'

    # Jump
    if re.search(r'w\s*=\s*\w+\[w\]', line):
        return 'JMP'

    # Move/Load
    if re.search(r'X\[.+\]\s*=\s*X\[.+\]', line):
        return 'MOVE'

    # New table
    if re.search(r'=\s*\{\s*\}', line):
        return 'NEWTABLE'

    return None

def main():
    print("[*] Analyzing Luraph VM opcodes...")

    result = parse_vm_code()
    if not result:
        return

    body, full_code = result

    # Analyze opcodes
    print("[*] Extracting opcode handlers...")
    opcode_map = analyze_specific_opcodes(body)

    print(f"[*] Mapped {len(opcode_map)} opcodes to operations")
    print()
    print("=== OPCODE MAP ===")
    for opcode in sorted(opcode_map.keys()):
        operation = opcode_map[opcode]
        print(f"  0x{opcode:02X} ({opcode:3d}): {operation}")

    # Save to file
    with open('opcode_map.json', 'w') as f:
        json.dump({f"0x{k:02X}": v for k, v in opcode_map.items()}, f, indent=2)

    print()
    print("[*] Opcode map saved to opcode_map.json")

    return opcode_map

if __name__ == "__main__":
    main()
