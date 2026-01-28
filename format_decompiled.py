#!/usr/bin/env python3
"""
Format the decompressed Luraph VM code for readability.
"""

import re

def format_lua(code):
    """Format Lua code with proper indentation."""
    # Add newlines after semicolons and certain keywords
    code = re.sub(r';(?=\S)', ';\n', code)

    # Add newlines around function definitions
    code = re.sub(r'(function\([^)]*\))', r'\n\1', code)
    code = re.sub(r'(end[,;])', r'\1\n', code)

    # Add newlines around control structures
    code = re.sub(r'\b(if\s+)', r'\n\1', code)
    code = re.sub(r'\b(else\b)', r'\n\1', code)
    code = re.sub(r'\b(while\s+)', r'\n\1', code)
    code = re.sub(r'\b(for\s+)', r'\n\1', code)
    code = re.sub(r'\b(repeat\b)', r'\n\1', code)
    code = re.sub(r'\b(until\s+)', r'\n\1', code)
    code = re.sub(r'\b(local\s+)', r'\n\1', code)
    code = re.sub(r'\b(return\s+)', r'\n\1', code)

    # Clean up multiple newlines
    code = re.sub(r'\n{3,}', '\n\n', code)

    # Indent based on braces and keywords
    lines = code.split('\n')
    formatted_lines = []
    indent = 0

    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append('')
            continue

        # Decrease indent before these
        if re.match(r'^(end|else|elseif|until)', line):
            indent = max(0, indent - 1)

        # Add indentation
        formatted_lines.append('    ' * indent + line)

        # Increase indent after these
        if re.search(r'\b(function|then|do|else|repeat)\s*$', line) or line.endswith('{'):
            indent += 1
        # Handle inline function definitions
        if re.search(r'function\([^)]*\)$', line) and not line.strip().startswith('end'):
            indent += 1

    return '\n'.join(formatted_lines)


def extract_functions(code):
    """Extract function definitions from the VM table."""
    functions = {}

    # Pattern for simple function assignments: name=function(...)...end
    # This is a simplified extraction
    pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)=function\('

    for match in re.finditer(pattern, code):
        name = match.group(1)
        start = match.start()

        # Find the matching end
        depth = 0
        pos = match.end()
        func_start = match.start()

        in_string = False
        string_char = None

        while pos < len(code):
            char = code[pos]

            # Handle strings
            if not in_string:
                if char in '"\'':
                    in_string = True
                    string_char = char
                elif code[pos:pos+2] == '[[':
                    in_string = True
                    string_char = ']]'
                    pos += 1
            else:
                if string_char in '"\'':
                    if char == string_char and code[pos-1:pos] != '\\':
                        in_string = False
                elif code[pos:pos+2] == string_char:
                    in_string = False
                    pos += 1

            if not in_string:
                # Check for function/end keywords
                if code[pos:pos+8] == 'function':
                    depth += 1
                elif code[pos:pos+3] == 'end':
                    if depth == 0:
                        # Found the matching end
                        func_code = code[func_start:pos+3]
                        functions[name] = func_code
                        break
                    depth -= 1

            pos += 1

    return functions


def analyze_vm(code):
    """Analyze the VM code structure."""
    analysis = []

    # Count functions
    func_count = len(re.findall(r'function\s*\(', code))
    analysis.append(f"Total functions: {func_count}")

    # Find important patterns
    patterns = {
        'Coroutine usage': r'coroutine\.',
        'Bit operations': r'bit32\.',
        'String operations': r'string\.',
        'Table operations': r'table\.',
        'Math operations': r'math\.',
        'Upvalues': r'upvalue',
        'Debug library': r'debug\.',
        'Loadstring': r'loadstring',
        'Environment': r'getfenv|setfenv|_ENV',
    }

    for name, pattern in patterns.items():
        matches = len(re.findall(pattern, code))
        if matches > 0:
            analysis.append(f"{name}: {matches} occurrences")

    # Find string literals (potential meaningful strings)
    strings = re.findall(r'"([^"]{3,50})"', code)
    unique_strings = set(strings)
    analysis.append(f"\nUnique string literals: {len(unique_strings)}")

    # Show some interesting strings
    interesting = [s for s in unique_strings if not s.startswith('\\') and len(s) > 5]
    if interesting:
        analysis.append("Sample strings:")
        for s in sorted(interesting)[:20]:
            analysis.append(f"  - {s}")

    return '\n'.join(analysis)


# Read the decompressed code
with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
    code = f.read()

print(f"Original code size: {len(code)} bytes")
print()

# Analyze
print("=== VM Analysis ===")
print(analyze_vm(code))
print()

# Format the code
print("Formatting code...")
formatted = format_lua(code)

# Save formatted version
with open('/home/user/deobluraph/decompressed_vm_formatted.lua', 'w') as f:
    f.write(formatted)

print(f"Formatted code saved to: /home/user/deobluraph/decompressed_vm_formatted.lua")
print(f"Formatted size: {len(formatted)} bytes")

# Extract and save individual functions
print("\nExtracting named functions...")
functions = extract_functions(code)
print(f"Found {len(functions)} named functions")

# Show function names
if functions:
    print("\nFunction names found:")
    for name in sorted(functions.keys())[:50]:
        print(f"  - {name}")
    if len(functions) > 50:
        print(f"  ... and {len(functions) - 50} more")
