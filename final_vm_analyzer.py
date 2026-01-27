#!/usr/bin/env python3
"""
Final Luraph VM Analyzer
Properly parses the complex opcode dispatch tree
"""

import re
import json
from collections import defaultdict

def load_e8_body():
    """Load the E8 function body"""
    with open('/home/user/deobluraph/deobfuscated.lua', 'r') as f:
        code = f.read()

    # Find E8's main handler
    match = re.search(r'E8=function\(z,V,B,L\)\(V\)\[0b0010_1000\]=function\(W,y,I\)(.*?)end,\w+=(?:function|bit)', code, re.DOTALL)
    if match:
        return match.group(1)
    return None

def identify_operation_from_code(code_snippet):
    """Identify the Lua operation from a code snippet"""
    s = code_snippet[:200]

    # Map patterns to operations
    patterns = [
        # Arithmetic with constants on right
        (r'\(X\)\[.+?\]\s*=\s*U\[\w+\]\s*-\s*m\[\w+\]', 'SUBK'),
        (r'\(X\)\[.+?\]\s*=\s*m\[\w+\]\s*\+\s*X\[', 'ADDK'),
        (r'X\[.+?\]\s*=\s*m\[\w+\]\s*\*\s*U\[\w+\]', 'MULK'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*\*\s*S\[\w+\]', 'MULK'),
        (r'X\[.+?\]\s*=\s*S\[\w+\]\s*\.\.\s*X\[', 'CONCATK'),
        (r'X\[.+?\]\s*=\s*U\[\w+\]\s*\*\s*X\[', 'MULK'),

        # Regular arithmetic
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*\+\s*X\[', 'ADD'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*-\s*X\[', 'SUB'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*\*\s*X\[', 'MUL'),
        (r'X\[.+?\]\s*/\s*X\[', 'DIV'),
        (r'X\[.+?\]\s*%\s*X\[', 'MOD'),
        (r'X\[.+?\]\s*\^\s*X\[', 'POW'),

        # Comparison
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*>=\s*U\[\w+\]', 'GEK'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*>\s*X\[', 'GT'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*>=\s*X\[', 'GE'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*<\s*X\[', 'LT'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*<=\s*X\[', 'LE'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*==\s*X\[', 'EQ'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*~=\s*X\[', 'NE'),
        (r'm\[\w+\]\s*>\s*X\[', 'GTK'),
        (r'm\[\w+\]\s*~=\s*X\[', 'NEK'),
        (r'm\[\w+\]\s*==\s*X\[', 'EQK'),
        (r'X\[.+?\]\s*<\s*U\[\w+\]', 'LTK'),

        # String
        (r'X\[.+?\]\s*=\s*X\[.+?\]\s*\.\.\s*X\[', 'CONCAT'),

        # Table operations
        (r'X\[.+?\]\[X\[.+?\]\]\s*=\s*\(X\[', 'SETTABLE'),
        (r'X\[.+?\]\[X\[.+?\]\]\s*=\s*X\[', 'SETTABLE'),
        (r'X\[.+?\]\[X\[.+?\]\]\s*=\s*m\[', 'SETTABLEK'),
        (r'\[S\[\w+\]\]\s*=\s*X\[', 'SETTABLEK'),
        (r'\[U\[\w+\]\]\s*=\s*X\[', 'SETTABLEK'),
        (r'X\[.+?\]\s*=\s*X\[.+?\]\[X\[', 'GETTABLE'),
        (r'X\[.+?\]\s*=\s*y\[.+?\]\[X\[', 'GETTABUP'),

        # Unary
        (r'=\s*-\s*X\[', 'UNM'),
        (r'=\s*not\s+X\[', 'NOT'),
        (r'=\s*#\s*X\[', 'LEN'),
        (r'K\s*=\s*#K', 'LENK'),

        # Load operations
        (r'X\[.+?\]\s*=\s*nil[;\s]', 'LOADNIL'),
        (r'X\[.+?\]\s*=\s*true[;\s]', 'LOADTRUE'),
        (r'X\[.+?\]\s*=\s*false[;\s]', 'LOADFALSE'),
        (r'\(X\)\[.+?\]\s*=\s*X\[.+?\][;\s]', 'MOVE'),
        (r'X\[.+?\]\s*=\s*X[;\s]', 'LOADSELF'),  # X[...]=X (table self)
        (r'X\[.+?\]\s*=\s*V\[\d+\]\(', 'LOADK'),
        (r'X\[.+?\]\s*=\s*m\[\w+\][;\s]', 'LOADK'),
        (r'X\[.+?\]\s*=\s*U\[\w+\][;\s]', 'LOADK'),
        (r'X\[.+?\]\s*=\s*S\[\w+\][;\s]', 'LOADK'),
        (r'X\[_\[\w+\]\]\s*=\s*m\[\w+\]', 'LOADK'),

        # Upvalue operations
        (r'y\[.+?\]\s*=\s*X\[', 'SETUPVAL'),
        (r'X\[.+?\]\s*=\s*y\[', 'GETUPVAL'),
        (r'X\[.+?\]\s*=\s*\(i\[0X3\]\[i\[', 'GETUPVAL'),
        (r'i\[0x3\]\[i\[0X2\]\]\)\[X\[', 'SETUPVAL'),
        (r'\(i\[0X3\]\[i\[0X2\]\]\)\[X\[', 'SETUPVAL'),

        # Control flow
        (r'w\s*=\s*\(\s*_\[\w+\]\s*\)', 'JMP'),
        (r'w\s*=\s*_\[\w+\]', 'JMP'),
        (r'w\s*=\s*N\[\w+\]', 'JMP'),
        (r'w\s*=\s*d\[\w+\]', 'JMP'),
        (r'I\s*=\s*\(\s*d\[\w+\]\s*\)', 'CALL'),

        # Function calls
        (r'X\[i\]\s*\(', 'CALL'),
        (r'return\s+X\[i\]\(', 'TAILCALL'),
        (r'return\s+X\[', 'RETURN'),

        # For loops
        (r'for\s+Y,p\s+in\s+H', 'TFORLOOP'),
        (r'G\s*\+\s*=\s*Q', 'FORLOOP'),
        (r'G\s*<=\s*A', 'FORLOOP'),
        (r'G\s*>=\s*A', 'FORLOOP'),
        (r'c\s*=\s*\(\s*\{', 'FORPREP'),

        # Closure
        (r'a\s*=\s*i\[0B110\]', 'CLOSURE'),
        (r'V\[0X28\]\(i,x\)', 'CLOSURE'),

        # Vararg
        (r'e,F\s*=\s*V\[', 'VARARG'),
        (r'for\s+Y\s*=\s*0b1,k', 'VARARG'),

        # Test/conditional
        (r'if\s+X\[d\[\w+\]\]\s*==\s*m\[\w+\]\s*then\s*w\s*=', 'TEST'),
        (r'if\s+m\[\w+\]\s*==\s*X\[d\[\w+\]\]\s*then\s*w\s*=', 'TEST'),
        (r'if\s+not\s*\(\s*not\s*\(\s*X\[.+?\]\s*<\s*X\[', 'TESTLT'),
        (r'if\s+not\s*\(\s*X\[.+?\]\s*<\s*U\[', 'TESTLTK'),
    ]

    for pattern, op_type in patterns:
        if re.search(pattern, s):
            return op_type

    return None

def parse_opcode_tree(body):
    """Parse the opcode dispatch tree and extract all mappings"""
    opcodes = {}

    # The structure uses:
    # if o>=VALUE then ... else ...  (binary tree)
    # if o==VALUE then ...  (leaf check)
    # if o~=VALUE then ... else ...  (negated check, else is the == case)

    # First, find all specific opcode checks (o==VALUE or o~=VALUE)
    # Pattern: if o==VALUE then CODE or o~=VALUE then ... else CODE

    # Find o==VALUE patterns
    eq_pattern = r'if\s+o\s*==\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)\s*then\s*([^;]+;)'
    for match in re.finditer(eq_pattern, body):
        val_str = match.group(1).replace('_', '')
        code = match.group(2)

        try:
            if 'x' in val_str.lower():
                opcode = int(val_str, 16)
            elif 'b' in val_str.lower():
                opcode = int(val_str[2:], 2)
            else:
                opcode = int(val_str)

            op = identify_operation_from_code(code)
            if op and opcode not in opcodes:
                opcodes[opcode] = op
        except:
            pass

    # Find o~=VALUE patterns (the else branch is the == case)
    neq_pattern = r'o\s*~=\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)\s*then\s*[^;]+;\s*else\s*([^;]+;)'
    for match in re.finditer(neq_pattern, body):
        val_str = match.group(1).replace('_', '')
        code = match.group(2)  # The else branch is where o==VALUE

        try:
            if 'x' in val_str.lower():
                opcode = int(val_str, 16)
            elif 'b' in val_str.lower():
                opcode = int(val_str[2:], 2)
            else:
                opcode = int(val_str)

            op = identify_operation_from_code(code)
            if op and opcode not in opcodes:
                opcodes[opcode] = op
        except:
            pass

    # Also look for operations right after range checks
    # Pattern: if o>=RANGE then if o>=SUBRANGE then OPERATION
    range_ops = re.finditer(
        r'if\s+(?:not\s*\()?\s*o\s*[<>=]+\s*(0x[0-9a-fA-F_]+|0b[01_]+|\d+)\s*\)?\s*then\s*(?:if\s+[^{]+?then\s*)?([^;]+;)',
        body
    )

    for match in range_ops:
        code = match.group(2)
        op = identify_operation_from_code(code)
        # These are harder to map to specific opcodes without more context

    return opcodes

def analyze_instruction_fields():
    """Analyze how instruction fields are used"""
    # From the code, we can see:
    # q[w] - fetch instruction (q is bytecode array, w is PC)
    # o = opcode
    # N[w], _[w], d[w] - instruction operands (A, B, C fields)
    # U[w], m[w], S[w] - constant operands (Bx, K fields)

    print("[*] Instruction field mapping:")
    print("    q[w]  - Fetch instruction from bytecode")
    print("    o     - Opcode (extracted from instruction)")
    print("    N[w]  - Operand A (typically destination register)")
    print("    _[w]  - Operand B (source register)")
    print("    d[w]  - Operand C (source register/immediate)")
    print("    U[w]  - Constant from U table")
    print("    m[w]  - Constant from m table")
    print("    S[w]  - Constant from S table")
    print("    X     - Register stack")
    print("    y     - Upvalue array")
    print("    H     - Open upvalues (for closures)")

def generate_lua_decompiler_skeleton(opcodes):
    """Generate a skeleton decompiler based on opcode map"""
    code = []
    code.append("-- Luraph VM Decompiler Skeleton")
    code.append("-- Generated from opcode analysis")
    code.append("")
    code.append("local opcodes = {")

    for opcode in sorted(opcodes.keys()):
        op_type = opcodes[opcode]
        code.append(f"    [0x{opcode:02X}] = '{op_type}',  -- {opcode}")

    code.append("}")
    code.append("")
    code.append("-- Decompile function")
    code.append("local function decompile(bytecode, constants)")
    code.append("    local output = {}")
    code.append("    local pc = 1")
    code.append("    ")
    code.append("    while pc <= #bytecode do")
    code.append("        local instr = bytecode[pc]")
    code.append("        local op = instr & 0xFF  -- Extract opcode")
    code.append("        local A = (instr >> 8) & 0xFF")
    code.append("        local B = (instr >> 16) & 0xFF")
    code.append("        local C = (instr >> 24) & 0xFF")
    code.append("        ")
    code.append("        local op_name = opcodes[op] or 'UNKNOWN'")
    code.append("        table.insert(output, string.format('%d: %s A=%d B=%d C=%d', pc, op_name, A, B, C))")
    code.append("        pc = pc + 1")
    code.append("    end")
    code.append("    ")
    code.append("    return table.concat(output, '\\n')")
    code.append("end")
    code.append("")
    code.append("return { opcodes = opcodes, decompile = decompile }")

    return '\n'.join(code)

def main():
    print("=" * 70)
    print("FINAL LURAPH VM ANALYZER")
    print("=" * 70)
    print()

    # Load E8 body
    print("[*] Loading E8 function body...")
    body = load_e8_body()
    if not body:
        print("[!] Failed to load E8 body")
        return

    print(f"[*] Loaded {len(body)} characters")

    # Parse opcodes
    print("[*] Parsing opcode dispatch tree...")
    opcodes = parse_opcode_tree(body)

    print()
    print("=" * 70)
    print("OPCODE MAP")
    print("=" * 70)

    # Group by operation type
    by_type = defaultdict(list)
    for opcode, op_type in opcodes.items():
        by_type[op_type].append(opcode)

    for op_type in sorted(by_type.keys()):
        codes = sorted(by_type[op_type])
        codes_str = ', '.join(f'0x{c:02X}' for c in codes)
        print(f"{op_type:12s}: {codes_str}")

    print()
    print(f"Total opcodes mapped: {len(opcodes)}")
    print(f"Total operation types: {len(by_type)}")

    # Analyze instruction fields
    print()
    analyze_instruction_fields()

    # Save results
    print()
    print("[*] Saving results...")

    with open('luraph_opcode_map.json', 'w') as f:
        json.dump({f"0x{k:02X}": v for k, v in sorted(opcodes.items())}, f, indent=2)
    print("    -> luraph_opcode_map.json")

    # Generate decompiler skeleton
    skeleton = generate_lua_decompiler_skeleton(opcodes)
    with open('luraph_decompiler_skeleton.lua', 'w') as f:
        f.write(skeleton)
    print("    -> luraph_decompiler_skeleton.lua")

    # Generate documentation
    doc = []
    doc.append("=" * 70)
    doc.append("LURAPH VM OPCODE DOCUMENTATION")
    doc.append("=" * 70)
    doc.append("")
    doc.append(f"Total opcodes: {len(opcodes)}")
    doc.append(f"Total operation types: {len(by_type)}")
    doc.append("")
    doc.append("OPERATION TYPES:")
    for op_type in sorted(by_type.keys()):
        codes = sorted(by_type[op_type])
        doc.append(f"\n{op_type}:")
        doc.append(f"  Opcodes: {', '.join(f'0x{c:02X}' for c in codes)}")
        doc.append(f"  Count: {len(codes)}")

    with open('luraph_opcode_docs.txt', 'w') as f:
        f.write('\n'.join(doc))
    print("    -> luraph_opcode_docs.txt")

    return opcodes

if __name__ == "__main__":
    main()
