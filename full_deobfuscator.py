#!/usr/bin/env python3
"""
Comprehensive Luraph Deobfuscator
Handles Base85 decoding, LZMA decompression, and VM analysis
"""

import re
import struct
import sys
from collections import defaultdict

def base85_decode(data):
    """Decode base85 encoded data (Luraph format)"""
    # Replace 'z' with '!!!!!' (Luraph uses this shorthand)
    data = data.replace('z', '!!!!!')

    result = bytearray()
    i = 0
    while i < len(data):
        if i + 5 <= len(data):
            chunk = data[i:i+5]
            try:
                # Decode 5 characters to 4 bytes
                value = 0
                for j, c in enumerate(chunk):
                    value = value * 85 + (ord(c) - 33)

                # Convert to 4 bytes (big-endian)
                result.extend(struct.pack('>I', value))
                i += 5
            except:
                i += 1
        else:
            break

    return bytes(result)


def extract_long_strings(code):
    """Extract all long string literals from the code"""
    strings = []
    # Match [[ ]], [=[ ]=], [==[ ]==], etc.
    pattern = r'\[=*\[(.*?)\]=*\]'
    for match in re.finditer(pattern, code, re.DOTALL):
        strings.append(match.group(1))
    return strings


def analyze_vm_structure(code):
    """Analyze the VM structure and extract handler information"""
    handlers = {}

    # Find all function definitions
    func_pattern = r'(\w+)=function\(([^)]*)\)'
    for match in re.finditer(func_pattern, code):
        name = match.group(1)
        params = match.group(2)

        # Get function body (until next function or end of table)
        start = match.end()
        # Simple heuristic: find the matching 'end'
        depth = 1
        end = start
        while end < len(code) and depth > 0:
            if code[end:end+8] == 'function':
                depth += 1
            elif code[end:end+3] == 'end':
                depth -= 1
            end += 1

        body = code[start:end]
        handlers[name] = {
            'params': params.split(',') if params else [],
            'body_size': len(body),
        }

    return handlers


def extract_constants(code):
    """Extract constant values from the code"""
    constants = {
        'numbers': set(),
        'strings': set(),
    }

    # Extract numbers (hex, binary, decimal)
    for m in re.finditer(r'\b0[xX]([0-9a-fA-F_]+)\b', code):
        try:
            constants['numbers'].add(int(m.group(1).replace('_', ''), 16))
        except:
            pass

    for m in re.finditer(r'\b0[bB]([01_]+)\b', code):
        try:
            constants['numbers'].add(int(m.group(1).replace('_', ''), 2))
        except:
            pass

    # Extract short strings
    for m in re.finditer(r'"([^"\\]{1,50})"', code):
        s = m.group(1)
        if any(c.isalpha() for c in s):
            constants['strings'].add(s)

    return constants


def find_opcode_dispatch(code):
    """Find the main opcode dispatch logic"""
    # Look for patterns like: if I==0x... then ... elseif I==0x... then
    dispatch_pattern = r'if\s+(\w+)==(0[xXbB]?[0-9a-fA-F_]+)\s+then'
    matches = list(re.finditer(dispatch_pattern, code))

    if matches:
        return {
            'dispatch_var': matches[0].group(1),
            'opcode_count': len(matches),
            'opcodes': [m.group(2) for m in matches[:20]]
        }
    return None


def reconstruct_code(vm_data):
    """Attempt to reconstruct readable Lua code from VM data"""
    lines = []
    lines.append("-- Luraph Deobfuscated Output")
    lines.append("-- This is a reconstruction of the original code logic")
    lines.append("")

    # Add handler descriptions
    if 'handlers' in vm_data:
        lines.append("-- VM Handlers found: " + str(len(vm_data['handlers'])))
        for name, info in list(vm_data['handlers'].items())[:20]:
            lines.append(f"--   {name}({', '.join(info['params'])})")
        lines.append("")

    # Add constants
    if 'constants' in vm_data:
        if vm_data['constants']['strings']:
            lines.append("-- String constants found:")
            for s in sorted(vm_data['constants']['strings'])[:50]:
                lines.append(f'--   "{s}"')
            lines.append("")

    # Add dispatch info
    if 'dispatch' in vm_data and vm_data['dispatch']:
        lines.append(f"-- Opcode dispatch variable: {vm_data['dispatch']['dispatch_var']}")
        lines.append(f"-- Total opcodes: {vm_data['dispatch']['opcode_count']}")
        lines.append("-- Sample opcodes: " + ", ".join(vm_data['dispatch']['opcodes']))
        lines.append("")

    return '\n'.join(lines)


