#!/usr/bin/env python3
"""
Inject bytecode logging into the decompressed VM and run it.
"""

import re

# Read decompressed VM
with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
    vm_code = f.read()

# Find E8 function and inject logging
# E8 creates V[0x28] which is the interpreter

# Find where V[0x28] or V[40] is assigned
# Pattern: (V)[0b0010_1000]= or V[40]=

# Add logging wrapper
logging_code = '''
-- BYTECODE LOGGING INJECTED
local _LOG = print
local _DUMP_COUNT = 0
local _MAX_DUMP = 50

local function _dump_bytecode(W, name)
    _DUMP_COUNT = _DUMP_COUNT + 1
    if _DUMP_COUNT > _MAX_DUMP then return end

    _LOG("\\n=== FUNCTION " .. _DUMP_COUNT .. " (" .. tostring(name) .. ") ===")

    if type(W) ~= "table" then
        _LOG("W is not a table: " .. type(W))
        return
    end

    -- Dump W structure
    for k, v in pairs(W) do
        local vtype = type(v)
        if vtype == "table" then
            local count = 0
            for _ in pairs(v) do count = count + 1 end
            _LOG("W[" .. tostring(k) .. "] = <table:" .. count .. ">")

            -- Dump contents if it's an array-like table
            if count > 0 and count < 200 then
                local is_array = true
                local max_idx = 0
                for kk, _ in pairs(v) do
                    if type(kk) ~= "number" then is_array = false; break end
                    if kk > max_idx then max_idx = kk end
                end

                if is_array and max_idx == count then
                    -- It's a proper array, dump first 100 elements
                    local dump = {}
                    for i = 1, math.min(100, count) do
                        if type(v[i]) == "number" then
                            table.insert(dump, string.format("%d", v[i]))
                        elseif type(v[i]) == "string" then
                            local s = v[i]
                            if #s > 30 then s = s:sub(1,30) .. "..." end
                            s = s:gsub("[\\x00-\\x1f]", ".")
                            table.insert(dump, '"' .. s .. '"')
                        else
                            table.insert(dump, tostring(type(v[i])))
                        end
                    end
                    _LOG("  Values: " .. table.concat(dump, ", "))
                end
            end
        elseif vtype == "number" then
            _LOG("W[" .. tostring(k) .. "] = " .. v)
        elseif vtype == "string" then
            _LOG("W[" .. tostring(k) .. '] = "' .. v:sub(1, 50) .. '"')
        elseif vtype == "function" then
            _LOG("W[" .. tostring(k) .. "] = <function>")
        end
    end
end

'''

# Find the start of the table definition
# The code starts with: return({J=table.move,...
# We want to inject our logging after the return({ but before the first member

insert_pos = vm_code.find('return({')
if insert_pos != -1:
    # Find the position after return({
    insert_pos = insert_pos + len('return({')

    # Insert our logging code as the first member of the table
    modified_vm = (
        vm_code[:insert_pos] +
        '\n_BYTECODE_LOG = (function() ' + logging_code + ' return _dump_bytecode end)(),\n' +
        vm_code[insert_pos:]
    )

    # Now we need to find where V[0x28] is assigned and wrap it
    # Pattern: (V)[0b0010_1000]=function(W,y,I)
    # We want to insert a call to _dump_bytecode(W) at the start of that function

    # Find the pattern
    interp_pattern = r'\(V\)\[0b0010_1000\]=\s*function\(W,y,I\)'
    match = re.search(interp_pattern, modified_vm)

    if match:
        # Insert logging call after the function definition starts
        func_start = match.end()

        # Find the first statement after the function header
        # We need to insert our logging before any processing
        modified_vm = (
            modified_vm[:func_start] +
            '\n_G._BYTECODE_LOG(W, "interpreter"); ' +
            modified_vm[func_start:]
        )

        print(f"Injected logging at positions")
    else:
        print("Could not find interpreter function pattern")
        # Try alternate patterns
        alt_patterns = [
            r'V\[0x28\]=function\(W',
            r'V\[40\]=function\(W',
            r'\[0X28\]=function\(W',
        ]
        for p in alt_patterns:
            if re.search(p, modified_vm):
                print(f"  Found alternate pattern: {p}")

    # Save modified VM
    with open('/tmp/modified_vm.lua', 'w') as f:
        f.write(modified_vm)

    print(f"Modified VM saved: {len(modified_vm)} bytes")
else:
    print("Could not find return({ in VM code")

# Now create a runner script
runner = '''-- Run the modified VM with stubs
print("=== RUNNING MODIFIED VM ===")

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

-- Load the modified VM
local vm_code = [=[
''' + modified_vm.replace(']=]', ']=].."]=]"..[[') + '''
]=]

local ok, err = pcall(function()
    local vm_func, load_err = loadstring(vm_code, "ModifiedVM")
    if not vm_func then
        print("Load error: " .. tostring(load_err))
        return
    end

    print("VM loaded, executing...")
    local vm = vm_func()

    print("VM type: " .. type(vm))
    if type(vm) == "table" then
        print("VM keys:")
        for k, v in pairs(vm) do
            print("  " .. tostring(k) .. " = " .. type(v))
        end
    end
end)

if not ok then
    print("Error: " .. tostring(err))
end

print("\\n=== DONE ===")
'''

with open('/tmp/run_modified_vm.lua', 'w') as f:
    f.write(runner)

print(f"Runner script saved")
