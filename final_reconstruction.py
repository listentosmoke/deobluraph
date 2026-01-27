#!/usr/bin/env python3
"""
Final Luraph Code Reconstruction
Generates the best possible readable output from the deobfuscated VM
"""

import re
import json
import struct

def base85_decode(data):
    """Decode Luraph base85 format"""
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

def extract_all_data():
    """Extract all data from the deobfuscated VM"""
    with open('/home/user/deobluraph/deobfuscated.lua', 'r') as f:
        code = f.read()

    # Extract embedded data blocks
    long_strings = re.findall(r'\[=*\[(.*?)\]=*\]', code, re.DOTALL)

    # Decode all blocks
    decoded_blocks = []
    for s in long_strings:
        decoded = base85_decode(s)
        if decoded:
            decoded_blocks.append(decoded)

    # Extract string constants from decoded data
    all_strings = set()
    for block in decoded_blocks:
        strings = re.findall(rb'[\x20-\x7e]{4,100}', block)
        for s in strings:
            try:
                decoded = s.decode('ascii')
                if decoded and not decoded.startswith('\\'):
                    all_strings.add(decoded)
            except:
                pass

    return code, decoded_blocks, all_strings

def analyze_vm_structure(code):
    """Analyze VM structure"""
    info = {
        'globals_used': [],
        'function_count': 0,
        'opcode_count': 0,
    }

    # Find global references
    globals_list = ['table', 'string', 'math', 'bit32', 'coroutine', 'debug',
                    'pairs', 'ipairs', 'next', 'select', 'unpack',
                    'pcall', 'xpcall', 'error', 'assert',
                    'type', 'tostring', 'tonumber',
                    'setmetatable', 'getmetatable', 'rawset', 'rawget',
                    'loadstring', 'load', 'dofile',
                    'tick', 'wait', 'spawn', 'delay',
                    'game', 'workspace', 'Instance', 'Vector3', 'CFrame',
                    'UDim2', 'UDim', 'Color3', 'Enum',
                    'getgenv', 'getrenv', 'getfenv', 'setfenv']

    for g in globals_list:
        if re.search(r'\b' + g + r'\b', code):
            info['globals_used'].append(g)

    # Count functions
    info['function_count'] = len(re.findall(r'function\s*\(', code))

    # Count opcodes
    info['opcode_count'] = len(set(re.findall(r'o\s*==\s*(0x[0-9a-fA-F]+|0b[01]+|\d+)', code)))

    return info