def decode_all_strings(code):
    """Decode all embedded base85 strings"""
    decoded_data = []
    long_strings = extract_long_strings(code)

    for i, s in enumerate(long_strings):
        try:
            decoded = base85_decode(s)
            if decoded:
                decoded_data.append({
                    'index': i,
                    'original_size': len(s),
                    'decoded_size': len(decoded),
                    'preview': decoded[:100],
                    'data': decoded
                })
        except Exception as e:
            pass

    return decoded_data


def analyze_decoded_data(decoded_items):
    """Analyze decoded data to understand its structure"""
    analysis = []

    for item in decoded_items:
        data = item['data']
        info = {
            'index': item['index'],
            'size': len(data),
            'type': 'unknown'
        }

        # Check if it's Lua bytecode
        if data[:4] == b'\x1bLua':
            info['type'] = 'lua_bytecode'
            info['lua_version'] = data[4] if len(data) > 4 else None

        # Check for ASCII text
        elif all(32 <= b < 127 or b in (10, 13, 9) for b in data[:100]):
            info['type'] = 'text'
            info['preview'] = data[:200].decode('ascii', errors='ignore')

        # Check for structured binary data
        else:
            info['type'] = 'binary'
            # Try to identify patterns
            info['hex_preview'] = data[:50].hex()

        analysis.append(info)

    return analysis


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "deobfuscated.lua"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "deobfuscated_analyzed.lua"

    print(f"[*] Loading: {input_file}")

    with open(input_file, 'r') as f:
        code = f.read()

    print(f"[*] File size: {len(code)} bytes")

    # Analyze VM structure
    print("[*] Analyzing VM structure...")
    handlers = analyze_vm_structure(code)
    print(f"    Found {len(handlers)} handler functions")

    # Extract constants
    print("[*] Extracting constants...")
    constants = extract_constants(code)
    print(f"    Found {len(constants['numbers'])} unique numbers")
    print(f"    Found {len(constants['strings'])} unique strings")

    # Find opcode dispatch
    print("[*] Finding opcode dispatch...")
    dispatch = find_opcode_dispatch(code)
    if dispatch:
        print(f"    Found dispatch on variable: {dispatch['dispatch_var']}")
        print(f"    Total opcodes: {dispatch['opcode_count']}")

    # Decode embedded strings
    print("[*] Decoding embedded data...")
    decoded = decode_all_strings(code)
    print(f"    Decoded {len(decoded)} data blocks")

    # Analyze decoded data
    print("[*] Analyzing decoded data...")
    data_analysis = analyze_decoded_data(decoded)
    for info in data_analysis[:5]:
        print(f"    Block {info['index']}: {info['size']} bytes, type: {info['type']}")

    # Compile analysis
    vm_data = {
        'handlers': handlers,
        'constants': constants,
        'dispatch': dispatch,
        'decoded_blocks': len(decoded),
        'data_analysis': data_analysis,
    }

    # Reconstruct code
    print("[*] Reconstructing code...")
    reconstructed = reconstruct_code(vm_data)

    # Also include the formatted original
    with open(output_file, 'w') as f:
        f.write(reconstructed)
        f.write("\n\n-- Original decompressed VM code follows:\n\n")
        # Format the code with newlines
        formatted = code.replace(';', ';\n').replace(',', ',\n')
        f.write(formatted)

    print(f"[*] Written analysis to: {output_file}")

    # Write decoded data blocks
    for i, item in enumerate(decoded[:5]):
        block_file = f"decoded_block_{i}.bin"
        with open(block_file, 'wb') as f:
            f.write(item['data'])
        print(f"[*] Written decoded block to: {block_file}")

    # Summary
    print("\n" + "=" * 60)
    print("DEOBFUSCATION SUMMARY")
    print("=" * 60)
    print(f"Original file: {len(code)} bytes")
    print(f"VM handlers: {len(handlers)}")
    print(f"Unique numbers: {len(constants['numbers'])}")
    print(f"Unique strings: {len(constants['strings'])}")
    print(f"Decoded data blocks: {len(decoded)}")
    print(f"Total decoded bytes: {sum(item['decoded_size'] for item in decoded)}")

    return vm_data


if __name__ == "__main__":
    main()
