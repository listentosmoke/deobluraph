#!/usr/bin/env python3
"""
Custom LZMA decoder for Luraph obfuscated bytecode.
This bypasses the slow Lua LZMA implementation by doing decompression in Python.
"""

import re
import struct
import lzma
import io
import sys

def decode_base85(data):
    """Decode Luraph's custom base85 encoding.

    Uses ASCII 33-117 (! to u) as the 85 characters.
    'z' is shorthand for '!!!!!' (0x00000000).
    """
    result = bytearray()
    i = 0

    while i < len(data):
        if data[i] == 'z':
            # z = 4 zero bytes
            result.extend(b'\x00\x00\x00\x00')
            i += 1
        elif i + 4 < len(data):
            # Decode 5 chars to 4 bytes
            chars = data[i:i+5]
            if len(chars) < 5:
                break

            try:
                value = 0
                for j, c in enumerate(chars):
                    value = value * 85 + (ord(c) - 33)

                # Convert to 4 bytes (big-endian)
                result.extend(struct.pack('>I', value & 0xFFFFFFFF))
                i += 5
            except:
                # Skip invalid chars
                i += 1
        else:
            break

    return bytes(result)

def try_lzma_decompress(data):
    """Try various LZMA decompression methods."""

    # Method 1: Standard LZMA with auto-detect
    try:
        return lzma.decompress(data)
    except:
        pass

    # Method 2: Raw LZMA stream
    try:
        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_RAW,
                                             filters=[{"id": lzma.FILTER_LZMA1}])
        return decompressor.decompress(data)
    except:
        pass

    # Method 3: Try skipping header bytes
    for skip in range(0, 20):
        try:
            return lzma.decompress(data[skip:])
        except:
            pass

    # Method 4: Try LZMA alone format
    try:
        return lzma.decompress(data, format=lzma.FORMAT_ALONE)
    except:
        pass

    return None

def find_encoded_blocks(lua_content):
    """Find all base85 encoded blocks in the Lua script."""

    # Pattern for string literals
    blocks = []

    # Find strings that look like base85 (printable ASCII, specific character set)
    # Base85 uses chars 33-117 (! to u) plus 'z'

    # Look for large quoted strings
    for match in re.finditer(r'"([^"]{50,})"', lua_content):
        s = match.group(1)
        # Check if mostly base85 characters
        base85_count = sum(1 for c in s if 33 <= ord(c) <= 117 or c == 'z')
        if base85_count > len(s) * 0.9:  # 90%+ base85 chars
            blocks.append(s)

    # Also look for single-quoted strings
    for match in re.finditer(r"'([^']{50,})'", lua_content):
        s = match.group(1)
        base85_count = sum(1 for c in s if 33 <= ord(c) <= 117 or c == 'z')
        if base85_count > len(s) * 0.9:
            blocks.append(s)

    return blocks

def analyze_decoded_data(data):
    """Analyze decoded binary data to identify structure."""

    if len(data) < 4:
        return "Too short"

    # Check for Lua bytecode signatures
    if data[:4] == b'\x1bLua':
        return "Lua bytecode"
    if data[:4] == b'\x1bLJ\x01':
        return "LuaJIT bytecode"
    if data[:3] == b'RSB':
        return "Luau bytecode (Roblox)"

    # Check entropy
    from collections import Counter
    freq = Counter(data[:1000])
    entropy = -sum((c/1000) * (c/1000).bit_length() for c in freq.values() if c > 0)

    # Look for patterns
    patterns = {
        b'\x00\x00\x00': "Many null sequences (possibly encrypted or structured)",
        b'function': "Contains 'function' keyword",
        b'return': "Contains 'return' keyword",
        b'local': "Contains 'local' keyword",
    }

    info = []
    for pat, desc in patterns.items():
        if pat in data[:2000]:
            info.append(desc)

    return f"Unknown format, {len(data)} bytes" + (", " + ", ".join(info) if info else "")

def main():
    print("=" * 60)
    print("LURAPH CUSTOM DECODER")
    print("=" * 60)

    # Read the script
    with open('/home/user/deobluraph/script.lua', 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    print(f"Script size: {len(content)} bytes")

    # Find encoded blocks
    blocks = find_encoded_blocks(content)
    print(f"Found {len(blocks)} potential base85 blocks")

    # Process each block
    decoded_blocks = []

    for i, block in enumerate(blocks):
        print(f"\n--- Block {i} ({len(block)} chars) ---")

        # Decode base85
        try:
            decoded = decode_base85(block)
            print(f"Base85 decoded: {len(decoded)} bytes")

            if len(decoded) > 0:
                # Show first bytes
                print(f"First 32 bytes: {decoded[:32].hex()}")

                # Try LZMA decompression
                decompressed = try_lzma_decompress(decoded)
                if decompressed:
                    print(f"LZMA decompressed: {len(decompressed)} bytes")
                    print(f"Analysis: {analyze_decoded_data(decompressed)}")
                    decoded_blocks.append({
                        'index': i,
                        'encoded_len': len(block),
                        'decoded_len': len(decoded),
                        'decompressed_len': len(decompressed),
                        'data': decompressed
                    })
                else:
                    print("LZMA decompression failed")
                    # Save raw decoded data
                    decoded_blocks.append({
                        'index': i,
                        'encoded_len': len(block),
                        'decoded_len': len(decoded),
                        'decompressed_len': 0,
                        'data': decoded
                    })
        except Exception as e:
            print(f"Error: {e}")

    # Save largest blocks
    if decoded_blocks:
        print("\n" + "=" * 60)
        print("SAVING DECODED DATA")
        print("=" * 60)

        # Sort by data size
        decoded_blocks.sort(key=lambda x: len(x['data']), reverse=True)

        for j, block in enumerate(decoded_blocks[:5]):
            filename = f'/home/user/deobluraph/decoded_block_{j}.bin'
            with open(filename, 'wb') as f:
                f.write(block['data'])
            print(f"Saved {filename}: {len(block['data'])} bytes")

    return decoded_blocks

if __name__ == '__main__':
    blocks = main()
