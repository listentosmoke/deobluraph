#!/usr/bin/env python3
"""
Trace VM execution to capture the actual program behavior.
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

# Create execution tracer
tracer_prefix = '''-- EXECUTION TRACER
print("=== EXECUTION TRACER ===")

-- Stub Roblox functions but log calls
local _call_log = {}
local _call_count = 0
local _max_log = 5000

local function _trace(category, msg)
    _call_count = _call_count + 1
    if _call_count <= _max_log then
        local entry = "[" .. category .. "] " .. msg
        table.insert(_call_log, entry)
        print(entry)
    end
end

-- Create logging stubs for Roblox APIs
game = setmetatable({}, {
    __index = function(t, k)
        _trace("game", "Accessing game." .. tostring(k))
        if k == "GetService" then
            return function(self, name)
                _trace("game", "GetService(" .. tostring(name) .. ")")
                return setmetatable({}, {
                    __index = function(st, sk)
                        _trace("service:" .. tostring(name), "Accessing " .. tostring(sk))
                        return function(...)
                            _trace("service:" .. tostring(name), "Called " .. tostring(sk))
                            return {}
                        end
                    end
                })
            end
        elseif k == "PlaceId" then
            return 0
        end
        return function(...)
            _trace("game", "Called " .. tostring(k))
            return {}
        end
    end
})

workspace = setmetatable({}, {
    __index = function(t, k)
        _trace("workspace", "Accessing " .. tostring(k))
        return {}
    end
})

script = setmetatable({ Parent = {} }, {
    __index = function(t, k)
        _trace("script", "Accessing " .. tostring(k))
        return {}
    end
})

Instance = {
    new = function(class, parent)
        _trace("Instance", "new(" .. tostring(class) .. ")")
        return setmetatable({}, {
            __index = function(t, k) return function() end end,
            __newindex = function(t, k, v)
                _trace("Instance", "Setting " .. tostring(k) .. " = " .. tostring(v))
            end
        })
    end
}

-- Other Roblox stubs
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
Drawing = { new = function(t) _trace("Drawing", "new(" .. tostring(t) .. ")"); return {} end }
Input = nil

-- Hook print to trace output
local _orig_print = print
print = function(...)
    _trace("OUTPUT", table.concat({...}, " "))
end

-- Hook loadstring
local _orig_loadstring = loadstring
loadstring = function(code, name, ...)
    if type(code) == "string" and #code > 1000 then
        _trace("loadstring", "Loading " .. #code .. " bytes as '" .. tostring(name) .. "'")
    end
    return _orig_loadstring(code, name, ...)
end

_trace("INIT", "Starting execution...")

-- Run original script
local _result = (function(...)
'''

tracer_suffix = '''
end)(...)

_trace("DONE", "Script returned: " .. type(_result))
_trace("STATS", "Total traced calls: " .. _call_count)

-- Dump log summary
print("\\n=== EXECUTION SUMMARY ===")
print("Total calls logged: " .. #_call_log)

-- Count by category
local categories = {}
for _, entry in ipairs(_call_log) do
    local cat = entry:match("^%[([^%]]+)%]")
    if cat then
        categories[cat] = (categories[cat] or 0) + 1
    end
end

print("\\nBy category:")
for cat, count in pairs(categories) do
    print("  " .. cat .. ": " .. count)
end
'''

final_script = tracer_prefix + content + tracer_suffix

with open('/tmp/trace_script.lua', 'w') as f:
    f.write(final_script)

print(f"Tracer script written to /tmp/trace_script.lua")
print(f"Size: {len(final_script)} bytes")
