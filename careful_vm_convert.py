#!/usr/bin/env python3
"""
Carefully convert the VM code preserving long strings and only modifying actual code.
"""

import re


def convert_code_portion(code: str) -> str:
    """Convert Luau syntax in code portion (not strings)."""

    # Remove ALL underscores from numbers (including trailing)
    # First handle hex with underscores anywhere
    def fix_hex(m):
        return m.group(0).replace('_', '')
    code = re.sub(r'0[Xx][0-9A-Fa-f_]+', fix_hex, code)

    # Handle decimal with underscores (including trailing)
    def fix_decimal(m):
        return m.group(0).replace('_', '')
    # Match digit sequences that contain underscores
    code = re.sub(r'\b(\d[0-9_]*)', fix_decimal, code)

    # Convert binary literals
    def convert_binary(m):
        binary_str = m.group(1).replace('_', '')
        try:
            return str(int(binary_str, 2))
        except:
            return m.group(0)

    code = re.sub(r'0[Bb]([01_]+)', convert_binary, code)

    # Convert compound assignments
    # Be very careful not to break things

    # Handle simple variable assignments
    code = re.sub(r'\b(\w+)\s*\+=', r'\1=\1+', code)
    code = re.sub(r'\b(\w+)\s*-=', r'\1=\1-', code)
    code = re.sub(r'\b(\w+)\s*\*=', r'\1=\1*', code)

    # Replace continue
    code = re.sub(r'\bcontinue\s*;', '-- continue;', code)

    return code


def main():
    print("Converting VM code carefully...")

    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        content = f.read()

    print(f"Original size: {len(content)} bytes")

    # Find the long string
    ls_start = content.find('[=[')
    ls_end = content.find(']=]') + 3

    if ls_start == -1 or ls_end == 2:  # -1 + 3 = 2
        print("No long string found!")
        return

    print(f"Long string: {ls_start} to {ls_end} ({ls_end - ls_start} chars)")

    # Split into three parts
    before = content[:ls_start]
    long_string = content[ls_start:ls_end]
    after = content[ls_end:]

    print(f"Before: {len(before)} chars")
    print(f"Long string: {len(long_string)} chars")
    print(f"After: {len(after)} chars")

    # First, join ALL newlines in before and after (but not in long_string)
    before = ' '.join(before.split())  # Normalize whitespace
    after = ' '.join(after.split())

    # Now convert the code portions
    before_converted = convert_code_portion(before)
    after_converted = convert_code_portion(after)

    # Combine
    result = before_converted + long_string + after_converted

    print(f"Result size: {len(result)} bytes")
    print(f"Result newlines: {result.count(chr(10))}")

    # Save
    with open('/home/user/deobluraph/vm_careful.lua', 'w') as f:
        f.write(result)

    print("Saved to vm_careful.lua")

    # Test syntax
    import subprocess
    result_check = subprocess.run(
        ['lua5.3', '-e', 'local f, e = loadfile("/home/user/deobluraph/vm_careful.lua"); if not f then print("Error: " .. e) else print("Syntax OK!") end'],
        capture_output=True,
        text=True
    )
    print(result_check.stdout)
    if result_check.stderr:
        print(result_check.stderr)


if __name__ == '__main__':
    main()
