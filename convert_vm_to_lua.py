#!/usr/bin/env python3
"""
Convert Luau-specific syntax in the VM to standard Lua 5.3/5.4 syntax.
"""

import re


def convert_to_standard_lua(code: str) -> str:
    """Convert Luau syntax to standard Lua."""

    # Replace compound assignment operators
    # x += y  ->  x = x + y
    # x -= y  ->  x = x - y
    # x *= y  ->  x = x * y
    # etc.

    # Pattern: identifier += expression
    # This is tricky because we need to handle complex LHS

    # First, let's handle simple cases: variable += expr
    def replace_compound(match):
        lhs = match.group(1)
        op = match.group(2)
        rhs = match.group(3)
        return f"{lhs}={lhs}{op}{rhs}"

    # Match: word+= or word-= or word*= etc
    # Be careful with patterns like (B)[0X5]+=1
    patterns = [
        (r'(\w+)\s*\+=\s*', r'\1=\1+'),
        (r'(\w+)\s*-=\s*', r'\1=\1-'),
        (r'(\w+)\s*\*=\s*', r'\1=\1*'),
        (r'(\w+)\s*/=\s*', r'\1=\1/'),
        (r'(\w+)\s*%=\s*', r'\1=\1%'),
        (r'(\w+)\s*\.\.\=\s*', r'\1=\1..'),
    ]

    result = code

    # Also handle indexed access: (B)[idx]+=expr  or B[idx]+=expr
    # This needs more careful handling

    # Match compound assignment with table access
    # Pattern: (var)[index] op= expr or var[index] op= expr
    def replace_indexed_compound(match):
        full_lhs = match.group(1)  # (B)[0X5] or B[0X5]
        op = match.group(2)        # +, -, *, /
        rhs = match.group(3)       # rest of line until ;
        return f"{full_lhs}={full_lhs}{op}{rhs}"

    # Handle (B)[...]+= and B[...]+= patterns
    indexed_patterns = [
        # (var)[index]+=
        (r'(\([^)]+\)\[[^\]]+\])\s*\+=\s*([^;]+)', r'\1=\1+\2'),
        (r'(\([^)]+\)\[[^\]]+\])\s*-=\s*([^;]+)', r'\1=\1-\2'),
        (r'(\([^)]+\)\[[^\]]+\])\s*\*=\s*([^;]+)', r'\1=\1*\2'),
        # var[index]+=
        (r'(\w+\[[^\]]+\])\s*\+=\s*([^;]+)', r'\1=\1+\2'),
        (r'(\w+\[[^\]]+\])\s*-=\s*([^;]+)', r'\1=\1-\2'),
        (r'(\w+\[[^\]]+\])\s*\*=\s*([^;]+)', r'\1=\1*\2'),
    ]

    for pattern, replacement in indexed_patterns:
        result = re.sub(pattern, replacement, result)

    # Simple variable compound assignments
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)

    # Replace 'continue' with Lua-compatible workaround
    # In standard Lua, there's no continue. We'll just remove it for now
    # (This might break some loops, but let's see)
    # Actually, Lua 5.2+ doesn't have continue, but we can try using goto
    # For simplicity, let's convert continue to a no-op that might work
    result = re.sub(r'\bcontinue\b\s*;', '-- continue', result)

    # Remove the leading 'return' if the whole file is wrapped in return({...})
    # Actually, keep it as is - the VM returns a table

    # Handle binary literals 0B... -> convert to decimal
    def convert_binary(match):
        binary_str = match.group(1).replace('_', '')
        try:
            return str(int(binary_str, 2))
        except:
            return match.group(0)

    result = re.sub(r'0[Bb]([01_]+)', convert_binary, result)

    # Handle hex with underscores (valid in Luau, might not work everywhere)
    result = re.sub(r'(0[Xx][0-9A-Fa-f_]+)', lambda m: m.group(1).replace('_', ''), result)

    # Handle decimal with underscores
    result = re.sub(r'(\d+)_(\d+)', r'\1\2', result)
    result = re.sub(r'(\d+)_(\d+)', r'\1\2', result)  # Run twice for multiple underscores

    return result


def main():
    print("Converting VM to standard Lua...")

    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        vm_code = f.read()

    print(f"Original size: {len(vm_code)} bytes")

    converted = convert_to_standard_lua(vm_code)

    print(f"Converted size: {len(converted)} bytes")

    # Save converted
    with open('/home/user/deobluraph/vm_standard_lua.lua', 'w') as f:
        f.write(converted)

    print(f"Saved to: /home/user/deobluraph/vm_standard_lua.lua")

    # Try to load it with Lua to check for syntax errors
    print("\nTesting syntax with lua5.3...")
    import subprocess
    result = subprocess.run(
        ['lua5.3', '-e', f'loadfile("/home/user/deobluraph/vm_standard_lua.lua")'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("Syntax OK!")
    else:
        print(f"Syntax error: {result.stderr[:500]}")

        # Find the first error line
        match = re.search(r':(\d+):', result.stderr)
        if match:
            line_num = int(match.group(1))
            lines = converted.split('\n')
            if 0 < line_num <= len(lines):
                print(f"\nLine {line_num}: {lines[line_num-1][:100]}")
                if line_num > 1:
                    print(f"Line {line_num-1}: {lines[line_num-2][:100]}")


if __name__ == '__main__':
    main()
