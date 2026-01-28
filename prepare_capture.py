#!/usr/bin/env python3
"""
Prepare the obfuscated script for runtime capture with Luau.
This version saves the decompressed code to a file.
"""

import re

# Read the original script
with open('/home/user/deobluraph/script.lua', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Remove Roblox-specific getgenv line
content = re.sub(r'^getgenv\(\)[^\n]*\n', '', content)

# Remove ALL comment lines at the start
while True:
    content = content.strip()
    if content.startswith('--'):
        newline_idx = content.find('\n')
        if newline_idx > 0:
            content = content[newline_idx+1:]
        else:
            break
    else:
        break

content = content.strip()
print(f"After cleanup, starts with: {content[:50]}")
print(f"After cleanup, ends with: {content[-50:]}")

# Inject hooks to save decompressed code
hooks_prefix = '''-- RUNTIME CAPTURE - SAVE DECOMPRESSED CODE
print("=== CAPTURE INIT ===")

-- Stub Roblox functions
game = { GetService = function() return {} end, PlaceId = 0 }
workspace = {}
script = { Parent = {} }
Instance = { new = function() return {} end }
getgenv = function() return _G end
gethui = function() return {} end
hookfunction = function(f) return f end
getrawmetatable = function() return {} end
setreadonly = function() end
isreadonly = function() return false end
islclosure = function() return true end
iscclosure = function() return false end
getinfo = function() return {} end
getconstants = function() return {} end
getupvalues = function() return {} end
setupvalue = function() end
getfenv = function() return _G end
setfenv = function() end
syn = nil
Drawing = nil
Input = nil

-- Keep original functions
local _orig_type = type
local _orig_tostring = tostring
local _orig_loadstring = loadstring

-- Capture state
local _loadstring_count = 0
local _saved_code = nil

-- Hook loadstring to capture decompressed code
loadstring = function(code, name, ...)
    _loadstring_count = _loadstring_count + 1

    if _orig_type(code) == "string" and #code > 10000 then
        print("\\n=== LARGE LOADSTRING #" .. _loadstring_count .. " ===")
        print("Name: " .. _orig_tostring(name))
        print("Code length: " .. #code)
        print("First 500 chars: " .. code:sub(1, 500))

        -- Save the code
        _saved_code = code

        -- Write to stdout in a parseable format
        print("\\n=== BEGIN_DECOMPRESSED_CODE ===")
        -- Output in chunks to handle large size
        local chunk_size = 50000
        for i = 1, #code, chunk_size do
            local chunk = code:sub(i, i + chunk_size - 1)
            print(chunk)
        end
        print("=== END_DECOMPRESSED_CODE ===")
    end

    -- Call original loadstring
    return _orig_loadstring(code, name, ...)
end

print("=== EXECUTING SCRIPT ===")

-- Run the original script
local _result = (function(...)
'''

hooks_suffix = '''
end)(...)

print("\\n=== SCRIPT RETURNED ===")
print("Type: " .. _orig_type(_result))
print("Loadstring calls: " .. _loadstring_count)
print("\\n=== CAPTURE COMPLETE ===")
'''

# Build the final script
final_script = hooks_prefix + content + hooks_suffix

output_path = '/tmp/capture_script.lua'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(final_script)

print(f"\nOriginal size: {len(content)} bytes")
print(f"Wrapped size: {len(final_script)} bytes")
print(f"Written to: {output_path}")
