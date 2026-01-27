-- Instrumented Luraph VM
-- This file loads the deobfuscated VM and adds hooks to capture bytecode

-- Lua 5.4 compatibility
if not unpack then
    rawset(_G, "unpack", table.unpack)
end
if not getgenv then
    rawset(_G, "getgenv", function() return _G end)
end

-- Output file
local output = io.open("captured_runtime_data.lua", "w")
local function log(msg)
    output:write(msg .. "\n")
    output:flush()
    print(msg)
end

log("-- Luraph VM Runtime Capture")
log("-- " .. os.date())
log("")

-- Counter for functions
local func_count = 0

-- Helper to serialize arrays
local function dump_array(arr, name, max_len)
    max_len = max_len or 5000
    if type(arr) ~= "table" then
        log(name .. " = " .. tostring(arr))
        return
    end

    local len = 0
    for k, v in pairs(arr) do
        len = len + 1
    end

    log(name .. " = {  -- " .. len .. " entries")

    local count = 0
    for i = 1, max_len do
        local v = arr[i]
        if v ~= nil then
            count = count + 1
            if type(v) == "string" then
                -- Escape and truncate long strings
                local s = v
                if #s > 100 then s = s:sub(1, 100) .. "..." end
                s = s:gsub("\\", "\\\\"):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\"", "\\\""):gsub("[%c]", "?")
                log(string.format("  [%d] = \"%s\",", i, s))
            elseif type(v) == "number" then
                log(string.format("  [%d] = %s,", i, v))
            elseif type(v) == "boolean" then
                log(string.format("  [%d] = %s,", i, tostring(v)))
            elseif type(v) == "function" then
                log(string.format("  [%d] = <function>,", i))
            elseif type(v) == "table" then
                log(string.format("  [%d] = <table:%d>,", i, #v))
            else
                log(string.format("  [%d] = <%s>,", i, type(v)))
            end
        end
    end

    if len > max_len then
        log("  -- ... " .. (len - max_len) .. " more entries")
    end
    log("}")
    log("")
end

-- Load the deobfuscated VM code
log("-- Loading deobfuscated VM...")
local vm_code_file = io.open("deobfuscated_fixed.lua", "r")
if not vm_code_file then
    log("-- ERROR: Could not open deobfuscated.lua")
    os.exit(1)
end
local vm_code = vm_code_file:read("*a")
vm_code_file:close()
log("-- Loaded " .. #vm_code .. " bytes")

-- Load and execute to get VM table
local vm_loader, err = load(vm_code, "vm")
if not vm_loader then
    log("-- ERROR loading VM: " .. tostring(err))
    os.exit(1)
end

log("-- Executing VM loader...")
local VM = vm_loader()

if type(VM) ~= "table" then
    log("-- ERROR: VM is not a table, got " .. type(VM))
    os.exit(1)
end

log("-- Got VM table")
log("")

-- List VM table keys
log("-- VM table keys:")
for k, v in pairs(VM) do
    log("  " .. tostring(k) .. " = " .. type(v))
end
log("")

-- Find E8 (the main interpreter setup function)
local E8 = VM.E8
if not E8 then
    log("-- ERROR: E8 not found in VM table")
    os.exit(1)
end

log("-- Found E8 function")
log("")

-- Create a mock V table to capture what E8 sets up
local captured_interpreters = {}

-- Hook E8
VM.E8 = function(z, V, B, L)
    log("-- E8 called with:")
    log("--   z type: " .. type(z))
    log("--   V type: " .. type(V))
    log("--   B type: " .. type(B))
    log("--   L type: " .. type(L))

    -- Call original E8
    E8(z, V, B, L)

    -- V[40] (0x28 = 40) should now have the interpreter
    local interp = V[40] or V[0x28]
    if interp then
        log("-- E8 created interpreter at V[40]")

        -- Hook the interpreter
        local original_interp = interp
        V[40] = function(W, y, I)
            func_count = func_count + 1
            local fid = func_count

            log("")
            log("-- =============================================")
            log("-- FUNCTION " .. fid .. " PROTOTYPE")
            log("-- =============================================")

            if type(W) == "table" then
                -- W[1] = stack size / parameter info
                log("-- W[1] (info): " .. tostring(W[1]))

                -- W[4] = operand A (N)
                if W[4] then dump_array(W[4], "operandA_" .. fid, 3000) end

                -- W[5] = operand C (_)
                if W[5] then dump_array(W[5], "operandC_" .. fid, 3000) end

                -- W[7] = operand B (d)
                if W[7] then dump_array(W[7], "operandB_" .. fid, 3000) end

                -- W[8] = constants m
                if W[8] then dump_array(W[8], "constantsM_" .. fid, 1000) end

                -- W[9] = constants U
                if W[9] then dump_array(W[9], "constantsU_" .. fid, 1000) end

                -- W[10] = INSTRUCTIONS (q) - THE BYTECODE!
                if W[10] then dump_array(W[10], "INSTRUCTIONS_" .. fid, 5000) end

                -- W[11] = constants S
                if W[11] then dump_array(W[11], "constantsS_" .. fid, 1000) end
            end

            log("-- End of prototype " .. fid)
            log("")

            -- Call original
            return original_interp(W, y, I)
        end
        V[0x28] = V[40]
    end
end

-- Now we need to trigger the VM execution
-- The VM is initialized by calling :wS() or similar entry function
log("-- Looking for entry point...")

-- Find wS function (the entry point that starts execution)
local wS = VM.wS
if wS then
    log("-- Found wS entry function")

    -- The wS function typically calls the first bytecode block
    -- Let's try to trace its execution
    log("-- Attempting to call VM:wS()...")

    local ok, err = pcall(function()
        VM:wS()
    end)

    if not ok then
        log("-- wS execution error: " .. tostring(err))
    end
else
    log("-- wS not found, looking for alternative entry...")

    -- Try to find any function that looks like an entry point
    for k, v in pairs(VM) do
        if type(v) == "function" and type(k) == "string" and k:match("^[a-zA-Z]") then
            log("-- Trying: " .. k)
        end
    end
end

log("")
log("-- Captured " .. func_count .. " function prototypes")
log("-- Data saved to captured_runtime_data.lua")

output:close()
