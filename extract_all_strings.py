#!/usr/bin/env python3
"""
Extract all readable strings from the Luraph bytecode and VM.
"""

import struct
import re


def base85_decode(s: str) -> bytes:
    """Decode Luraph base85."""
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


def read_leb128(data: bytes, pos: int) -> tuple:
    """Read LEB128 value and return (value, new_pos)."""
    result = 0
    mult = 1
    while pos < len(data):
        b = data[pos]
        pos += 1
        if b > 127:
            result += (b - 128) * mult
        else:
            result += b * mult
            break
        mult *= 128
    return result, pos


def find_strings_in_bytes(data: bytes, min_length=4) -> list:
    """Find all printable string sequences."""
    strings = []
    current = bytearray()
    start_pos = 0

    for i, b in enumerate(data):
        if 32 <= b < 127 or b in (9, 10, 13):  # printable or whitespace
            if len(current) == 0:
                start_pos = i
            current.append(b)
        else:
            if len(current) >= min_length:
                try:
                    s = bytes(current).decode('utf-8')
                    strings.append((start_pos, s))
                except:
                    pass
            current = bytearray()

    if len(current) >= min_length:
        try:
            s = bytes(current).decode('utf-8')
            strings.append((start_pos, s))
        except:
            pass

    return strings


def find_leb128_strings(data: bytes) -> list:
    """Find length-prefixed strings using LEB128 length."""
    strings = []
    i = 0

    while i < len(data) - 4:
        try:
            length, pos = read_leb128(data, i)
            if 3 <= length <= 500 and pos + length <= len(data):
                str_data = data[pos:pos + length]
                # Check if printable
                if all(32 <= b < 127 or b in (9, 10, 13) for b in str_data):
                    try:
                        s = str_data.decode('utf-8')
                        strings.append((i, length, s))
                        i = pos + length
                        continue
                    except:
                        pass
        except:
            pass
        i += 1

    return strings


def extract_vm_string_constants():
    """Extract string constants from the VM code itself."""
    with open('/home/user/deobluraph/decompressed_vm.lua', 'r', errors='replace') as f:
        vm_code = f.read()

    # Find quoted strings
    quoted = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', vm_code)
    quoted += re.findall(r"'([^'\\]*(?:\\.[^'\\]*)*)'", vm_code)

    # Filter for interesting ones
    interesting = []
    for s in quoted:
        s = s.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
        if len(s) >= 3 and not s.startswith('0') and not all(c in '0123456789ABCDEFabcdef' for c in s):
            if not re.match(r'^[0-9X]+$', s):
                interesting.append(s)

    return list(set(interesting))


def main():
    print("=== Extracting Strings from Luraph Bytecode ===\n")

    # Read bytecode
    with open('/home/user/deobluraph/bytecode_raw.bin', 'rb') as f:
        bytecode = f.read()

    print(f"Bytecode size: {len(bytecode)} bytes\n")

    # Find raw strings
    print("=== Raw Printable Strings (min 6 chars) ===")
    raw_strings = find_strings_in_bytes(bytecode, min_length=6)
    print(f"Found {len(raw_strings)} raw strings\n")

    # Filter for meaningful strings (not just repeated chars)
    meaningful = []
    for pos, s in raw_strings:
        # Skip if all same char or too repetitive
        if len(set(s)) > 2:
            meaningful.append((pos, s))

    print(f"Meaningful raw strings: {len(meaningful)}")
    for pos, s in meaningful[:100]:
        display = s[:80] + "..." if len(s) > 80 else s
        display = display.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        print(f"  @{pos:6d}: {display}")

    # Find LEB128-prefixed strings
    print("\n\n=== LEB128 Length-Prefixed Strings ===")
    leb_strings = find_leb128_strings(bytecode)
    print(f"Found {len(leb_strings)} LEB128-prefixed strings\n")

    for pos, length, s in leb_strings[:100]:
        display = s[:80] + "..." if len(s) > 80 else s
        display = display.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        print(f"  @{pos:6d} (len={length:3d}): {display}")

    # Extract from VM code
    print("\n\n=== String Constants from VM Code ===")
    vm_strings = extract_vm_string_constants()
    print(f"Found {len(vm_strings)} unique string constants\n")

    # Sort by length and show interesting ones
    vm_strings.sort(key=len, reverse=True)
    for s in vm_strings[:50]:
        display = s[:80] + "..." if len(s) > 80 else s
        display = display.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        print(f"  {display}")

    # Look for patterns that might indicate data structure
    print("\n\n=== Byte Pattern Analysis ===")

    # Count byte frequencies
    freq = {}
    for b in bytecode:
        freq[b] = freq.get(b, 0) + 1

    # Most common bytes
    print("Most common bytes:")
    sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    for b, count in sorted_freq[:20]:
        pct = 100 * count / len(bytecode)
        print(f"  0x{b:02X} ({chr(b) if 32 <= b < 127 else '.'}) : {count:6d} ({pct:.2f}%)")

    # Look for repeating 4-byte patterns
    print("\n4-byte pattern analysis:")
    patterns = {}
    for i in range(0, len(bytecode) - 3, 4):
        p = bytecode[i:i+4]
        patterns[p] = patterns.get(p, 0) + 1

    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
    print(f"Total unique 4-byte patterns: {len(patterns)}")
    print("Most common:")
    for p, count in sorted_patterns[:20]:
        val = struct.unpack('>I', p)[0]
        val_le = struct.unpack('<I', p)[0]
        print(f"  {p.hex()} (BE={val:10d}, LE={val_le:10d}): {count}")

    # Save all strings to file
    with open('/home/user/deobluraph/extracted_strings.txt', 'w') as f:
        f.write("=== Raw Strings ===\n")
        for pos, s in meaningful:
            f.write(f"@{pos}: {s}\n")
        f.write("\n=== LEB128 Strings ===\n")
        for pos, length, s in leb_strings:
            f.write(f"@{pos} (len={length}): {s}\n")
        f.write("\n=== VM String Constants ===\n")
        for s in vm_strings:
            f.write(f"{s}\n")

    print(f"\nAll strings saved to: /home/user/deobluraph/extracted_strings.txt")


if __name__ == '__main__':
    main()
