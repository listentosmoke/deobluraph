-- Luraph Runtime Decompiler
-- Traces VM execution and reconstructs original code

-- Compatibility
if not unpack then rawset(_G, "unpack", table.unpack) end
if not getgenv then rawset(_G, "getgenv", function() return _G end) end
if not setfenv then rawset(_G, "setfenv", function() end) end
if not getfenv then rawset(_G, "getfenv", function() return _G end) end

-- Store original functions
local orig = {
    print = print,
    pairs = pairs,
    ipairs = ipairs,
    type = type,
    tostring = tostring,
    pcall = pcall,
    loadstring = loadstring or load,
    load = load,
    setmetatable = setmetatable,
    getmetatable = getmetatable,
    rawset = rawset,
    rawget = rawget,
    select = select,
}

-- Trace storage
local trace = {
    operations = {},
    strings = {},
    function_calls = {},
    variables = {},
    control_flow = {},
}

local function log_op(op_type, details)
    trace.operations[#trace.operations + 1] = {
        type = op_type,
        details = details,
        time = os.clock()
    }
end

-- Create a deep proxy for tables that logs all access
local function create_proxy(target, name)
    local proxy = {}
    local mt = {
        __index = function(t, k)
            local v = target[k]
            log_op("GET", {table = name, key = tostring(k), value_type = orig.type(v)})
            if orig.type(v) == "table" then
                return create_proxy(v, name .. "." .. tostring(k))
            end
            return v
        end,
        __newindex = function(t, k, v)
            log_op("SET", {table = name, key = tostring(k), value_type = orig.type(v)})
            target[k] = v
        end,
        __call = function(t, ...)
            log_op("CALL", {func = name, args = select("#", ...)})
            return target(...)
        end,
    }
    setmetatable(proxy, mt)
    return proxy
end

-- Hook loadstring to capture and analyze decompressed code
local captured_vm = nil
local function hooked_loadstring(code, chunkname, ...)
    if orig.type(code) == "string" and #code > 1000 then
        if code:sub(1, 4) ~= "\27Lua" then
            captured_vm = code
            orig.print("[Decompiler] Captured VM code: " .. #code .. " bytes")

            -- Now we need to analyze and decompile this code
            -- The VM code is a table with handler functions
            -- Let's extract the structure
        end
    end

    -- Return a modified version that traces execution
    return create_traced_loader(code, chunkname, ...)
end

local function create_traced_loader(code, chunkname, ...)
    -- Load the code normally first
    local func, err = orig.loadstring(code, chunkname, ...)
    if not func then
        return nil, err
    end

    -- Check if this is the VM code
    if captured_vm == code then
        -- Wrap the VM to trace execution
        return function(...)
            orig.print("[Decompiler] VM execution started")
            local vm_table = func(...)

            if orig.type(vm_table) == "table" then
                -- This is the VM table, wrap its entry point
                orig.print("[Decompiler] VM table captured")

                -- Find and trace the entry function
                local entry_name = nil
                for k, v in orig.pairs(vm_table) do
                    if orig.type(v) == "function" then
                        -- Wrap each function
                        local original_func = v
                        vm_table[k] = function(...)
                            log_op("VM_FUNC", {name = tostring(k), args = select("#", ...)})
                            return original_func(...)
                        end
                    end
                end
            end

            return vm_table
        end
    end

    return func
end

rawset(_G, "loadstring", hooked_loadstring)
rawset(_G, "load", function(chunk, chunkname, mode, env)
    if orig.type(chunk) == "string" then
        return hooked_loadstring(chunk, chunkname)
    end
    return orig.load(chunk, chunkname, mode, env)
end)

orig.print("[Decompiler] Starting trace...")
orig.print(string.rep("=", 60))

-- Execute the obfuscated script
local success, result = orig.pcall(function()
    return dofile("script.lua")
end)

orig.print(string.rep("=", 60))

if success then
    orig.print("[Decompiler] Execution completed")
else
    orig.print("[Decompiler] Error: " .. orig.tostring(result))
end

-- Write trace
orig.print("[Decompiler] Writing trace...")

local f = io.open("runtime_trace.txt", "w")
if f then
    f:write("=== RUNTIME TRACE ===\n\n")
    f:write("Total operations: " .. #trace.operations .. "\n\n")

    for i, op in orig.ipairs(trace.operations) do
        f:write(string.format("[%d] %s: %s\n", i, op.type, orig.tostring(op.details)))
    end
    f:close()
end

-- If we captured the VM code, analyze it
if captured_vm then
    orig.print("[Decompiler] Analyzing captured VM...")

    local f = io.open("captured_vm_raw.lua", "w")
    if f then
        f:write(captured_vm)
        f:close()
    end

    -- Try to extract meaningful code by parsing the VM structure
    -- Look for function definitions and their bodies

    local functions_found = {}
    for name, params, body in captured_vm:gmatch("(%w+)=function%(([^)]*)%)(.-)end[,}]") do
        functions_found[name] = {
            params = params,
            body_size = #body
        }
    end

    local f = io.open("vm_functions.txt", "w")
    if f then
        f:write("=== VM FUNCTIONS ===\n\n")
        for name, info in orig.pairs(functions_found) do
            f:write(string.format("%s(%s): %d chars\n", name, info.params, info.body_size))
        end
        f:close()
    end

    orig.print("[Decompiler] Found " .. (function()
        local c = 0
        for _ in orig.pairs(functions_found) do c = c + 1 end
        return c
    end)() .. " functions")
end

orig.print("[Decompiler] Done!")
