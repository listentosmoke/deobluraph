#!/usr/bin/env python3
"""
Inject bytecode capture hooks into the Luraph obfuscated script.
"""

import re

HOOKS_PREFIX = '''-- BYTECODE CAPTURE HOOKS (injected)
local _fc = 0
local _mf = 100

local function _ci(V)
    if type(V) ~= "table" then return end
    local interp = V[40] or V[0x28]
    if type(interp) ~= "function" then return end
    print("[CAPTURE] Hooking interpreter")
    local orig = interp
    V[40] = function(W, y, I)
        _fc += 1
        if _fc <= _mf then
            print("\\n=== FUNCTION " .. _fc .. " ===")
            if type(W) == "table" then
                if type(W[10]) == "table" then
                    local cnt = 0
                    for _ in pairs(W[10]) do cnt += 1 end
                    print("Instructions: " .. cnt)
                    for j = 1, math.min(50, cnt) do
                        if W[10][j] then
                            print(string.format("  [%d] = %d", j, W[10][j]))
                        end
                    end
                end
                if type(W[11]) == "table" then
                    local cnt = 0
                    for _ in pairs(W[11]) do cnt += 1 end
                    print("Strings: " .. cnt)
                    for j = 1, math.min(20, cnt) do
                        if W[11][j] then
                            local s = tostring(W[11][j])
                            if #s > 60 then s = s:sub(1,60) .. "..." end
                            print(string.format('  [%d] = "%s"', j, s:gsub("\\n","\\\\n")))
                        end
                    end
                end
            end
        end
        return orig(W, y, I)
    end
    V[0x28] = V[40]
end

print("=== CAPTURE INITIALIZED ===")

-- Wrap the VM table to hook E8
local _wrap_vm = function(vm)
    if type(vm) ~= "table" then return vm end
    local orig_E8 = vm.E8
    if orig_E8 then
        print("[CAPTURE] Hooking E8")
        vm.E8 = function(z, V, B, L)
            print("[E8] Called")
            orig_E8(z, V, B, L)
            _ci(V)
        end
    end
    return vm
end

-- Main script follows, wrapped in _wrap_vm
local _vm = _wrap_vm(
'''

HOOKS_SUFFIX = '''
)

-- Execute
print("[CAPTURE] Executing wS...")
local ok, err = pcall(function()
    _vm:wS()
end)
if ok then
    print("\\n=== COMPLETE ===")
    print("Functions: " .. _fc)
else
    print("\\n=== ERROR ===")
    print(tostring(err))
end
'''

def inject_hooks(script_path, output_path):
    with open(script_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    content = content.strip()

    # Remove Roblox-specific getgenv() line at start
    if content.startswith('getgenv()'):
        # Find end of this statement
        newline_idx = content.find('\n')
        if newline_idx > 0:
            content = content[newline_idx+1:].strip()

    # The script structure is:
    # return(function()...end):wS()(...)
    # We need to extract just the function definition

    # Find the return statement
    if not content.startswith('return('):
        # Skip comment lines
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('return('):
                content = '\n'.join(lines[i:])
                break

    content = content.strip()

    # Now extract: return(CONTENT):wS()(...)
    # We want CONTENT
    if content.startswith('return('):
        inner = content[7:]  # Remove "return("
        # Find the matching close paren before :wS()
        depth = 1
        end_idx = 0
        in_string = False
        string_char = None
        i = 0
        while i < len(inner):
            c = inner[i]
            # Handle strings
            if not in_string and (c == '"' or c == "'" or (c == '[' and i+1 < len(inner) and inner[i+1] == '[')):
                in_string = True
                if c == '[':
                    string_char = ']]'
                    i += 1
                else:
                    string_char = c
            elif in_string:
                if string_char == ']]':
                    if c == ']' and i+1 < len(inner) and inner[i+1] == ']':
                        in_string = False
                        i += 1
                elif c == string_char and (i == 0 or inner[i-1] != '\\'):
                    in_string = False
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
            i += 1

        if end_idx > 0:
            inner = inner[:end_idx]
        else:
            print("Warning: Could not find matching paren")
            inner = content
    else:
        inner = content

    # Build the hooked script
    hooked = HOOKS_PREFIX + inner + HOOKS_SUFFIX

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(hooked)

    print(f"Original: {len(content)} bytes")
    print(f"Hooked: {len(hooked)} bytes")
    print(f"Written to: {output_path}")

if __name__ == '__main__':
    inject_hooks('/home/user/deobluraph/script.lua', '/tmp/hooked_script.lua')
