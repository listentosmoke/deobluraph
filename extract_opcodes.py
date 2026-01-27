#!/usr/bin/env python3
"""
Extract opcodes by finding the opcode check immediately before each operation
"""

import re
import json
from collections import defaultdict

def load_vm_code():
    with open('/home/user/deobluraph/deobfuscated.lua', 'r') as f:
        return f.read()

def find_opcodes_for_operations():
    code = load_vm_code()

    # Find the dispatch section
    dispatch = re.search(r'repeat\s+local\s+o\s*=\s*\(?\s*q\[w\]\s*\)?\s*;(.{50000})', code, re.DOTALL)
    if not dispatch:
        print("[!] Could not find dispatch section")
        return {}

    body = dispatch.group(1)

    # Define operations and their patterns
    operations = {
        'ADD': [
            r'\+\s*X\[(?:N|d|_)\[w\]\]',  # X[A] + X[B]
        ],
        'ADDK': [
            r'\+\s*[Um]\[w\]',  # X[A] + K
            r'[Um]\[w\]\s*\+',  # K + X[A]
        ],
        'SUB': [
            r'X\[(?:N|d|_)\[w\]\]\s*-\s*X\[',  # X[A] - X[B]
        ],
        'SUBK': [
            r'[Um]\[w\]\s*-\s*[Xm]',  # K - X or K - K
            r'X\[.*?\]\s*-\s*[Um]\[',  # X - K
        ],
        'MUL': [
            r'X\[(?:N|d|_)\[w\]\]\s*\*\s*X\[',  # X[A] * X[B]
        ],
        'MULK': [
            r'[UmS]\[w\]\s*\*\s*X\[',  # K * X
            r'X\[.*?\]\s*\*\s*[UmS]\[',  # X * K
        ],
        'DIV': [
            r'X\[.*?\]\s*/\s*X\[(?!.*//)',  # X / X (not //)
        ],
        'IDIV': [
            r'X\[.*?\]\s*//\s*X\[',  # X // X
        ],
        'MOD': [
            r'X\[.*?\]\s*%\s*X\[',  # X % X
        ],
        'POW': [
            r'X\[.*?\]\s*\^\s*X\[',  # X ^ X
        ],
        'CONCAT': [
            r'X\[.*?\]\s*\.\.\s*X\[',  # X .. X
        ],
        'EQ': [
            r'X\[(?:N|d|_)\[w\]\]\s*==\s*X\[',  # X == X
        ],
        'EQK': [
            r'X\[.*?\]\s*==\s*[Um]\[',  # X == K
            r'[Um]\[w\]\s*==\s*X\[',  # K == X
        ],
        'NE': [
            r'X\[.*?\]\s*~=\s*X\[',  # X ~= X
        ],
        'NEK': [
            r'[Um]\[w\]\s*~=\s*X\[',  # K ~= X
        ],
        'LT': [
            r'X\[(?:N|d|_)\[w\]\]\s*<\s*X\[',  # X < X
        ],
        'LTK': [
            r'X\[.*?\]\s*<\s*[Um]\[',  # X < K
        ],
        'LE': [
            r'X\[.*?\]\s*<=\s*X\[',  # X <= X
        ],
        'GT': [
            r'X\[(?:N|d|_)\[w\]\]\s*>\s*X\[',  # X > X
        ],
        'GTK': [
            r'[Um]\[w\]\s*>\s*X\[',  # K > X
        ],
        'GE': [
            r'X\[(?:N|d|_)\[w\]\]\s*>=\s*X\[',  # X >= X
        ],
        'GEK': [
            r'X\[.*?\]\s*>=\s*[Um]\[',  # X >= K
        ],
        'UNM': [
            r'=\s*-\s*X\[',  # -X
        ],
        'NOT': [
            r'=\s*not\s+X\[',  # not X
        ],
        'LEN': [
            r'=\s*#\s*X\[',  # #X
        ],
        'GETTABLE': [
            r'X\[(?:N|d|_)\[w\]\]\[X\[',  # X[A][X[B]]
        ],
        'SETTABLE': [
            r'\[X\[(?:N|d|_)\[w\]\]\]\s*=\s*(?:\()?X\[',  # X[A][X[B]] = X
        ],
        'GETTABUP': [
            r'y\[(?:N|d|_)\[w\]\]\[X\[',  # y[A][X[B]]
        ],
        'SETTABUP': [
            r'y\[.*?\]\[X\[.*?\]\]\s*=',  # y[A][X[B]] =
        ],
        'GETUPVAL': [
            r'=\s*\(?\s*y\[(?:N|d|_)\[w\]\]\s*\)?[;\s]',  # = y[A]
        ],
        'SETUPVAL': [
            r'y\[(?:N|d|_)\[w\]\]\s*=\s*X\[',  # y[A] = X
        ],
        'LOADNIL': [
            r'=\s*nil\s*[;\s]',  # = nil
        ],
        'LOADK': [
            r'=\s*[UmSN]\[(?:N|d|_)?\[?w\]?\]\s*[;\s]',  # = K
            r'=\s*V\[\d+\]\s*\(',  # = V[n](
        ],
        'MOVE': [
            r'=\s*X\[(?:N|d|_)\[w\]\]\s*[;\s]',  # = X[A]
        ],
        'JMP': [
            r'w\s*=\s*\(?\s*(?:N|d|_)\[w\]\s*\)?[;\s]',  # w = operand
        ],
        'CALL': [
            r'X\[i\]\s*\(',  # X[i](
            r'I\s*=\s*\(?\s*d\[w\]\s*\)?.*X\[I\]\s*\(\s*\)',  # I=d[w]; X[I]()
        ],
        'RETURN': [
            r'return\s+X\[i\]\s*\(',  # return X[i](
        ],
        'FORLOOP': [
            r'G\s*\+\s*=\s*Q',  # G += Q
        ],
        'FORPREP': [
            r'c\s*=\s*\(\s*\{',  # c = ({
        ],
        'CLOSURE': [
            r'a\s*=\s*i\[0B110\]',  # closure setup
        ],
        'VARARG': [
            r'e,F\s*=\s*V\[',  # vararg capture
        ],
        'SELF': [
            r'X\[d\[w\]\]\s*=\s*X\[N\[w\]\].*X\[_\[w\]\]\s*=\s*X\[N\[w\]\]\[',  # self pattern
        ],
    }

    opcode_map = {}

    # For each operation type, find where it appears and trace back to opcode
    for op_name, patterns in operations.items():
        for pattern in patterns:
            for match in re.finditer(pattern, body):
                pos = match.start()

                # Look back for the nearest opcode check
                context = body[max(0, pos-300):pos]

                # Find opcode checks (o==VALUE or o~=VALUE)
                opchecks = list(re.finditer(
                    r'o\s*(==|~=)\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)',
                    context
                ))

                if opchecks:
                    last_check = opchecks[-1]
                    check_type = last_check.group(1)
                    val_str = last_check.group(2).replace('_', '')

                    try:
                        if 'x' in val_str.lower():
                            opcode = int(val_str, 16)
                        elif 'b' in val_str.lower():
                            opcode = int(val_str[2:], 2)
                        else:
                            opcode = int(val_str)

                        # For == checks, this IS the opcode
                        # For ~= checks, this is NOT the opcode (need else branch)
                        if check_type == '==':
                            if opcode not in opcode_map:
                                opcode_map[opcode] = op_name
                    except:
                        pass

    return opcode_map

