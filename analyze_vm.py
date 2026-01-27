#!/usr/bin/env python3
"""
Luraph VM Analyzer and Deobfuscator
Analyzes the VM structure and extracts meaningful content
"""

import re
import sys
import json
from collections import defaultdict

def extract_strings(code):
    """Extract all string literals from the code"""
    strings = set()

    # Match various string patterns
    patterns = [
        r'"([^"\\]*(?:\\.[^"\\]*)*)"',  # Double quoted
        r"'([^'\\]*(?:\\.[^'\\]*)*)'",  # Single quoted
        r'\[=*\[(.*?)\]=*\]',  # Long strings
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, code, re.DOTALL):
            s = match.group(1) if match.lastindex else match.group(0)
            if s and len(s) > 1:
                strings.add(s)

    return strings


def extract_numbers(code):
    """Extract all numeric constants"""
    numbers = set()

    # Hex numbers
    for match in re.finditer(r'0[xX][0-9a-fA-F_]+', code):
        try:
            num = int(match.group().replace('_', ''), 16)
            numbers.add(num)
        except:
            pass

    # Binary numbers
    for match in re.finditer(r'0[bB][01_]+', code):
        try:
            num = int(match.group().replace('_', '').replace('0b', '').replace('0B', ''), 2)
            numbers.add(num)
        except:
            pass

    # Decimal numbers
    for match in re.finditer(r'\b(\d+\.?\d*)\b', code):
        try:
            num = float(match.group())
            if num == int(num):
                numbers.add(int(num))
            else:
                numbers.add(num)
        except:
            pass

    return numbers


def extract_function_names(code):
    """Extract function definitions and references"""
    functions = set()

    # Function definitions
    for match in re.finditer(r'(\w+)\s*=\s*function', code):
        functions.add(match.group(1))

    # Method calls
    for match in re.finditer(r':(\w+)\s*\(', code):
        functions.add(match.group(1))

    # Direct calls
    for match in re.finditer(r'(\w+)\s*\(', code):
        functions.add(match.group(1))

    return functions


def extract_global_refs(code):
    """Extract references to global variables/functions"""
    globals_found = set()

    known_globals = [
        'print', 'pairs', 'ipairs', 'type', 'tostring', 'tonumber',
        'string', 'table', 'math', 'bit32', 'coroutine', 'debug',
        'loadstring', 'load', 'pcall', 'xpcall', 'error', 'assert',
        'setmetatable', 'getmetatable', 'rawset', 'rawget',
        'unpack', 'select', 'next', 'require',
        # Roblox specific
        'game', 'workspace', 'Instance', 'Vector3', 'CFrame', 'Color3',
        'UDim2', 'UDim', 'Enum', 'tick', 'wait', 'spawn', 'delay',
        'getgenv', 'getrenv', 'getfenv', 'setfenv',
    ]

    for g in known_globals:
        if re.search(r'\b' + g + r'\b', code):
            globals_found.add(g)

    return globals_found


def extract_vm_handlers(code):
    """Extract VM opcode handlers"""
    handlers = {}

    # Pattern for handler definitions
    pattern = r'(\w+)=function\(([^)]*)\)(.*?)(?=\w+=function|\}[\s,]*\))'

    for match in re.finditer(pattern, code, re.DOTALL):
        name = match.group(1)
        params = match.group(2)
        body = match.group(3)[:500]  # First 500 chars of body
        handlers[name] = {
            'params': params,
            'body_preview': body.strip()
        }

    return handlers


def analyze_control_flow(code):
    """Analyze control flow patterns"""
    patterns = {
        'while_true': len(re.findall(r'while\s+true\s+do', code)),
        'repeat_until': len(re.findall(r'repeat\s+', code)),
        'if_then': len(re.findall(r'if\s+.*?\s+then', code)),
        'for_loop': len(re.findall(r'for\s+\w+\s*=', code)),
        'break': len(re.findall(r'\bbreak\b', code)),
        'continue': len(re.findall(r'\bcontinue\b', code)),
        'return': len(re.findall(r'\breturn\b', code)),
    }
    return patterns


def find_entry_point(code):
    """Find the main entry point"""
    # Look for the pattern at the end: ):functionName()(...)
    match = re.search(r'\):(\w+)\(\)\s*\([^)]*\)\s*;?\s*$', code)
    if match:
        return match.group(1)

    # Alternative: look for return at end
    match = re.search(r'return\s+(\w+)\s*[;\s]*$', code)
    if match:
        return match.group(1)

    return None


