#!/usr/bin/env python3
"""
Decode base85 strings from the VM to find the actual user code.
"""

import re

def base85_decode(s):
    """Decode Luraph-style base85 (ASCII85 variant)."""
    # Replace 'z' shorthand for 4 null bytes
    s = s.replace('z', '!!!!!')

    result = bytearray()
    i = 0
    while i < len(s):
        if i + 5 <= len(s):
            chunk = s[i:i+5]
            try:
                # Each character is value 33-117 (ASCII ! to u)
                val = 0
                for c in chunk:
                    val = val * 85 + (ord(c) - 33)
                # Convert to 4 bytes (big endian)
                result.extend(val.to_bytes(4, 'big'))
                i += 5
            except:
                i += 1
        else:
            # Handle remaining bytes
            remaining = len(s) - i
            if remaining > 0:
                chunk = s[i:] + '!' * (5 - remaining)
                try:
                    val = 0
                    for c in chunk:
                        val = val * 85 + (ord(c) - 33)
                    result.extend(val.to_bytes(4, 'big')[:remaining-1])
                except:
                    pass
            break

    return bytes(result)


# Read the decompressed VM
with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
    vm_code = f.read()

# Find all quoted strings that look like base85
# Base85 uses characters !-u (ASCII 33-117)
pattern = r'"([!-u]{10,})"'
matches = re.findall(pattern, vm_code)

print(f"Found {len(matches)} potential base85 strings")
print()

# Decode and analyze
decoded_strings = []
readable_strings = []

for i, match in enumerate(matches[:100]):  # First 100
    try:
        decoded = base85_decode(match)
        decoded_strings.append(decoded)

        # Check if it contains readable text
        try:
            text = decoded.decode('utf-8', errors='ignore')
            # Filter for printable
            printable = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in text)
            if len(printable) > 10 and printable.count('.') < len(printable) * 0.5:
                readable_strings.append((i, match[:30], printable[:200]))
        except:
            pass

    except Exception as e:
        pass

print(f"Decoded {len(decoded_strings)} strings")
print(f"Found {len(readable_strings)} readable strings")
print()

print("=== READABLE STRINGS ===")
for idx, orig, text in readable_strings[:50]:
    print(f"\n[{idx}] Original: {orig}...")
    print(f"    Decoded: {text}")

# Also look for non-base85 strings that might be meaningful
print("\n\n=== NON-BASE85 STRINGS ===")
# Find strings that contain normal words
normal_pattern = r'"([A-Za-z_][A-Za-z0-9_\s]{5,50})"'
normal_matches = re.findall(normal_pattern, vm_code)
unique_normal = set(normal_matches)

print(f"Found {len(unique_normal)} potential identifier strings")
for s in sorted(unique_normal)[:30]:
    print(f"  - {s}")

# Look for function/method names
print("\n\n=== FUNCTION REFERENCES ===")
func_pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]+)\s*\('
func_matches = re.findall(func_pattern, vm_code)
func_counts = {}
for f in func_matches:
    func_counts[f] = func_counts.get(f, 0) + 1

print("Most common function calls:")
for f, c in sorted(func_counts.items(), key=lambda x: -x[1])[:30]:
    print(f"  {f}: {c}")
