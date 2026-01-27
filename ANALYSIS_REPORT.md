# Luraph v14.5.2 Deobfuscation Analysis Report

## Overview

This repository contains the analysis of a Luraph v14.5.2 obfuscated Lua script targeting the Luau/Roblox platform.

## Obfuscation Techniques Identified

1. **Virtualization**: Custom VM interpreter with 32+ mapped opcodes
2. **Bytecode Mutation**: Opcodes mapped to multiple values
3. **Control Flow Scrambling**: Dispatch tree with complex state machines
4. **Encryption**: Bytecode encrypted (7.9 bits/byte entropy)
5. **Compression**: LZMA (range coder) compression with base85 encoding

## Technical Findings

### VM Structure

| Component | Variable | Description |
|-----------|----------|-------------|
| Instructions | `q` | Opcode array |
| Program Counter | `w` | Current instruction index |
| Current Opcode | `o` | `q[w]` |
| Registers | `X` | Register stack |
| Upvalues | `y` | Closure upvalues |
| Constants | `U`, `m`, `S` | Constant pools |
| Operands | `N[w]`, `d[w]`, `_[w]` | A, B, C operands |
| Open Upvalues | `H` | Pending upvalue closures |
| Stack Base | `I` | Base register index |
| VM State | `V` | Internal state table |

### Key Functions

- **E8**: Main interpreter factory
- **V[40]**: Actual bytecode interpreter
- **wS**: Entry point/initialization
- **b**: LZMA range decoder (called 250M+ times during decompression)

### Opcode Mapping

```
EQ          : 0x80
GETTABLE    : 0x38
GETTABUP    : 0x1A, 0x86
JUMP        : 0x23, 0x2F, 0x8F
LE          : 0x29, 0x83
LEN         : 0x1D
MOVE        : 0x56, 0x7D, 0xA1
POW         : 0x50, 0x6B
RETURN      : 0x05, 0x71, 0x95
UNKNOWN     : 0x02, 0x14, 0x20, 0x2C, 0x32, 0x35, 0x41, 0x44, 0x4D, 0x53, 0x59, 0x5C, 0x6E, 0xC0
```

### Data Statistics

- **VM Code Size**: 836,745 bytes
- **Bytecode Size**: 596,536 bytes (base85 decoded)
- **Bytecode Entropy**: 7.9 bits/byte (encrypted)
- **VM Handlers**: 80 functions
- **Opcodes Mapped**: 32

## Analysis Files

| File | Description |
|------|-------------|
| `script.lua` | Original obfuscated script |
| `deobfuscated.lua` | Extracted VM code (single line, 836KB) |
| `deobfuscated_standard.lua` | Lua 5.1/5.2/LuaJIT compatible version |
| `comprehensive_output.lua` | Static analysis results |
| `comprehensive_output.json` | Analysis data in JSON format |
| `convert_to_standard_lua.py` | Luau → Standard Lua converter |

## Runtime Analysis Attempts

Multiple runtime capture approaches were attempted:

1. **Lua 5.4**: bit32 compatibility issues
2. **Lua 5.3**: string.pack overflow issues
3. **LuaJIT**: Works but LZMA decompression takes 250M+ function calls (impractical)
4. **Luau**: Sandbox restrictions prevent hooking

## Conclusion

The bytecode within the Luraph VM is encrypted with high entropy (7.9 bits/byte), preventing direct static analysis of the protected code. Runtime capture is possible in principle but impractical due to:

1. LZMA decompression requiring 250+ million function calls
2. Luau sandbox preventing modification of VM state
3. Standard Lua lacking Luau-specific features

### Recommendations

For full decompilation, consider:
1. Native Luau environment with debug library access
2. Binary instrumentation of Luau interpreter
3. Custom LZMA decoder with key extraction from VM constants
4. Memory dump analysis during Roblox execution

## Tools Created

- `bytecode_extractor.py`: Extract bytecode from VM
- `comprehensive_analysis.py`: Full VM analysis
- `convert_to_standard_lua.py`: Syntax converter
- `luajit_trace.lua`: Function call tracer
- `test_vm_load.lua`: VM loading test

---
*Analysis performed using static analysis, runtime tracing, and multiple Lua interpreters.*
