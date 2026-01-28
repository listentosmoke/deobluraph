# Luraph v14.5.2 Deobfuscation Report

## Summary

This report documents the analysis and partial deobfuscation of a Luraph v14.5.2 protected Lua script targeting Luau/Roblox.

## Files Produced

1. **decompressed_vm.lua** (836,922 bytes) - Raw decompressed VM code
2. **decompressed_vm_formatted.lua** (870,985 bytes) - Formatted version for readability
3. **luraph_decompiler.py** - Bytecode analysis tool
4. **extract_strings.py** - String extraction tool
5. **analyze_opcodes.py** - Opcode mapping analysis
6. **decompiled_output.lua** - Partial decompilation output

## Methodology

### 1. Initial Analysis
- Identified Luraph v14.5.2 obfuscator targeting Luau/Roblox
- Script structure: `return(function()...end)()(...)` pattern
- Two-stage protection: base85 encoding + LZMA compression

### 2. Runtime Capture Approach
- Built Luau from source with sandbox disabled
- Patched `/tmp/luau-src/CLI/src/Repl.cpp` to remove `luaL_sandbox()` call
- Injected hooks to intercept `loadstring` calls
- Captured the decompressed code (836,745 bytes) when LZMA decompression completed

### 3. Bytecode Analysis

#### VM Data Structures
From the E8 interpreter at line 751:
```lua
local I,_,S,N,q,U,d,m,h = W[1],W[5],W[11],W[4],W[10],W[9],W[7],W[8];
```

| Array | Index | Purpose |
|-------|-------|---------|
| W[1]  | I     | Instructions/code array |
| W[4]  | N     | Operand B array |
| W[5]  | _     | Operand A array |
| W[7]  | d     | Operand D array |
| W[8]  | m     | Operand E array |
| W[9]  | U     | Operand C array |
| W[10] | q     | Opcode array |
| W[11] | S     | String constants |

#### Opcode Mappings (from E8 interpreter)
```
0xBD (189): RETURN     - return X[i](...)
0xBC (188): SETTABLE   - X[B][X[D]] = X[A]
0xBB (187): SUBK       - X[D] = C - E (constants)
0xBA (186): CALL_NORET - Call without return values
0xB9 (185): VARARG     - Load vararg values to registers
0xB8 (184): GE_K       - X[D] = X[B] >= C
0xB7 (183): MUL        - X[B] = X[A] * X[D]
0xB6 (182): DIV        - X[D] = X[A] / X[B]
0xB5 (181): GT         - X[D] = X[B] > X[A]
0xB4 (180): FORLOOP    - Numeric for loop
0xAF (175): FORPREP    - For loop preparation
0xAE (174): JMP_IF     - Conditional jump
0xAD (173): CONCAT     - X[D] = X[B] .. X[A]
0xAC (172): FOR_INIT   - For loop initialization
0xAB (171): CALL0      - Call with 0 args
0xAA (170): CLOSURE    - Create closure from proto
0xC0 (192): LOADK      - Load constant/string
0xBE (190): LOADNIL    - X[B] = nil
0xBF (191): JMP_EQ     - Jump if equal
```

#### Base85 Decoder
Found at lines 5188-5197:
```lua
function(V, y)
    local I,_,S,N,q = B[14](y, 1, 5);  -- string.byte
    local U = (q-33) + (N-33)*85 + (S-33)*7225 + (_-33)*614125 + (I-33)*52200625;
    q = B[8](">I4", U);  -- string.unpack big-endian 32-bit
    V[y] = q;
    return q;
end
```

#### Bytecode Statistics
- **Main bytecode segment**: 596,536 bytes (decoded)
- **Total bytecode segments**: 27
- **Total decoded size**: 777,988 bytes

#### Opcode Frequency in Bytecode
| Opcode | Name | Count |
|--------|------|-------|
| 0xAB | CALL0 | 3,498 |
| 0xBC | SETTABLE | 3,293 |
| 0xBB | SUBK | 3,232 |
| 0xAA | CLOSURE | 2,485 |
| 0xB6 | DIV | 2,239 |
| 0xBD | RETURN | 2,129 |
| 0xBE | LOADNIL | 1,999 |
| 0xB7 | MUL | 1,950 |

