#!/usr/bin/env python3
"""
Minimal conversion of Luau VM to standard Lua.
Only fix what's absolutely necessary.
"""

import re
import sys


def minimal_convert(code: str) -> str:
    """Convert Luau to Lua with minimal changes."""

    # 1. Fix number underscores (0x1F_68 -> 0x1F68, 0x7A_ -> 0x7A)
    # Match hex numbers with underscores
    code = re.sub(r'(0[Xx])([0-9A-Fa-f_]+)',
                  lambda m: m.group(1) + m.group(2).replace('_', ''), code)

    # Match decimal numbers with underscores
    code = re.sub(r'\b(\d[0-9_]*)\b',
                  lambda m: m.group(1).replace('_', ''), code)

    # 2. Convert binary literals (0B10010 -> 18)
    def bin_to_dec(m):
        try:
            return str(int(m.group(1).replace('_', ''), 2))
        except:
            return m.group(0)
    code = re.sub(r'0[Bb]([01_]+)', bin_to_dec, code)

    # 3. Convert compound assignments
    # This is tricky - need to handle x+=1 -> x=x+1
    # But also I+=1 where I might be used elsewhere

    # Simple variable compound assignments
    # Pattern: word followed by += (not inside a string)
    code = re.sub(r'\b([a-zA-Z_]\w*)\s*\+=\s*', r'\1=\1+', code)
    code = re.sub(r'\b([a-zA-Z_]\w*)\s*-=\s*', r'\1=\1-', code)
    code = re.sub(r'\b([a-zA-Z_]\w*)\s*\*=\s*', r'\1=\1*', code)
    code = re.sub(r'\b([a-zA-Z_]\w*)\s*/=\s*', r'\1=\1/', code)
    code = re.sub(r'\b([a-zA-Z_]\w*)\s*%=\s*', r'\1=\1%', code)
    code = re.sub(r'\b([a-zA-Z_]\w*)\s*\.\.=\s*', r'\1=\1..', code)

    # 4. Replace 'continue' with goto (Lua 5.2+ has goto)
    # Actually, standard Lua doesn't have continue. Let's use a comment for now.
    code = re.sub(r'\bcontinue\s*;', '-- continue;', code)

    # 5. Remove invalid newlines (newlines that break expressions)
    # Find the long string boundaries first - don't touch content inside [=[...]=]
    ls_start = code.find('[=[')
    ls_end = code.find(']=]') + 3 if code.find(']=]') != -1 else len(code)

    if ls_start != -1:
        before = code[:ls_start]
        long_string = code[ls_start:ls_end]
        after = code[ls_end:]

        # Remove ALL newlines from code portions (they're invalid mid-expression)
        before = before.replace('\n', ' ')
        after = after.replace('\n', ' ')

        code = before + long_string + after
    else:
        # No long string, just remove all newlines
        code = code.replace('\n', ' ')

    return code


def main():
    print("Minimal VM conversion...")

    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        code = f.read()

    print(f"Original: {len(code)} bytes, {code.count(chr(10))} newlines")

    converted = minimal_convert(code)

    print(f"Converted: {len(converted)} bytes, {converted.count(chr(10))} newlines")

    # Save
    with open('/home/user/deobluraph/vm_minimal.lua', 'w') as f:
        f.write(converted)

    print("Saved to vm_minimal.lua")

    # Test syntax
    import subprocess
    result = subprocess.run(
        ['lua5.3', '-e', 'local f, e = loadfile("/home/user/deobluraph/vm_minimal.lua"); if not f then print("Error: " .. e) else print("Syntax OK!") end'],
        capture_output=True, text=True
    )
    print(result.stdout.strip())

    if 'Error' in result.stdout:
        # Find the error location
        match = re.search(r':(\d+):', result.stdout)
        if match:
            line_num = int(match.group(1))
            lines = converted.split('\n')
            if 0 < line_num <= len(lines):
                print(f"\nLine {line_num}: {lines[line_num-1][:100]}...")


if __name__ == '__main__':
    main()
