-- Deep Luraph VM Tracer
-- Comprehensively traces VM execution to extract original logic

local output_file = "trace_output.txt"
local deobfuscated_output = "final_deobfuscated.lua"

-- Compatibility shims
if not unpack then rawset(_G, "unpack", table.unpack) end
if not getgenv then rawset(_G, "getgenv", function() return _G end) end
if not setfenv then rawset(_G, "setfenv", function() end) end
if not getfenv then rawset(_G, "getfenv", function() return _G end) end

-- Trace storage
local traces = {}
local string_accesses = {}
local function_calls = {}
local captured_code = nil

local orig = {
    print = print,
    pairs = pairs,
    ipairs = ipairs,
    type = type,
    tostring = tostring,
    tonumber = tonumber,
    pcall = pcall,
    xpcall = xpcall,
    error = error,
    assert = assert,
    loadstring = loadstring or load,
    load = load,
    setmetatable = setmetatable,
    getmetatable = getmetatable,
    rawset = rawset,
    rawget = rawget,
    select = select,
    next = next,
    unpack = unpack or table.unpack,
}

local function log(msg)
    traces[#traces + 1] = msg
end

local function capture_string(context, str)
    if type(str) == "string" and #str > 2 and #str < 500 then
        local key = context .. ": " .. str:gsub("\n", "\\n"):gsub("\r", "\\r")
        string_accesses[key] = (string_accesses[key] or 0) + 1
    end
end

-- Create traced versions of common functions
local function create_traced_function(name, original)
    return function(...)
        local args = {...}
        local arg_str = ""
        for i, v in orig.ipairs(args) do
            if i > 1 then arg_str = arg_str .. ", " end
            if orig.type(v) == "string" then
                capture_string(name, v)
                arg_str = arg_str .. '"' .. v:sub(1, 50) .. '"'
            elseif orig.type(v) == "number" then
                arg_str = arg_str .. orig.tostring(v)
            else
                arg_str = arg_str .. orig.type(v)
            end
        end

        function_calls[name] = (function_calls[name] or 0) + 1

        if original then
            return original(...)
        end
    end
end

-- Hook loadstring to capture decompressed code
local load_count = 0
local function hooked_loadstring(code, chunkname, ...)
    load_count = load_count + 1

    if orig.type(code) == "string" then
        log("LOAD #" .. load_count .. ": " .. #code .. " bytes")

        -- Capture the largest code block that isn't bytecode
        if code:sub(1, 4) ~= "\27Lua" then
            if not captured_code or #code > #captured_code then
                captured_code = code
                log("Captured VM code: " .. #code .. " bytes")
            end
        end
    end

    return orig.loadstring(code, chunkname, ...)
end

rawset(_G, "loadstring", hooked_loadstring)
rawset(_G, "load", function(chunk, chunkname, mode, env)
    if orig.type(chunk) == "string" then
        return hooked_loadstring(chunk, chunkname)
    end
    return orig.load(chunk, chunkname, mode, env)
end)

-- Create traced string library
local traced_string = {}
for k, v in orig.pairs(string) do
    if orig.type(v) == "function" then
        traced_string[k] = function(...)
            local args = {...}
            if args[1] and orig.type(args[1]) == "string" then
                capture_string("string." .. k, args[1])
            end
            function_calls["string." .. k] = (function_calls["string." .. k] or 0) + 1
            return v(...)
        end
    else
        traced_string[k] = v
    end
end

-- Create traced table library
local traced_table = {}
for k, v in orig.pairs(table) do
    traced_table[k] = v
end

-- Create traced math library
local traced_math = {}
for k, v in orig.pairs(math) do
    traced_math[k] = v
end

-- Create traced bit32 library (if exists)
local traced_bit32 = {}
if bit32 then
    for k, v in orig.pairs(bit32) do
        traced_bit32[k] = v
    end
end

-- Create traced coroutine library
local traced_coroutine = {}
for k, v in orig.pairs(coroutine) do
    traced_coroutine[k] = v
end

orig.print("[Tracer] Starting deep trace...")
orig.print("=" .. string.rep("=", 59))

-- Execute the obfuscated script
local success, result = orig.pcall(function()
    return dofile("script.lua")
end)

orig.print("=" .. string.rep("=", 59))

if success then
    orig.print("[Tracer] Script executed: " .. orig.type(result))
else
    orig.print("[Tracer] Error: " .. orig.tostring(result))
end

-- Write trace output
orig.print("[Tracer] Writing trace output...")

local f = io.open(output_file, "w")
if f then
    f:write("=== TRACE LOG ===\n")
    for _, msg in orig.ipairs(traces) do
        f:write(msg .. "\n")
    end

    f:write("\n=== FUNCTION CALLS ===\n")
    local sorted_calls = {}
    for k, v in orig.pairs(function_calls) do
        sorted_calls[#sorted_calls + 1] = {name = k, count = v}
    end
    table.sort(sorted_calls, function(a, b) return a.count > b.count end)
    for _, item in orig.ipairs(sorted_calls) do
        f:write(item.name .. ": " .. item.count .. "\n")
    end

    f:write("\n=== STRING ACCESSES ===\n")
    local sorted_strings = {}
    for k, v in orig.pairs(string_accesses) do
        sorted_strings[#sorted_strings + 1] = {str = k, count = v}
    end
    table.sort(sorted_strings, function(a, b) return a.count > b.count end)
    for _, item in orig.ipairs(sorted_strings) do
        if item.count > 1 then
            f:write("[" .. item.count .. "] " .. item.str .. "\n")
        end
    end

    f:close()
    orig.print("[Tracer] Trace written to: " .. output_file)
end

-- Write captured code
if captured_code then
    local f = io.open(deobfuscated_output, "w")
    if f then
        f:write("-- Luraph Deobfuscated Output\n")
        f:write("-- Original size: " .. #captured_code .. " bytes\n")
        f:write("-- This is the decompressed VM code from Luraph v14.5.2\n\n")

        -- Format the code
        local formatted = captured_code
        formatted = formatted:gsub(";", ";\n")
        formatted = formatted:gsub("function%(", "\nfunction(")
        formatted = formatted:gsub("end,", "end,\n")

        f:write(formatted)
        f:close()
        orig.print("[Tracer] Code written to: " .. deobfuscated_output)
    end
end

orig.print("[Tracer] Done!")
orig.print("[Tracer] Total traces: " .. #traces)
orig.print("[Tracer] Function calls tracked: " .. #sorted_calls)
orig.print("[Tracer] String accesses tracked: " .. #sorted_strings)
