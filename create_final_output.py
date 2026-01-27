#!/usr/bin/env python3
"""
Create final deobfuscated output with full analysis
"""

import re
import json

def format_lua_code(code):
    """Format Lua code with proper indentation"""
    # Add newlines at logical points
    code = re.sub(r';(?!\s*$)', ';\n', code)
    code = re.sub(r'\bfunction\(', '\nfunction(', code)
    code = re.sub(r',(\w+)=', r',\n\1=', code)
    code = re.sub(r'\bend,', 'end,\n', code)
    code = re.sub(r'\bend;', 'end;\n', code)

    lines = code.split('\n')
    result = []
    indent = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Decrease indent for end, else, elseif, until
        if re.match(r'^(end|else|elseif|until)', line):
            indent = max(0, indent - 1)

        result.append('    ' * indent + line)

        # Increase indent after function, if, while, for, repeat, do
        if re.search(r'\b(function|if|while|for|repeat)\b.*then\s*$', line):
            indent += 1
        elif re.search(r'\bdo\s*$', line):
            indent += 1
        elif re.search(r'\bfunction\s*\([^)]*\)\s*$', line):
            indent += 1

        # Handle end keyword
        if line.strip() in ['end', 'end,', 'end;']:
            indent = max(0, indent - 1)

    return '\n'.join(result)


def extract_all_strings(code):
    """Extract all string literals"""
    strings = set()

    # Double quoted
    for m in re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', code):
        s = m.group(1)
        if s and len(s) > 2:
            strings.add(s)

    # Single quoted
    for m in re.finditer(r"'([^'\\]*(?:\\.[^'\\]*)*)'", code):
        s = m.group(1)
        if s and len(s) > 2:
            strings.add(s)

    return strings


def extract_vm_info(code):
    """Extract VM structure information"""
    info = {
        'handlers': [],
        'entry_point': None,
        'constants': [],
        'opcodes': [],
    }

    # Find handler functions
    for m in re.finditer(r'(\w+)=function\(([^)]*)\)', code):
        info['handlers'].append({
            'name': m.group(1),
            'params': m.group(2)
        })

    # Find entry point
    m = re.search(r'\):(\w+)\(\)\s*\([^)]*\)\s*;?\s*$', code)
    if m:
        info['entry_point'] = m.group(1)

    # Find opcode values (hex numbers in conditionals)
    for m in re.finditer(r'==\s*(0[xX][0-9a-fA-F]+)', code):
        try:
            val = int(m.group(1), 16)
            if val not in info['opcodes']:
                info['opcodes'].append(val)
        except:
            pass

    return info


def main():
    print("[*] Creating final deobfuscated output...")

    with open('deobfuscated.lua', 'r') as f:
        code = f.read()

    # Extract information
    vm_info = extract_vm_info(code)
    strings = extract_all_strings(code)

    # Filter interesting strings (not just encoded data)
    interesting_strings = [s for s in strings
                          if len(s) < 100
                          and not s.startswith('s8W')
                          and not re.match(r'^[!-~]+$', s)  # Not just printable ASCII noise
                          and any(c.isalpha() for c in s)]

    # Create comprehensive output
    output = []
    output.append("--[[")
    output.append("=" * 70)
    output.append("LURAPH v14.5.2 DEOBFUSCATION REPORT")
    output.append("=" * 70)
    output.append("")
    output.append("SUMMARY:")
    output.append(f"  - Original obfuscated size: ~565 KB")
    output.append(f"  - Decompressed VM code size: {len(code)} bytes")
    output.append(f"  - VM handler functions: {len(vm_info['handlers'])}")
    output.append(f"  - VM entry point: {vm_info['entry_point']}")
    output.append(f"  - Unique opcodes found: {len(vm_info['opcodes'])}")
    output.append("")
    output.append("OBFUSCATION LAYERS DECODED:")
    output.append("  1. Base85 string encoding - DECODED")
    output.append("  2. LZMA compression - DECODED")
    output.append("  3. VM bytecode virtualization - EXTRACTED (still encoded)")
    output.append("  4. Control flow obfuscation - VISIBLE in VM structure")
    output.append("")
    output.append("VM HANDLER FUNCTIONS:")
    for h in vm_info['handlers'][:30]:
        output.append(f"  - {h['name']}({h['params']})")
    if len(vm_info['handlers']) > 30:
        output.append(f"  ... and {len(vm_info['handlers']) - 30} more")
    output.append("")
    output.append("OPCODES (sample):")
    for op in sorted(vm_info['opcodes'])[:20]:
        output.append(f"  - 0x{op:04X} ({op})")
    output.append("")
    output.append("GLOBAL REFERENCES DETECTED:")
    globals_in_code = []
    for g in ['table', 'string', 'math', 'bit32', 'coroutine', 'pairs', 'ipairs',
              'pcall', 'unpack', 'select', 'setmetatable', 'getmetatable',
              'rawset', 'rawget', 'next', 'type', 'tostring', 'tonumber',
              'loadstring', 'load', 'error', 'assert', 'tick', 'UDim2']:
        if g in code:
            globals_in_code.append(g)
    output.append(f"  {', '.join(globals_in_code)}")
    output.append("")
    output.append("NOTE: The bytecode embedded in the long strings contains")
    output.append("the actual program logic. Full decompilation requires")
    output.append("understanding the Luraph VM instruction format.")
    output.append("=" * 70)
    output.append("]]--")
    output.append("")
    output.append("-- Decompressed VM Code follows:")
    output.append("")

    # Format and add the code
    formatted_code = format_lua_code(code)
    output.append(formatted_code)

    # Write output
    with open('script_deobfuscated.lua', 'w') as f:
        f.write('\n'.join(output))

    print(f"[*] Written to: script_deobfuscated.lua")
    print(f"[*] Total size: {len(''.join(output))} bytes")

    # Also save analysis as JSON
    analysis = {
        'original_size': 565000,
        'decompressed_size': len(code),
        'vm_handlers': len(vm_info['handlers']),
        'vm_entry_point': vm_info['entry_point'],
        'unique_opcodes': len(vm_info['opcodes']),
        'handler_names': [h['name'] for h in vm_info['handlers']],
        'opcode_values': vm_info['opcodes'][:50],
        'globals_used': globals_in_code,
    }

    with open('deobfuscation_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)

    print(f"[*] Analysis saved to: deobfuscation_analysis.json")


if __name__ == "__main__":
    main()
