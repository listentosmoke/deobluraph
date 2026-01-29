#!/usr/bin/env python3
"""
Fix invalid newlines in the VM code and convert Luau syntax to standard Lua.
"""

import re


def fix_newlines_and_convert(code: str) -> str:
    """Fix newlines and convert Luau to standard Lua."""

    # First, join lines that are broken in the middle of expressions
    # A newline is invalid if:
    # - The line ends with an opening bracket, operator, or incomplete expression
    # - The next line starts with a closing bracket, operator, or continuation

    # Simple approach: remove all newlines that occur outside of string literals
    # Then add back proper formatting

    # Actually, the simplest fix is to just remove all newlines since the code is minified anyway
    # But we need to preserve newlines inside long strings [=[...]=]

    # Find the long string
    long_string_start = code.find('[=[')
    long_string_end = code.find(']=]', long_string_start) + 3 if long_string_start != -1 else -1

    if long_string_start != -1:
        before = code[:long_string_start]
        long_string = code[long_string_start:long_string_end]
        after = code[long_string_end:]

        # Remove newlines in before and after, preserve in long_string
        before = before.replace('\n', ' ')
        after = after.replace('\n', ' ')

        code = before + long_string + after
    else:
        code = code.replace('\n', ' ')

    # Now convert Luau syntax to standard Lua

    # Remove underscores from numbers (0x1F_68 -> 0x1F68)
    code = re.sub(r'(0[Xx][0-9A-Fa-f_]+)', lambda m: m.group(1).replace('_', ''), code)
    code = re.sub(r'(\d+)_(\d+)', r'\1\2', code)
    code = re.sub(r'(\d+)_(\d+)', r'\1\2', code)

    # Convert binary literals 0B... to decimal
    def convert_binary(match):
        binary_str = match.group(1).replace('_', '')
        try:
            return str(int(binary_str, 2))
        except:
            return match.group(0)

    code = re.sub(r'0[Bb]([01_]+)', convert_binary, code)

    # Convert compound assignments
    # Handle indexed access: (B)[idx]+= or B[idx]+=
    # These need careful handling to avoid breaking

    # First handle table indexed compound assignments
    # Pattern: (expr)[index] op= value
    # We need to capture the full table access including nested brackets

    # Simple patterns for compound assignments on simple variables
    code = re.sub(r'(\w+)\s*\+=\s*', r'\1=\1+', code)
    code = re.sub(r'(\w+)\s*-=\s*', r'\1=\1-', code)
    code = re.sub(r'(\w+)\s*\*=\s*', r'\1=\1*', code)
    code = re.sub(r'(\w+)\s*/=\s*', r'\1=\1/', code)
    code = re.sub(r'(\w+)\s*%=\s*', r'\1=\1%', code)
    code = re.sub(r'(\w+)\s*\.\.=\s*', r'\1=\1..', code)

    # Replace continue with comment (Lua doesn't have continue)
    code = re.sub(r'\bcontinue\s*;', '-- continue;', code)

    return code


def main():
    print("Fixing VM code...")

    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        code = f.read()

    print(f"Original size: {len(code)} bytes")
    print(f"Original newlines: {code.count(chr(10))}")

    fixed = fix_newlines_and_convert(code)

    print(f"Fixed size: {len(fixed)} bytes")
    print(f"Fixed newlines: {fixed.count(chr(10))}")

    with open('/home/user/deobluraph/vm_fixed.lua', 'w') as f:
        f.write(fixed)

    print(f"Saved to: /home/user/deobluraph/vm_fixed.lua")

    # Test syntax
    print("\nTesting syntax...")
    import subprocess
    result = subprocess.run(
        ['lua5.3', '-e', 'local f, e = loadfile("/home/user/deobluraph/vm_fixed.lua"); if not f then print("Error: " .. e) else print("Syntax OK!") end'],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


if __name__ == '__main__':
    main()
