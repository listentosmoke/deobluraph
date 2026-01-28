#!/usr/bin/env python3
"""
Capture bytecode at runtime by hooking into the E8 interpreter.
"""

import re

# Read the original script
with open('/home/user/deobluraph/script.lua', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Remove getgenv and comments
content = re.sub(r'^getgenv\(\)[^\n]*\n', '', content)
while content.strip().startswith('--'):
    newline_idx = content.find('\n')
    if newline_idx > 0:
        content = content[newline_idx+1:]
    else:
        break
content = content.strip()

# Create bytecode capture hooks
capture_prefix = '''-- BYTECODE CAPTURE HOOKS
print("=== BYTECODE CAPTURE ===")

-- Roblox stubs
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

local _orig_setmetatable = setmetatable
local _orig_pairs = pairs
local _orig_ipairs = ipairs
local _orig_type = type
local _orig_tostring = tostring
local _orig_pcall = pcall
local _orig_loadstring = loadstring
local _orig_select = select

local _func_id = 0
local _captured_funcs = {}

local function dump_table(t, name, depth, max_entries)
    depth = depth or 0
    max_entries = max_entries or 100
    if depth > 3 then return end

    local indent = string.rep("  ", depth)
    local count = 0

    for k, v in _orig_pairs(t) do
        count = count + 1
        if count > max_entries then
            print(indent .. "... (more entries)")
            break
        end

        local kstr = _orig_tostring(k)
        local vtype = _orig_type(v)

        if vtype == "table" then
            local tc = 0
            for _ in _orig_pairs(v) do tc = tc + 1 end
            print(indent .. "[" .. kstr .. "] = <table:" .. tc .. ">")
            if depth < 2 and tc < 50 then
                dump_table(v, name .. "[" .. kstr .. "]", depth + 1, 30)
            end
        elseif vtype == "number" then
            print(indent .. "[" .. kstr .. "] = " .. v .. " (0x" .. string.format("%X", math.floor(v)) .. ")")
        elseif vtype == "string" then
            local s = v
            if #s > 60 then s = s:sub(1, 60) .. "..." end
            s = s:gsub("\\n", "\\\\n"):gsub("\\r", "\\\\r"):gsub("[\\x00-\\x1f]", ".")
            print(indent .. "[" .. kstr .. '] = "' .. s .. '"')
        elseif vtype == "function" then
            print(indent .. "[" .. kstr .. "] = <function>")
        else
            print(indent .. "[" .. kstr .. "] = " .. _orig_tostring(v))
        end
    end
end

-- Hook loadstring to capture and modify VM code
loadstring = function(code, name, ...)
    if _orig_type(code) ~= "string" then
        return _orig_loadstring(code, name, ...)
    end

    if #code < 1000 then
        return _orig_loadstring(code, name, ...)
    end

    print("\\n=== INTERCEPTED LOADSTRING ===")
    print("Name: " .. _orig_tostring(name))
    print("Length: " .. #code)

    -- Look for E8 function definition and inject hooks
    local modified = code

    -- Find and wrap the E8 function
    local e8_pattern = "E8=function"
    local e8_pos = modified:find(e8_pattern)

    if e8_pos then
        print("Found E8 at position " .. e8_pos)

        -- Inject hook code before E8
        local hook_code = [[
-- INJECTED BYTECODE CAPTURE HOOK
local _orig_E8_func = nil
local _capture_E8 = function(z, V, B, L)
    print("\\n=== E8 CALLED ===")

    -- V is the VM state table
    print("V type: " .. type(V))
    if type(V) == "table" then
        print("V keys:")
        for k, vv in pairs(V) do
            print("  [" .. tostring(k) .. "] = " .. type(vv))
        end
    end

    -- Original E8 creates V[0x28] = interpreter function
    -- We want to wrap that

    local result = _orig_E8_func(z, V, B, L)

    -- Now V[0x28] should be the interpreter
    if type(V) == "table" and type(V[0x28]) == "function" then
        local orig_interp = V[0x28]
        V[0x28] = function(W, y, I)
            print("\\n=== INTERPRETER CALLED ===")
            print("W (function data):")

            -- W[1] = instructions, W[5] = opA, W[10] = opcodes, etc.
            if type(W) == "table" then
                for k, v in pairs(W) do
                    local vtype = type(v)
                    if vtype == "table" then
                        local c = 0
                        for _ in pairs(v) do c = c + 1 end
                        print("  W[" .. tostring(k) .. "] = <table:" .. c .. ">")

                        -- Dump arrays that are likely bytecode
                        if type(k) == "number" and c > 0 and c < 500 then
                            print("    Contents:")
                            local cnt = 0
                            for kk, vv in pairs(v) do
                                cnt = cnt + 1
                                if cnt > 50 then
                                    print("      ... (more)")
                                    break
                                end
                                if type(vv) == "number" then
                                    print("      [" .. tostring(kk) .. "] = " .. vv .. " (0x" .. string.format("%X", math.floor(vv)) .. ")")
                                elseif type(vv) == "string" then
                                    local s = vv
                                    if #s > 40 then s = s:sub(1, 40) .. "..." end
                                    s = s:gsub("[\\x00-\\x1f]", ".")
                                    print("      [" .. tostring(kk) .. '] = "' .. s .. '"')
                                end
                            end
                        end
                    elseif vtype == "number" then
                        print("  W[" .. tostring(k) .. "] = " .. v)
                    end
                end
            end

            return orig_interp(W, y, I)
        end
        V[40] = V[0x28]  -- 0x28 = 40
    end

    return result
end
]]
        -- We'll need to replace E8=function with our wrapper
        -- This is complex - let's try a simpler approach
    end

    return _orig_loadstring(modified, name, ...)
end

print("=== EXECUTING SCRIPT ===")

local _result = (function(...)
'''

capture_suffix = '''
end)(...)

print("\\n=== EXECUTION COMPLETE ===")
print("Result type: " .. _orig_type(_result))
'''

final_script = capture_prefix + content + capture_suffix

with open('/tmp/bytecode_capture.lua', 'w') as f:
    f.write(final_script)

print(f"Bytecode capture script written: {len(final_script)} bytes")
