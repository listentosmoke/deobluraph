-- Luraph VM Tracer/Deobfuscator
-- Traces VM execution and captures original operations

local output_file = "deobfuscated_final.lua"
local trace_log = {}
local captured_strings = {}
local call_stack = {}

-- Compatibility
if not unpack then
    rawset(_G, "unpack", table.unpack)
end

if not getgenv then
    rawset(_G, "getgenv", function() return _G end)
end

-- Original functions to preserve
local orig_print = print
local orig_pairs = pairs
local orig_ipairs = ipairs
local orig_type = type
local orig_tostring = tostring
local orig_loadstring = loadstring or load
local orig_pcall = pcall

-- Trace function calls
local function log_trace(msg)
    trace_log[#trace_log + 1] = msg
end

-- Capture string literals used in the code
local function capture_string(s)
    if type(s) == "string" and #s > 2 and #s < 1000 then
        if not captured_strings[s] then
            captured_strings[s] = true
            log_trace("STRING: " .. s:gsub("\n", "\\n"):gsub("\r", "\\r"))
        end
    end
end

-- Create proxied environment to trace calls
local function create_traced_env()
    local env = {}
    local original_G = _G

    -- Proxy for global access
    setmetatable(env, {
        __index = function(t, k)
            local v = original_G[k]
            if type(k) == "string" then
                capture_string(k)
            end
            return v
        end,
        __newindex = function(t, k, v)
            if type(k) == "string" then
                capture_string(k)
            end
            if type(v) == "string" then
                capture_string(v)
            end
            original_G[k] = v
        end
    })

    return env
end

-- Intercept loadstring to capture final decompiled code
local captured_vm_code = nil
local load_count = 0

local function hooked_loadstring(code, chunkname, ...)
    load_count = load_count + 1

    if type(code) == "string" then
        orig_print("[Tracer] Load #" .. load_count .. " - " .. #code .. " bytes")

        -- Check if it's bytecode or source
        if code:sub(1, 4) == "\27Lua" then
            orig_print("[Tracer] Detected Lua bytecode")
        else
            -- Capture the largest non-bytecode chunk as the main code
            if not captured_vm_code or #code > #captured_vm_code then
                captured_vm_code = code
                orig_print("[Tracer] Updated captured code: " .. #code .. " bytes")
            end
        end
    end

    -- Still return a working function to continue execution
    return orig_loadstring(code, chunkname, ...)
end

-- Hook load function
local function hooked_load(chunk, chunkname, mode, env)
    if type(chunk) == "string" then
        return hooked_loadstring(chunk, chunkname)
    end
    return (loadstring or load)(chunk, chunkname, mode, env)
end

-- Install hooks
rawset(_G, "loadstring", hooked_loadstring)
rawset(_G, "load", hooked_load)

-- Monitor require calls
local orig_require = require
rawset(_G, "require", function(modname)
    log_trace("REQUIRE: " .. tostring(modname))
    return orig_require(modname)
end)

orig_print("[Tracer] Starting VM trace...")
orig_print("=" .. string.rep("=", 59))

-- Execute the obfuscated script
local success, result = orig_pcall(function()
    return dofile("script.lua")
end)

orig_print("=" .. string.rep("=", 59))

if success then
    orig_print("[Tracer] Script executed successfully")
    orig_print("[Tracer] Result type: " .. type(result))
else
    orig_print("[Tracer] Script error: " .. tostring(result))
end

-- Write captured code
if captured_vm_code then
    orig_print("[Tracer] Writing captured VM code...")
    local f = io.open(output_file, "w")
    if f then
        f:write(captured_vm_code)
        f:close()
        orig_print("[Tracer] Written " .. #captured_vm_code .. " bytes to " .. output_file)
    end
end

-- Write trace log
if #trace_log > 0 then
    local f = io.open("trace_log.txt", "w")
    if f then
        for _, line in ipairs(trace_log) do
            f:write(line .. "\n")
        end
        f:close()
        orig_print("[Tracer] Trace log: " .. #trace_log .. " entries")
    end
end

-- Write captured strings
local string_count = 0
for _ in pairs(captured_strings) do string_count = string_count + 1 end
if string_count > 0 then
    local f = io.open("captured_strings.txt", "w")
    if f then
        for s, _ in pairs(captured_strings) do
            f:write(s .. "\n---\n")
        end
        f:close()
        orig_print("[Tracer] Captured " .. string_count .. " unique strings")
    end
end

orig_print("[Tracer] Done!")
