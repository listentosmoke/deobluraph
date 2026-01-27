#!/usr/bin/env python3
"""
Lua code formatter - adds proper indentation and newlines
"""

import re
import sys

def format_lua(code):
    """Format Lua code with proper indentation and structure"""

    # First, let's normalize some patterns
    result = []
    indent = 0
    in_string = False
    string_char = None
    i = 0
    current_line = ""

    # Keywords that increase indent
    increase_indent = ['function', 'if', 'while', 'for', 'repeat', 'do', '{']
    decrease_indent = ['end', 'until', '}']

    # Add newlines after certain patterns
    code = re.sub(r';(?!\s*$)', ';\n', code)
    code = re.sub(r'\bdo\b(?!\s*\n)', 'do\n', code)
    code = re.sub(r'\bthen\b(?!\s*\n)', 'then\n', code)
    code = re.sub(r'\belse\b(?!\s*\n)', 'else\n', code)
    code = re.sub(r'\bend\b', '\nend', code)
    code = re.sub(r'\{', '{\n', code)
    code = re.sub(r'\}', '\n}', code)
    code = re.sub(r',\s*(\w+\s*=)', r',\n\1', code)

    lines = code.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for indent decrease
        temp_indent = indent
        for kw in decrease_indent:
            if line.startswith(kw) or line == kw:
                temp_indent = max(0, indent - 1)
                break

        result.append('    ' * temp_indent + line)

        # Check for indent increase
        for kw in increase_indent:
            if kw in line and 'end' not in line:
                indent += 1
                break

        # Check for indent decrease for next line
        for kw in decrease_indent:
            if line.endswith(kw) or line == kw:
                indent = max(0, indent - 1)
                break

    return '\n'.join(result)


def simple_format(code):
    """Simple formatting: just add newlines at sensible points"""
    # Add newlines after semicolons
    code = re.sub(r';', ';\n', code)
    # Add newlines around functions
    code = re.sub(r'(function\([^)]*\))', r'\n\1\n', code)
    # Add newlines around end
    code = re.sub(r'\bend\b', r'\nend\n', code)
    # Add newlines around braces
    code = re.sub(r'\{', r'{\n', code)
    code = re.sub(r'\}', r'\n}\n', code)
    # Add newlines around key=value pairs in tables
    code = re.sub(r',(\s*)(\w+)(\s*)=', r',\n\2=', code)
    # Clean up multiple newlines
    code = re.sub(r'\n{3,}', '\n\n', code)
    return code


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "deobfuscated.lua"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "deobfuscated_formatted.lua"

    with open(input_file, 'r') as f:
        code = f.read()

    formatted = simple_format(code)

    with open(output_file, 'w') as f:
        f.write(formatted)

    print(f"Formatted {len(code)} bytes -> {len(formatted)} bytes")
    print(f"Output: {output_file}")
