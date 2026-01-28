#!/usr/bin/env python3
"""
Extract and analyze strings from Luraph bytecode to understand the protected script.
"""

import re
import struct
from collections import Counter


def base85_decode(s: str) -> bytes:
    """Decode Luraph base85 (z = !!!!! shorthand)."""
    s = s.replace('z', '!!!!!')
    result = bytearray()
    i = 0
    while i + 5 <= len(s):
        chunk = s[i:i+5]
        try:
            vals = [ord(c) - 33 for c in chunk]
            val = vals[4] + vals[3]*85 + vals[2]*7225 + vals[1]*614125 + vals[0]*52200625
            result.extend(struct.pack('>I', val))
        except:
            pass
        i += 5
    return bytes(result)


def extract_strings_from_bytes(data: bytes, min_length: int = 4) -> list:
    """Extract printable strings from binary data."""
    strings = []
    current = []

    for i, b in enumerate(data):
        if 32 <= b <= 126:  # Printable ASCII
            current.append(chr(b))
        else:
            if len(current) >= min_length:
                s = ''.join(current)
                # Filter out obvious garbage
                if not s.replace('.', '').replace('_', '').isdigit():
                    strings.append(s)
            current = []

    # Don't forget the last string
    if len(current) >= min_length:
        s = ''.join(current)
        if not s.replace('.', '').replace('_', '').isdigit():
            strings.append(s)

    return strings


def categorize_string(s: str) -> str:
    """Categorize a string based on its content."""
    s_lower = s.lower()

    # Roblox APIs
    if any(x in s_lower for x in ['game:', 'workspace', 'player', 'character', 'humanoid',
                                   'getservice', 'findchild', 'waitforchild', 'instance',
                                   'cframe', 'vector3', 'udim2', 'color3', 'enum']):
        return 'ROBLOX_API'

    # Network/HTTP
    if any(x in s_lower for x in ['http', 'https', 'request', 'webhook', 'discord',
                                   'api', 'post', 'get', 'url', 'endpoint']):
        return 'NETWORK'

    # UI elements
    if any(x in s_lower for x in ['gui', 'frame', 'textlabel', 'textbutton', 'imagebutton',
                                   'screengui', 'localscript', 'uicorner', 'uilayout']):
        return 'UI'

    # Exploit-related
    if any(x in s_lower for x in ['getgenv', 'getrenv', 'hookfunction', 'getrawmetatable',
                                   'setreadonly', 'getupvalue', 'getconstants', 'getinfo',
                                   'iscclosure', 'islclosure', 'drawing', 'syn', 'krnl']):
        return 'EXPLOIT_API'

    # Events
    if any(x in s_lower for x in ['.connect', ':connect', 'event', 'signal', 'fired',
                                   'bindable', 'remote']):
        return 'EVENTS'

    # Game logic
    if any(x in s_lower for x in ['damage', 'health', 'speed', 'teleport', 'esp', 'aimbot',
                                   'noclip', 'fly', 'infinite', 'bypass', 'anticheat']):
        return 'GAME_HACK'

    # Likely identifiers
    if re.match(r'^[A-Z][a-zA-Z0-9_]+$', s) and len(s) > 3:
        return 'IDENTIFIER'

    # Common Lua keywords/functions
    if s in ['function', 'local', 'return', 'if', 'then', 'else', 'elseif', 'end',
             'for', 'while', 'repeat', 'until', 'do', 'break', 'and', 'or', 'not',
             'true', 'false', 'nil', 'print', 'pairs', 'ipairs', 'tostring', 'tonumber',
             'type', 'pcall', 'xpcall', 'error', 'assert', 'require', 'loadstring']:
        return 'LUA_KEYWORD'

    return 'OTHER'


def main():
    print("=== Luraph Bytecode String Analyzer ===\n")

    # Read the VM code
    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        vm_code = f.read()

    print(f"VM code size: {len(vm_code)} bytes")

    # Extract all base85 encoded segments
    all_bytecode = bytearray()
    segments = []

    # Find [=[...]=] strings
    pos = 0
    while True:
        start = vm_code.find('[=[', pos)
        if start == -1:
            break
        end = vm_code.find(']=]', start + 3)
        if end == -1:
            break

        content = vm_code[start+3:end].replace('\n', '').replace('\r', '').replace(' ', '')
        if len(content) > 50:
            decoded = base85_decode(content)
            if len(decoded) > 20:
                segments.append(decoded)
                all_bytecode.extend(decoded)

        pos = end + 3

    print(f"Found {len(segments)} bytecode segments")
    print(f"Total decoded bytecode: {len(all_bytecode)} bytes\n")

    # Extract strings from bytecode
    all_strings = extract_strings_from_bytes(bytes(all_bytecode))

    # Deduplicate and count
    string_counts = Counter(all_strings)

    # Categorize strings
    categories = {}
    for s in string_counts.keys():
        cat = categorize_string(s)
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((s, string_counts[s]))

    # Print results by category
    print("=" * 60)
    print("STRINGS BY CATEGORY")
    print("=" * 60)

    category_order = ['ROBLOX_API', 'EXPLOIT_API', 'NETWORK', 'GAME_HACK',
                      'UI', 'EVENTS', 'IDENTIFIER', 'LUA_KEYWORD', 'OTHER']

    for cat in category_order:
        if cat in categories:
            strings = sorted(categories[cat], key=lambda x: -x[1])
            print(f"\n=== {cat} ({len(strings)} strings) ===")
            for s, count in strings[:50]:  # Limit output
                if len(s) > 70:
                    s = s[:70] + "..."
                print(f"  [{count:3d}x] {s}")
            if len(strings) > 50:
                print(f"  ... and {len(strings) - 50} more")

    # Look for specific interesting patterns
    print("\n" + "=" * 60)
    print("INTERESTING PATTERNS")
    print("=" * 60)

    # Find URLs
    url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
    urls = set()
    for s in all_strings:
        matches = url_pattern.findall(s)
        urls.update(matches)

    if urls:
        print("\n=== URLs Found ===")
        for url in sorted(urls):
            print(f"  {url}")

    # Find function-like patterns
    print("\n=== Potential Function Names ===")
    func_pattern = re.compile(r'^[a-z][a-zA-Z0-9_]*$')
    potential_funcs = [s for s in all_strings if func_pattern.match(s) and 3 < len(s) < 30]
    for s in sorted(set(potential_funcs))[:100]:
        print(f"  {s}")

    # Save full string list
    output_file = '/home/user/deobluraph/extracted_strings.txt'
    with open(output_file, 'w') as f:
        f.write("=== All Extracted Strings from Luraph Bytecode ===\n\n")
        for cat in category_order:
            if cat in categories:
                f.write(f"\n=== {cat} ===\n")
                for s, count in sorted(categories[cat], key=lambda x: -x[1]):
                    f.write(f"[{count}x] {s}\n")

    print(f"\nFull string list saved to: {output_file}")
    print(f"\nTotal unique strings found: {len(string_counts)}")


if __name__ == '__main__':
    main()
