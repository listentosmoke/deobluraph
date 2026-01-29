#!/usr/bin/env python3
"""
Deep analysis of Luraph bytecode format.

This analyzes the bytecode structure by:
1. Reading the deserialization code from the VM
2. Simulating the bytecode parsing
3. Extracting the actual instruction data
"""

import struct
import re
from typing import List, Tuple, Dict, Any


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


class LEB128Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_byte(self) -> int:
        if self.pos >= len(self.data):
            return 0
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_uleb128(self) -> int:
        result = 0
        shift = 0
        while True:
            b = self.read_byte()
            result |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
            if shift > 35:  # Sanity check
                break
        return result

    def read_sleb128(self) -> int:
        result = 0
        shift = 0
        while True:
            b = self.read_byte()
            result |= (b & 0x7F) << shift
            shift += 7
            if (b & 0x80) == 0:
                if b & 0x40:
                    result |= -(1 << shift)
                break
            if shift > 35:
                break
        return result


def analyze_leb128_sequence(data: bytes, max_values: int = 100) -> List[int]:
    """Read a sequence of LEB128 values and return them."""
    reader = LEB128Reader(data)
    values = []
    try:
        for _ in range(max_values):
            if reader.pos >= len(data):
                break
            val = reader.read_uleb128()
            values.append(val)
    except:
        pass
    return values


def find_string_table(data: bytes) -> List[Tuple[int, str]]:
    """Find potential string tables in the bytecode."""
    strings = []
    i = 0

    while i < len(data) - 4:
        # Look for length-prefixed strings
        # Try reading a LEB128 length
        reader = LEB128Reader(data[i:])
        try:
            length = reader.read_uleb128()
            if 1 <= length <= 1000 and i + reader.pos + length <= len(data):
                # Try to read as string
                str_start = i + reader.pos
                str_data = data[str_start:str_start + length]

                # Check if it's printable
                try:
                    s = str_data.decode('utf-8')
                    if all(c.isprintable() or c in '\n\r\t' for c in s):
                        strings.append((i, s))
                        i = str_start + length
                        continue
                except:
                    pass
        except:
            pass
        i += 1

    return strings


def analyze_bytecode_structure(data: bytes):
    """Analyze the overall structure of the bytecode."""
    print(f"Bytecode size: {len(data)} bytes")
    print()

    # First 100 bytes as hex
    print("First 100 bytes:")
    for i in range(0, min(100, len(data)), 16):
        hex_part = ' '.join(f'{b:02X}' for b in data[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
        print(f"  {i:04X}: {hex_part:<48} {ascii_part}")

    print()

    # Try reading as LEB128 values
    print("First 30 LEB128 values:")
    reader = LEB128Reader(data)
    for i in range(30):
        pos = reader.pos
        val = reader.read_uleb128()
        print(f"  [{i:2d}] pos={pos:5d}: {val:10d} (0x{val:X})")

    print()

    # Find potential string tables
    print("Looking for string tables...")
    strings = find_string_table(data)
    print(f"Found {len(strings)} potential strings")

    if strings:
        print("\nFirst 50 strings found:")
        for i, (offset, s) in enumerate(strings[:50]):
            display = s[:60] + "..." if len(s) > 60 else s
            display = display.replace('\n', '\\n').replace('\r', '\\r')
            print(f"  [{i:3d}] @{offset:6d}: \"{display}\"")

    # Look for patterns that might indicate function boundaries
    print("\n\nLooking for function boundaries...")

    # In Luraph, function boundaries might be marked by specific patterns
    # Let's look for sequences that could be function headers

    # Look for small numbers followed by larger numbers (num_params, flags, num_upvalues, num_constants)
    reader = LEB128Reader(data)
    potential_headers = []

    for start_pos in range(0, min(len(data) - 20, 10000), 1):
        reader.pos = start_pos
        try:
            v1 = reader.read_uleb128()  # Could be num_params
            v2 = reader.read_uleb128()  # Could be is_vararg
            v3 = reader.read_uleb128()  # Could be max_stack
            v4 = reader.read_uleb128()  # Could be num_upvalues or num_constants

            # Check if these look like reasonable function header values
            if (0 <= v1 <= 255 and
                0 <= v2 <= 1 and
                0 <= v3 <= 255 and
                0 <= v4 <= 10000):  # num_constants

                # Read what might be num_instructions
                v5 = reader.read_uleb128()

                if 1 <= v5 <= 100000:  # Reasonable instruction count
                    potential_headers.append({
                        'pos': start_pos,
                        'num_params': v1,
                        'is_vararg': v2,
                        'max_stack': v3,
                        'v4': v4,
                        'num_instructions': v5,
                        'next_pos': reader.pos
                    })

        except:
            pass

    print(f"\nFound {len(potential_headers)} potential function headers")
    for h in potential_headers[:20]:
        print(f"  pos={h['pos']:5d}: params={h['num_params']}, vararg={h['is_vararg']}, "
              f"stack={h['max_stack']}, v4={h['v4']}, instructions={h['num_instructions']}")


def main():
    print("=== Luraph Bytecode Format Analyzer ===\n")

    # Read VM code
    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        vm_code = f.read()

    # Extract main bytecode
    bytecode = None
    pos = 0
    while True:
        start = vm_code.find('[=[', pos)
        if start == -1:
            break
        end = vm_code.find(']=]', start + 3)
        if end == -1:
            break

        content = vm_code[start+3:end].replace('\n', '').replace('\r', '').replace(' ', '')
        if len(content) > 100:
            decoded = base85_decode(content)
            if bytecode is None or len(decoded) > len(bytecode):
                bytecode = decoded

        pos = end + 3

    if bytecode:
        print(f"Main bytecode extracted: {len(bytecode)} bytes\n")
        analyze_bytecode_structure(bytecode)

        # Save raw bytecode for further analysis
        with open('/home/user/deobluraph/bytecode_raw.bin', 'wb') as f:
            f.write(bytecode)
        print(f"\nRaw bytecode saved to: /home/user/deobluraph/bytecode_raw.bin")
    else:
        print("No bytecode found!")


if __name__ == '__main__':
    main()
