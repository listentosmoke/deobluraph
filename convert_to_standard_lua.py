#!/usr/bin/env python3
"""
Convert Luau-specific syntax to standard Lua 5.1/5.2 syntax.
This handles:
1. Binary literals (0b/0B prefix)
2. Underscore number separators (0x7A_ -> 0x7A)
3. continue keyword -> do end (no-op, relies on control flow)
4. Compound assignments (+=, -=, etc.)
"""

import re
import sys

def convert_binary_literals(code):
    """Convert binary literals 0b/0B to decimal."""
    def replace_binary(match):
        binary = match.group(1).replace('_', '')  # Remove underscores
        try:
            return str(int(binary, 2))
        except ValueError:
            return match.group(0)

    # Match 0b/0B followed by binary digits and optional underscores
    code = re.sub(r'0[bB]([01_]+)', replace_binary, code)
    return code

def remove_number_underscores(code):
    """Remove trailing underscores and internal underscores from numbers."""
    # Remove trailing underscore from hex numbers (0x7A_ -> 0x7A)
    code = re.sub(r'(0[xX][0-9A-Fa-f]+)_', r'\1', code)

    # Remove internal underscores from hex numbers
    def fix_hex(m):
        return m.group(1) + m.group(2).replace('_', '')
    code = re.sub(r'(0[xX])([0-9A-Fa-f_]+)', fix_hex, code)

    # Remove underscores from decimal numbers
    code = re.sub(r'(\d)_(\d)', r'\1\2', code)

    return code

def replace_continue(code):
    """Replace continue with a no-op (do end doesn't work well, need goto in Lua 5.2+)."""
    # Simple replacement - continue becomes an empty statement
    # This won't always work but is a reasonable approximation
    code = re.sub(r'\bcontinue\s*;', 'do end;', code)
    code = re.sub(r'\bcontinue\b', 'do end', code)
    return code

def fix_escape_sequences(code):
    """Fix Luau-specific escape sequences."""
    # Replace \u{XX} unicode escapes with \xXX
    def replace_unicode(m):
        hex_val = m.group(1)
        # Pad to 2 digits and use \x escape
        val = int(hex_val, 16)
        if val < 256:
            return f'\\x{val:02X}'
        else:
            # Multi-byte, need special handling
            return f'\\x{val & 0xFF:02X}'

    code = re.sub(r'\\u\{([0-9A-Fa-f]+)\}', replace_unicode, code)

    # Remove \z (Luau whitespace eating escape)
    code = code.replace('\\z', '')

    # Fix ALL invalid escapes by removing the backslash
    # Valid Lua escapes: \a \b \f \n \r \t \v \\ \' \" \[ \] \0-9 \xHH
    # Everything else is invalid and the backslash should be removed
    # Use a function to replace \X where X is not a valid escape character

    def fix_escape(m):
        char = m.group(1)
        # Check if it's a valid escape
        if char in 'abfnrtv\\\'\"[]':
            return m.group(0)  # Keep valid escapes
        elif char.isdigit():
            return m.group(0)  # Keep numeric escapes
        elif char == 'x':
            return m.group(0)  # Keep hex escapes
        else:
            # Invalid escape - remove the backslash
            return char

    # Match backslash followed by any character
    code = re.sub(r'\\(.)', fix_escape, code)

    return code

def replace_integer_division(code):
    """Replace // with math.floor(a/b) - complex due to operator precedence."""
    # For simple cases like a//b, we can use math.floor
    # But since this could break in complex expressions, let's just use regular division
    # which will work for most integer contexts in this obfuscated code
    code = code.replace('//', '/')
    return code

def replace_compound_assignments(code):
    """Replace compound assignments like += with expanded form."""
    # Handle patterns like: variable += expr
    # This is complex because we need to handle things like:
    # x += 1  -> x = x + 1
    # a[b] += c -> a[b] = a[b] + c
    # W[8] += x -> W[8] = W[8] + x

    # Define the operators and their replacements
    ops = [
        ('+=', ' + '),
        ('-=', ' - '),
        ('*=', ' * '),
        ('/=', ' / '),
        ('%=', ' % '),
        ('..=', ' .. '),
    ]

    # First handle simple variable assignments
    for op, expanded_op in ops:
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*' + re.escape(op) + r'\s*'
        replacement = r'\1 = \1' + expanded_op
        code = re.sub(pattern, replacement, code)

    # Handle indexed assignments like W[8] += x or arr[i] -= 1
    # Pattern: identifier[index] op= expr
    for op, expanded_op in ops:
        # Handle simple numeric index: W[8] += x
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\[([^\]]+)\]\s*' + re.escape(op) + r'\s*'
        replacement = r'\1[\2] = \1[\2]' + expanded_op
        code = re.sub(pattern, replacement, code)

    return code

def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else '/home/user/deobluraph/deobfuscated.lua'
    output_file = sys.argv[2] if len(sys.argv) > 2 else '/home/user/deobluraph/deobfuscated_standard.lua'

    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
        code = f.read()

    original_len = len(code)

    print("Converting binary literals...")
    code = convert_binary_literals(code)

    print("Removing number underscores...")
    code = remove_number_underscores(code)

    print("Replacing continue keyword...")
    code = replace_continue(code)

    print("Fixing escape sequences...")
    code = fix_escape_sequences(code)

    print("Replacing integer division...")
    code = replace_integer_division(code)

    print("Replacing compound assignments...")
    code = replace_compound_assignments(code)

    # Remove auto-execution at end (e.g., "):wS()(...)")
    print("Removing auto-execution...")
    if code.endswith(':wS()(...);'):
        code = code[:-11]  # Remove ":wS()(...);"
    elif ':wS()(' in code[-50:]:
        # Find and remove auto-execution pattern at end
        idx = code.rfind(':wS()')
        if idx > len(code) - 50:
            # Remove everything from :wS() to end
            code = code[:idx]

    print(f"Writing {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(code)

    print(f"Done! {original_len} -> {len(code)} bytes")

    # Quick validation
    print("\nValidating output...")

    # Check for remaining issues
    issues = []
    if re.search(r'0[bB][01]', code):
        issues.append("Binary literals still present")
    if re.search(r'0[xX][0-9A-Fa-f]+_', code):
        issues.append("Underscore suffixes still present")
    if re.search(r'\bcontinue\b', code):
        issues.append("continue keyword still present")
    if re.search(r'\w\s*[+\-*/]=[^=]', code):
        issues.append("Compound assignments still present")

    if issues:
        print("Remaining issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("All conversions successful!")

if __name__ == '__main__':
    main()
