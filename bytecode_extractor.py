#!/usr/bin/env python3
"""
Bytecode Extractor and Analyzer for Luraph VM
Extracts and decodes all bytecode data from the deobfuscated VM
"""

import re
import struct
from collections import defaultdict

class BytecodeExtractor:
    def __init__(self):
        self.vm_code = None
        self.bytecode_blocks = []
        self.strings = []
        self.constants = []

    def load(self, path='deobfuscated.lua'):
        with open(path, 'r', errors='ignore') as f:
            self.vm_code = f.read()
        print(f"[*] Loaded {len(self.vm_code)} bytes of VM code")

    def base85_decode(self, data):
        """Decode Luraph's base85 encoding"""
        # Replace 'z' with '!!!!!' (shorthand for 0x00000000)
        data = data.replace('z', '!!!!!')
        result = bytearray()
        i = 0
        while i + 5 <= len(data):
            try:
                value = 0
                valid = True
                for c in data[i:i+5]:
                    code = ord(c) - 33
                    if code < 0 or code >= 85:
                        valid = False
                        break
                    value = value * 85 + code
                if valid and value <= 0xFFFFFFFF:
                    result.extend(struct.pack('>I', value))
            except:
                pass
            i += 5

        # Handle remaining bytes
        remaining = len(data) - i
        if remaining > 0:
            chunk = data[i:] + '!' * (5 - remaining)
            try:
                value = 0
                for c in chunk:
                    code = ord(c) - 33
                    if code >= 0 and code < 85:
                        value = value * 85 + code
                for j in range(4 - remaining + 1):
                    result.append((value >> (24 - j * 8)) & 0xFF)
            except:
                pass

        return bytes(result)

    def extract_bytecode_blocks(self):
        """Extract all base85 encoded bytecode blocks"""
        # Pattern for long strings: [=*[...]=*]
        for m in re.finditer(r'\[=*\[(.*?)\]=*\]', self.vm_code, re.DOTALL):
            raw = m.group(1)
            if len(raw) < 10:
                continue

            # Decode base85
            decoded = self.base85_decode(raw)
            if len(decoded) > 50:
                self.bytecode_blocks.append({
                    'raw_size': len(raw),
                    'decoded_size': len(decoded),
                    'data': decoded,
                    'preview': raw[:50]
                })

        self.bytecode_blocks.sort(key=lambda x: x['decoded_size'], reverse=True)
        total = sum(b['decoded_size'] for b in self.bytecode_blocks)
        print(f"[*] Found {len(self.bytecode_blocks)} bytecode blocks ({total} bytes total)")

    def extract_strings(self):
        """Extract all string constants from VM code"""
        # Find strings in the VM code
        for m in re.finditer(r'"([^"]*)"', self.vm_code):
            s = m.group(1)
            if len(s) > 2 and s.isprintable():
                self.strings.append(s)

        for m in re.finditer(r"'([^']*)'", self.vm_code):
            s = m.group(1)
            if len(s) > 2 and s.isprintable():
                self.strings.append(s)

        # Deduplicate
        self.strings = list(set(self.strings))
        self.strings.sort(key=len, reverse=True)
        print(f"[*] Found {len(self.strings)} unique strings")

    def analyze_bytecode_structure(self):
        """Analyze the structure of the largest bytecode block"""
        if not self.bytecode_blocks:
            return

        main = self.bytecode_blocks[0]['data']
        print(f"\n[*] Analyzing main bytecode block: {len(main)} bytes")

        # Try to identify the bytecode format
        # Lua bytecode typically has:
        # - Header with signature, version, etc.
        # - Function prototype with:
        #   - Source name
        #   - Line info
        #   - Upvalues
        #   - Constants (nil, bool, number, string)
        #   - Prototypes (nested functions)
        #   - Instructions

        # Check for Lua signature
        if main[:4] == b'\x1bLua':
            print("  [!] Standard Lua bytecode detected!")
            self._parse_lua_bytecode(main)
            return

        # Try different interpretations
        print("  [*] Trying to identify bytecode format...")

        # Check if it might be LZMA compressed
        if main[:2] == b'\x5d\x00' or main[0:1] == b'\x5d':
            print("  [?] Might be LZMA compressed")

        # Check for patterns
        # Look at 4-byte word patterns
        word_freq = defaultdict(int)
        for i in range(0, min(1000, len(main) - 3), 4):
            word = struct.unpack('<I', main[i:i+4])[0]
            word_freq[word & 0xFF] += 1  # Count low byte (potential opcodes)

        print("  [*] Low byte frequency (potential opcodes):")
        for byte, count in sorted(word_freq.items(), key=lambda x: -x[1])[:20]:
            print(f"      0x{byte:02X}: {count}")

        # Try to find instruction patterns
        # Luraph uses 8-bit opcodes with 8-bit operands
        self._analyze_as_luraph_bytecode(main)

    def _parse_lua_bytecode(self, data):
        """Parse standard Lua bytecode"""
        print("  Parsing standard Lua format...")
        # This would need full Lua bytecode parser
        # For now, just show header info
        if len(data) > 12:
            version = data[4]
            print(f"    Lua version: {version >> 4}.{version & 0xF}")

    def _analyze_as_luraph_bytecode(self, data):
        """Analyze data as Luraph VM bytecode"""
        print("\n  [*] Analyzing as Luraph bytecode format...")

        # The VM uses arrays for:
        # - q (instructions)
        # - N, d, _ (operands A, B, C)
        # - U, m, S (constants)

        # Try to find structure by looking for repeating patterns
        # Each instruction might be: opcode + operands

        # Check if data looks like serialized Lua tables
        # Luraph might use a custom serialization

        # Try reading as sequence of varints + data
        i = 0
        values = []
        while i < min(200, len(data)):
            # Try reading as varint
            val = 0
            shift = 0
            while i < len(data):
                b = data[i]
                i += 1
                val |= (b & 0x7F) << shift
                shift += 7
                if (b & 0x80) == 0:
                    break
            values.append(val)

        print(f"  [*] First {len(values)} varint values:")
        print(f"      {values[:30]}")

        # Alternative: treat as fixed-width data
        print(f"\n  [*] First 50 bytes as hex:")
        print(f"      {' '.join(f'{b:02X}' for b in data[:50])}")

        # Try to find string-like data
        strings_found = []
        i = 0
        while i < len(data) - 1:
            # Look for length-prefixed strings
            length = data[i]
            if 4 < length < 64 and i + length + 1 <= len(data):
                try:
                    s = data[i+1:i+1+length].decode('ascii')
                    if s.isprintable() and ' ' not in s[:5]:
                        strings_found.append((i, s))
                        i += length + 1
                        continue
                except:
                    pass
            i += 1

        if strings_found:
            print(f"\n  [*] Found {len(strings_found)} potential strings in bytecode:")
            for pos, s in strings_found[:20]:
                print(f"      @{pos}: \"{s[:50]}\"")

    def generate_output(self, output_path):
        """Generate comprehensive analysis output"""
        lines = []

        lines.append("--" + "=" * 78)
        lines.append("-- LURAPH BYTECODE EXTRACTION RESULTS")
        lines.append("--" + "=" * 78)
        lines.append("")

        lines.append(f"-- VM Code Size: {len(self.vm_code)} bytes")
        lines.append(f"-- Bytecode Blocks: {len(self.bytecode_blocks)}")
        lines.append(f"-- Total Bytecode: {sum(b['decoded_size'] for b in self.bytecode_blocks)} bytes")
        lines.append(f"-- Unique Strings: {len(self.strings)}")
        lines.append("")

        # Bytecode blocks
        lines.append("--[[ BYTECODE BLOCKS")
        for i, block in enumerate(self.bytecode_blocks[:30]):
            lines.append(f"  Block {i}: {block['decoded_size']:6d} bytes (raw: {block['raw_size']:6d})")
        lines.append("]]")
        lines.append("")

        # Hex dump of largest block
        if self.bytecode_blocks:
            main = self.bytecode_blocks[0]['data']
            lines.append(f"--[[ MAIN BYTECODE HEX DUMP (first 1000 bytes)")
            for i in range(0, min(1000, len(main)), 16):
                hex_part = ' '.join(f'{b:02X}' for b in main[i:i+16])
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in main[i:i+16])
                lines.append(f"  {i:04X}: {hex_part:<48} {ascii_part}")
            lines.append("]]")
            lines.append("")

        # Strings found (readable ones)
        lines.append("--[[ READABLE STRINGS")
        readable = [s for s in self.strings if all(c.isprintable() for c in s) and len(s) > 3]
        readable = readable[:100]
        for s in readable:
            if len(s) < 80:
                lines.append(f'  "{s}"')
        lines.append("]]")
        lines.append("")

        # Raw bytecode data for each block
        lines.append("-- RAW BYTECODE DATA")
        lines.append("")
        for i, block in enumerate(self.bytecode_blocks[:10]):
            lines.append(f"-- Block {i}: {block['decoded_size']} bytes")
            lines.append(f"bytecode_block_{i} = {{")

            data = block['data']
            # Output as array of numbers
            for j in range(0, len(data), 16):
                chunk = data[j:j+16]
                nums = ', '.join(str(b) for b in chunk)
                lines.append(f"  {nums}, -- offset {j}")
            lines.append("}")
            lines.append("")

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"\n[*] Saved output to {output_path}")


def main():
    print("=" * 70)
    print("LURAPH BYTECODE EXTRACTOR")
    print("=" * 70)
    print()

    extractor = BytecodeExtractor()
    extractor.load('deobfuscated.lua')
    extractor.extract_bytecode_blocks()
    extractor.extract_strings()
    extractor.analyze_bytecode_structure()
    extractor.generate_output('bytecode_extracted.lua')


if __name__ == "__main__":
    main()