### 4. Obfuscation Techniques Used

1. **Variable Renaming**: Single-letter names (z, V, B, L, W, y, I)
2. **Numeric Obfuscation**: Mixed hex (0X), binary (0B), underscores in numbers
3. **Control Flow Flattening**: Binary tree dispatch for opcodes
4. **Dead Code Injection**: Anti-tamper checks with V[n] comparisons
5. **String Encoding**: Base85-encoded bytecode strings
6. **Lazy Decoding**: `__index` metamethod for on-demand bytecode reading
7. **Custom Bytecode Format**: Separate arrays for opcodes and operands

### 5. Anti-Tamper Checks
The script performs loadstring checks on startup:
1. Tests `loadstring(54456)` - numeric code check
2. Tests `loadstring("\x1bLuaP")` - Lua bytecode signature
3. Tests `loadstring(tostring(func))` - function reference check

## What Was Captured vs What Remains Encoded

### Successfully Captured
- ✅ VM Interpreter: 836KB of Lua source code
- ✅ Opcode Handlers: 125+ functions
- ✅ VM Data Structure: Register/stack/constant organization
- ✅ Opcode Mappings: ~20 opcodes identified

### Still Encoded (Within Bytecode)
- ❌ Original function names
- ❌ String constants (API names, messages)
- ❌ Control flow structure
- ❌ Variable names

## Limitations

### Why Full Decompilation is Challenging

1. **Complex Bytecode Format**: Instructions stored as separate parallel arrays rather than packed 4-byte instructions
2. **String Encryption**: All string constants are within the bytecode, requiring full deserialization
3. **Opcode Shuffling**: Each Luraph build can shuffle opcodes differently
4. **Anti-Analysis**: Dead code and fake branches complicate analysis

### What Would Be Required

1. **Runtime Tracing**: Hook into the interpreter to capture instruction-by-instruction execution
2. **Bytecode Deserializer**: Fully reverse the bytecode format from the deserialization functions
3. **Control Flow Analysis**: Reconstruct if/else/while/for from jump opcodes
4. **SSA Form**: Convert register-based code to proper variable assignments

## Files Structure

```
deobluraph/
├── script.lua                    # Original obfuscated script
├── decompressed_vm.lua          # Captured VM code
├── decompressed_vm_formatted.lua # Formatted VM code
├── luraph_decompiler.py         # Bytecode analysis tool
├── analyze_opcodes.py           # Opcode extraction
├── extract_strings.py           # String extraction
├── capture_bytecode.py          # Runtime capture hooks
├── inject_vm_logging.py         # VM logging injection
├── decompiled_output.lua        # Partial decompilation
├── extracted_strings.txt        # Extracted string data
└── DEOBFUSCATION_REPORT.md      # This report
```

## Conclusion

The Luraph protection has been **partially bypassed**:
- ✅ Captured the complete VM implementation (836KB)
- ✅ Identified the opcode dispatch structure
- ✅ Mapped ~20 opcodes to their Lua operations
- ✅ Extracted 596KB of raw bytecode

However, **full source code recovery** would require:
- Building a complete bytecode deserializer
- Creating a control flow reconstruction algorithm
- Implementing expression tree building from stack operations

The provided tools (`luraph_decompiler.py`, `analyze_opcodes.py`) can serve as a starting point for further analysis.

## Technical Reference

### Key Code Locations
- **E8 interpreter**: `decompressed_vm_formatted.lua:748-1200`
- **Base85 decoder**: `decompressed_vm_formatted.lua:5188-5197`
- **Bytecode strings**: `decompressed_vm_formatted.lua:5198+`
- **Entry point (wS)**: `decompressed_vm.lua:830200`

### VM State Table (V)
| Index | Purpose |
|-------|---------|
| V[7]  | Code reader function |
| V[13] | Instruction unpacker |
| V[16] | Environment setup |
| V[17] | Bytecode buffer reader |
| V[32] | Anti-tamper flags |
| V[34] | Varint reader |
| V[40] | Interpreter function (created by E8) |

### Runtime Variables
| Name | Purpose |
|------|---------|
| X    | Registers/stack |
| w    | Program counter |
| y    | Upvalues array |
| H    | Open upvalue tracking |
| o    | Current opcode |
