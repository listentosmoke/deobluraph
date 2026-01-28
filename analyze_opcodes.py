#!/usr/bin/env python3
"""
Analyze the Luraph VM interpreter to extract opcode mappings.
"""

import re

# Read the decompressed VM
with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
    vm_code = f.read()

# Find E8 function
e8_start = vm_code.find('E8=')
if e8_start == -1:
    print("E8 not found!")
    exit(1)

# Extract a large chunk of the interpreter
e8_code = vm_code[e8_start:e8_start+50000]

# Parse the VM structure from the variable assignments
# W[1] = instructions, W[5] = operandA, W[11] = strings, etc.

print("=== VM DATA STRUCTURE ===")
print("""
From the interpreter:
  W[1]  = I  = Instructions/code array
  W[5]  = _  = Operand A array
  W[11] = S  = String constants
  W[4]  = N  = Operand B array
  W[10] = q  = Opcode array
  W[9]  = U  = Operand C array
  W[7]  = d  = Operand D array
  W[8]  = m  = Operand E array

Runtime:
  X = Registers/stack
  w = Program counter
  y = Upvalues
  H = Open upvalue tracking
""")

# Find all opcode comparisons
# Pattern: o==0x?? or o~=0x?? or o>=0x?? or o<0x??
opcode_pattern = r'o([=<>~!]+)(0[xXbB][0-9a-fA-F_]+|\d+)'
matches = re.findall(opcode_pattern, e8_code)

opcodes_found = set()
for op, val in matches:
    # Normalize the value
    val = val.replace('_', '')
    if val.startswith('0x') or val.startswith('0X'):
        num = int(val, 16)
    elif val.startswith('0b') or val.startswith('0B'):
        num = int(val, 2)
    else:
        num = int(val)
    opcodes_found.add(num)

print("\n=== OPCODES FOUND ===")
for op in sorted(opcodes_found):
    print(f"  0x{op:02X} ({op})")

# Now let's extract what each opcode does by finding the action after the comparison
print("\n=== OPCODE ACTIONS ===")

# More detailed analysis - find patterns like:
# if o==VALUE then ACTION
# o~=VALUE then ACTION (means if o==VALUE, skip this branch)

# Find all comparison blocks
block_pattern = r'if\s+o([=~<>]+)(0[xXbB][0-9a-fA-F_]+|\d+)\s+then\s*([^;]+);'
blocks = re.findall(block_pattern, e8_code)

opcode_actions = {}
for op, val, action in blocks:
    val = val.replace('_', '')
    if val.startswith('0x') or val.startswith('0X'):
        num = int(val, 16)
    elif val.startswith('0b') or val.startswith('0B'):
        num = int(val, 2)
    else:
        num = int(val)

    if op == '==' or op == '~=':
        # Clean up action
        action = action.strip()
        if len(action) > 100:
            action = action[:100] + '...'
        opcode_actions[num] = (op, action)

for op in sorted(opcode_actions.keys()):
    cmp, action = opcode_actions[op]
    symbol = "==" if cmp == "==" else "!="
    print(f"\n  0x{op:02X}: {symbol}")
    print(f"    {action}")

# Look for simpler assignments after else blocks
print("\n=== ANALYZING OPCODE SEMANTICS ===")

# Key patterns to identify:
semantics = {
    'MOVE': r'X\[(\w+)\]\s*=\s*X\[(\w+)\]',
    'LOADK': r'X\[(\w+)\]\s*=\s*S\[(\w+)\]',
    'LOADNIL': r'X\[(\w+)\]\s*=\s*nil',
    'LOADBOOL': r'X\[(\w+)\]\s*=\s*(true|false)',
    'GETUPVAL': r'X\[(\w+)\]\s*=\s*y\[(\w+)\]',
    'GETTABLE': r'X\[(\w+)\]\s*=\s*X\[(\w+)\]\[X\[(\w+)\]\]',
    'SETTABLE': r'X\[(\w+)\]\[X\[(\w+)\]\]\s*=',
    'ADD': r'X\[(\w+)\]\+X\[(\w+)\]',
    'SUB': r'X\[(\w+)\]\-X\[(\w+)\]',
    'MUL': r'X\[(\w+)\]\*X\[(\w+)\]',
    'DIV': r'X\[(\w+)\]/X\[(\w+)\]',
    'CONCAT': r'\.\.X\[(\w+)\]',
    'CALL': r'X\[(\w+)\]\(',
    'RETURN': r'return\s+X\[',
    'FORLOOP': r'for\s+(\w+)\s*=',
    'JMP': r'w\s*=\s*(\w+)\[w\]',
}

print("\nPattern matches in interpreter:")
for name, pattern in semantics.items():
    matches = re.findall(pattern, e8_code)
    if matches:
        print(f"  {name}: {len(matches)} occurrences")