def decode_obfuscated_strings(code):
    """Try to decode obfuscated string patterns"""
    decoded = []

    # Look for string.char patterns
    char_patterns = re.findall(r'string\.char\(([^)]+)\)', code)
    for pattern in char_patterns:
        try:
            nums = [int(x.strip()) for x in pattern.split(',') if x.strip().isdigit()]
            if nums:
                s = ''.join(chr(n) for n in nums if 0 <= n < 256)
                if s and len(s) > 1:
                    decoded.append(s)
        except:
            pass

    # Look for hex escape sequences in strings
    hex_strings = re.findall(r'"((?:\\x[0-9a-fA-F]{2})+)"', code)
    for hs in hex_strings:
        try:
            s = bytes.fromhex(hs.replace('\\x', '')).decode('utf-8', errors='ignore')
            if s:
                decoded.append(s)
        except:
            pass

    return decoded


def extract_bytecode_data(code):
    """Extract potential bytecode/data arrays"""
    data_arrays = []

    # Look for large numeric arrays
    array_pattern = r'\{([0-9,\s\-\.xXbB_]+)\}'
    for match in re.finditer(array_pattern, code):
        content = match.group(1)
        if len(content) > 50:  # Only large arrays
            data_arrays.append(content[:200] + '...' if len(content) > 200 else content)

    return data_arrays


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "deobfuscated.lua"

    print(f"[*] Analyzing: {input_file}")

    with open(input_file, 'r') as f:
        code = f.read()

    print(f"[*] File size: {len(code)} bytes")
    print()

    # Analysis
    print("=" * 60)
    print("STRING ANALYSIS")
    print("=" * 60)
    strings = extract_strings(code)
    interesting_strings = [s for s in strings if len(s) > 3 and not s.startswith('0x')]
    print(f"Found {len(strings)} strings, {len(interesting_strings)} interesting")
    for s in sorted(interesting_strings, key=len, reverse=True)[:30]:
        if len(s) < 100:
            print(f"  - {repr(s)}")
    print()

    print("=" * 60)
    print("GLOBAL REFERENCES")
    print("=" * 60)
    globals_found = extract_global_refs(code)
    print(f"Found references to: {', '.join(sorted(globals_found))}")
    print()

    print("=" * 60)
    print("CONTROL FLOW ANALYSIS")
    print("=" * 60)
    cf = analyze_control_flow(code)
    for k, v in cf.items():
        print(f"  {k}: {v}")
    print()

    print("=" * 60)
    print("ENTRY POINT")
    print("=" * 60)
    entry = find_entry_point(code)
    print(f"Main entry function: {entry}")
    print()

    print("=" * 60)
    print("VM HANDLERS (sample)")
    print("=" * 60)
    handlers = extract_vm_handlers(code)
    print(f"Found {len(handlers)} handler functions")
    for name, info in list(handlers.items())[:10]:
        print(f"  {name}({info['params']})")
    print()

    print("=" * 60)
    print("DECODED STRINGS")
    print("=" * 60)
    decoded = decode_obfuscated_strings(code)
    if decoded:
        for s in decoded[:20]:
            print(f"  - {repr(s)}")
    else:
        print("  No decoded strings found")
    print()

    print("=" * 60)
    print("NUMERIC CONSTANTS (sample)")
    print("=" * 60)
    numbers = extract_numbers(code)
    # Filter to interesting numbers
    interesting_nums = [n for n in numbers if isinstance(n, int) and (n > 1000 or n < -1000)]
    print(f"Found {len(numbers)} numbers, {len(interesting_nums)} large constants")
    for n in sorted(interesting_nums)[:20]:
        print(f"  {n} (0x{n:X})" if isinstance(n, int) else f"  {n}")
    print()

    # Write analysis report
    report = {
        'file_size': len(code),
        'string_count': len(strings),
        'interesting_strings': list(interesting_strings)[:50],
        'globals': list(globals_found),
        'control_flow': cf,
        'entry_point': entry,
        'handler_count': len(handlers),
        'handler_names': list(handlers.keys()),
        'decoded_strings': decoded[:50],
        'large_numbers': list(interesting_nums)[:100],
    }

    with open('vm_analysis.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"[*] Analysis saved to vm_analysis.json")


if __name__ == "__main__":
    main()