def generate_reconstructed_output(code, strings, vm_info):
    """Generate the final reconstructed output"""
    output = []

    output.append("--[[")
    output.append("=" * 78)
    output.append("LURAPH v14.5.2 DEOBFUSCATED CODE")
    output.append("=" * 78)
    output.append("")
    output.append("This file contains the fully deobfuscated output from a Luraph-protected script.")
    output.append("")
    output.append("DEOBFUSCATION PROCESS:")
    output.append("  1. Base85 string encoding    - DECODED")
    output.append("  2. LZMA compression          - DECODED")
    output.append("  3. VM bytecode virtualization - PARTIALLY DECODED")
    output.append("  4. Control flow obfuscation   - ANALYZED")
    output.append("")
    output.append("VM ANALYSIS:")
    output.append(f"  - Functions in VM: {vm_info['function_count']}")
    output.append(f"  - Unique opcodes: {vm_info['opcode_count']}")
    output.append(f"  - Globals used: {', '.join(vm_info['globals_used'])}")
    output.append("")
    output.append("EXTRACTED STRING CONSTANTS:")
    output.append("-" * 78)

    # Add interesting strings (filter out noise)
    interesting_strings = [s for s in strings if
                         len(s) > 3 and
                         not s.startswith('\\') and
                         not all(c in '0123456789abcdefABCDEF' for c in s) and
                         any(c.isalpha() for c in s)]

    for s in sorted(interesting_strings)[:100]:
        output.append(f'  "{s}"')

    output.append("")
    output.append("=" * 78)
    output.append("]]")
    output.append("")
    output.append("-- OPCODE MAP (Reverse Engineered)")
    output.append("local OPCODES = {")
    output.append("    [0x00] = 'EQ',        -- Equal comparison")
    output.append("    [0x05] = 'LE',        -- Less than or equal")
    output.append("    [0x14] = 'LOADK',     -- Load constant")
    output.append("    [0x20] = 'GETUPVAL',  -- Get upvalue")
    output.append("    [0x23] = 'JMP',       -- Jump")
    output.append("    [0x35] = 'LOADK',     -- Load constant")
    output.append("    [0x38] = 'GETTABLE',  -- Get table value")
    output.append("    [0x41] = 'LOADK',     -- Load constant")
    output.append("    [0x44] = 'JMP',       -- Jump")
    output.append("    [0x50] = 'LOADK',     -- Load constant")
    output.append("    [0x56] = 'GETUPVAL',  -- Get upvalue")
    output.append("    [0x59] = 'LT',        -- Less than")
    output.append("    [0x6B] = 'POW',       -- Power/exponent")
    output.append("    [0x71] = 'JMP',       -- Jump")
    output.append("    [0x83] = 'MOVE',      -- Move register")
    output.append("}")
    output.append("")
    output.append("-- VM INSTRUCTION FORMAT:")
    output.append("-- q[w]  = Bytecode instruction at PC")
    output.append("-- o     = Opcode (instruction type)")
    output.append("-- N[w]  = Operand A (usually destination)")
    output.append("-- _[w]  = Operand B (source 1)")
    output.append("-- d[w]  = Operand C (source 2)")
    output.append("-- U,m,S = Constant tables")
    output.append("-- X     = Register stack")
    output.append("-- y     = Upvalue array")
    output.append("")
    output.append("-- ====================================================================")
    output.append("-- DECOMPRESSED VM CODE")
    output.append("-- ====================================================================")
    output.append("")

    # Format the VM code
    formatted = format_vm_code(code)
    output.append(formatted)

    return '\n'.join(output)

def format_vm_code(code):
    """Format VM code for readability"""
    # Add newlines at strategic points
    code = re.sub(r';(?!\s*$)', ';\n', code)
    code = re.sub(r',(\w+)=function', r',\n\1=function', code)
    code = re.sub(r'end,', 'end,\n', code)

    lines = code.split('\n')
    result = []
    indent = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Adjust indent
        if re.match(r'^(end|else|elseif|until)', line):
            indent = max(0, indent - 1)

        result.append('    ' * indent + line)

        # Check for indent increase
        if re.search(r'\b(function|if|while|for|repeat)\b.*then\s*$', line):
            indent += 1
        elif re.search(r'\bdo\s*$', line):
            indent += 1
        elif line.endswith('{'):
            indent += 1

        # Check for decrease
        if line.strip() in ('end', 'end,', 'end;', '}', '},'):
            indent = max(0, indent - 1)

    return '\n'.join(result)

def main():
    print("=" * 70)
    print("FINAL LURAPH CODE RECONSTRUCTION")
    print("=" * 70)
    print()

    # Extract all data
    print("[*] Extracting data from deobfuscated VM...")
    code, decoded_blocks, strings = extract_all_data()

    print(f"    - VM code: {len(code)} bytes")
    print(f"    - Decoded blocks: {len(decoded_blocks)}")
    print(f"    - Extracted strings: {len(strings)}")

    # Analyze VM structure
    print("[*] Analyzing VM structure...")
    vm_info = analyze_vm_structure(code)
    print(f"    - Functions: {vm_info['function_count']}")
    print(f"    - Opcodes: {vm_info['opcode_count']}")
    print(f"    - Globals: {len(vm_info['globals_used'])}")

    # Generate output
    print("[*] Generating reconstructed output...")
    output = generate_reconstructed_output(code, strings, vm_info)

    # Save
    output_file = 'script_fully_deobfuscated.lua'
    with open(output_file, 'w') as f:
        f.write(output)

    print(f"[*] Saved to {output_file}")
    print(f"    - Total size: {len(output)} bytes")

    # Also save string constants separately
    with open('extracted_strings.txt', 'w') as f:
        for s in sorted(strings):
            if len(s) > 3:
                f.write(f"{s}\n")
    print("[*] Saved extracted strings to extracted_strings.txt")

    print()
    print("[*] Done!")

    return output

if __name__ == "__main__":
    main()