def main():
    print("=" * 70)
    print("LURAPH OPCODE EXTRACTION")
    print("=" * 70)
    print()

    opcodes = find_opcodes_for_operations()

    # Group by operation
    by_op = defaultdict(list)
    for opcode, op_name in opcodes.items():
        by_op[op_name].append(opcode)

    print("OPCODE MAP:")
    print("-" * 70)
    for op_name in sorted(by_op.keys()):
        codes = sorted(by_op[op_name])
        codes_str = ', '.join(f'0x{c:02X}' for c in codes)
        print(f"{op_name:12s}: {codes_str}")

    print()
    print(f"Total opcodes mapped: {len(opcodes)}")
    print(f"Total operation types: {len(by_op)}")

    # Save results
    with open('luraph_final_opcodes.json', 'w') as f:
        json.dump({f"0x{k:02X}": v for k, v in sorted(opcodes.items())}, f, indent=2)
    print()
    print("Saved to luraph_final_opcodes.json")

    # Print full map
    print()
    print("=" * 70)
    print("FULL OPCODE TABLE")
    print("=" * 70)
    for opcode in sorted(opcodes.keys()):
        print(f"  0x{opcode:02X} ({opcode:3d}): {opcodes[opcode]}")

    return opcodes

if __name__ == "__main__":
    main()
