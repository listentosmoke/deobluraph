-- Runtime Debugger for Luraph VM
-- Captures decrypted bytecode by hooking VM execution

-- Lua 5.4 compatibility
if not unpack then
    rawset(_G, "unpack", table.unpack)
end
if not getgenv then
    rawset(_G, "getgenv", function() return _G end)
end

-- Output file for captured data
local output_file = io.open("captured_bytecode.lua", "w")
local function log(...)
    local args = {...}
    local line = ""
    for i, v in ipairs(args) do
        line = line .. tostring(v) .. "\t"
    end
    output_file:write(line .. "\n")
    output_file:flush()
    print(line)
end

log("-- Luraph Runtime Bytecode Capture")
log("-- Capturing decrypted VM data...")
log("")

-- Track all captured functions
local captured_functions = {}
local function_counter = 0

-- Helper to serialize a table
local function serialize_array(arr, name, max_items)
    max_items = max_items or 10000
    local result = {}
    local count = 0

    if type(arr) ~= "table" then
        return name .. " = " .. tostring(arr)
    end

    -- Check if it's an array-like table
    local is_array = true
    local max_idx = 0
    for k, v in pairs(arr) do
        if type(k) ~= "number" then
            is_array = false
            break
        end
        if k > max_idx then max_idx = k end
        count = count + 1
        if count > max_items then break end
    end

    if is_array and max_idx > 0 then
        result[#result+1] = name .. " = {"
        for i = 1, math.min(max_idx, max_items) do
            local v = arr[i]
            if v ~= nil then
                if type(v) == "string" then
                    -- Escape string
                    local escaped = v:gsub("\\", "\\\\"):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\"", "\\\"")
                    result[#result+1] = string.format("  [%d] = %q,", i, v)
                elseif type(v) == "number" then
                    result[#result+1] = string.format("  [%d] = %s,", i, tostring(v))
                elseif type(v) == "boolean" then
                    result[#result+1] = string.format("  [%d] = %s,", i, tostring(v))
                else
                    result[#result+1] = string.format("  [%d] = <%s>,", i, type(v))
                end
            end
        end
        if max_idx > max_items then
            result[#result+1] = "  -- ... " .. (max_idx - max_items) .. " more entries"
        end
        result[#result+1] = "}"
    else
        result[#result+1] = name .. " = { -- non-array table"
        for k, v in pairs(arr) do
            count = count + 1
            if count > max_items then break end
            if type(v) == "string" then
                result[#result+1] = string.format("  [%s] = %q,", tostring(k), v)
            else
                result[#result+1] = string.format("  [%s] = %s,", tostring(k), tostring(v))
            end
        end
        result[#result+1] = "}"
    end

    return table.concat(result, "\n")
end

-- Hook the original loadstring
local original_loadstring = loadstring or load
local captured_vm = nil

rawset(_G, "loadstring", function(code, ...)
    log("-- loadstring called with " .. #code .. " bytes")

    -- Load the code to get the VM
    local fn, err = original_loadstring(code, ...)
    if not fn then
        log("-- Load error: " .. tostring(err))
        return fn, err
    end

    -- Return a wrapper that captures execution
    return function(...)
        log("-- VM function executing...")

        -- Execute to get the VM table
        local result = fn(...)

        if type(result) == "table" then
            log("-- Got VM table, hooking E8...")
            captured_vm = result

            -- Find E8 function
            local E8 = result.E8
            if E8 then
                log("-- Found E8 function, hooking...")

                -- Hook E8 to capture when it creates interpreter
                result.E8 = function(z, V, B, L)
                    log("-- E8 called")

                    -- Call original E8
                    E8(z, V, B, L)

                    -- Now V[40] should have the interpreter function
                    -- Hook it to capture bytecode
                    local original_interp = V[40] or V[0x28]
                    if original_interp then
                        log("-- Found interpreter at V[40], hooking...")

                        V[40] = function(W, y, I)
                            function_counter = function_counter + 1
                            local func_id = function_counter

                            log("")
                            log("-- ============================================")
                            log("-- FUNCTION " .. func_id)
                            log("-- ============================================")

                            -- W contains the prototype data:
                            -- W[1] = ? (I)
                            -- W[4] = operand A array (N)
                            -- W[5] = operand C array (_)
                            -- W[7] = operand B array (d)
                            -- W[8] = constant array m
                            -- W[9] = constant array U
                            -- W[10] = instruction array q (BYTECODE!)
                            -- W[11] = constant array S

                            if type(W) == "table" then
                                log("-- Prototype W has " .. #W .. " entries")

                                -- Capture instruction array (q = W[10])
                                local q = W[10]
                                if type(q) == "table" then
                                    log("-- Instructions (q = W[10]): " .. #q .. " entries")
                                    output_file:write(serialize_array(q, "instructions_" .. func_id, 5000) .. "\n\n")
                                end

                                -- Capture operand arrays
                                local N = W[4]  -- operand A
                                if type(N) == "table" then
                                    log("-- Operand A (N = W[4]): " .. #N .. " entries")
                                    output_file:write(serialize_array(N, "operandA_" .. func_id, 5000) .. "\n\n")
                                end

                                local d = W[7]  -- operand B
                                if type(d) == "table" then
                                    log("-- Operand B (d = W[7]): " .. #d .. " entries")
                                    output_file:write(serialize_array(d, "operandB_" .. func_id, 5000) .. "\n\n")
                                end

                                local underscore = W[5]  -- operand C
                                if type(underscore) == "table" then
                                    log("-- Operand C (_ = W[5]): " .. #underscore .. " entries")
                                    output_file:write(serialize_array(underscore, "operandC_" .. func_id, 5000) .. "\n\n")
                                end

                                -- Capture constant arrays
                                local m = W[8]
                                if type(m) == "table" then
                                    log("-- Constants m (W[8]): " .. #m .. " entries")
                                    output_file:write(serialize_array(m, "constants_m_" .. func_id, 2000) .. "\n\n")
                                end

                                local U = W[9]
                                if type(U) == "table" then
                                    log("-- Constants U (W[9]): " .. #U .. " entries")
                                    output_file:write(serialize_array(U, "constants_U_" .. func_id, 2000) .. "\n\n")
                                end

                                local S = W[11]
                                if type(S) == "table" then
                                    log("-- Constants S (W[11]): " .. #S .. " entries")
                                    output_file:write(serialize_array(S, "constants_S_" .. func_id, 2000) .. "\n\n")
                                end

                                -- Store for later analysis
                                captured_functions[func_id] = {
                                    instructions = q,
                                    operandA = N,
                                    operandB = d,
                                    operandC = underscore,
                                    constantsM = m,
                                    constantsU = U,
                                    constantsS = S
                                }
                            end

                            -- Call original interpreter
                            return original_interp(W, y, I)
                        end
                        V[0x28] = V[40]  -- Also set binary version
                    end
                end
            end
        end

        return result
    end
end)

-- Also hook load for Lua 5.2+
rawset(_G, "load", _G.loadstring)

log("-- Hooks installed, loading script...")
log("")

-- Now load and execute the obfuscated script
local f, err = io.open("script.lua", "r")
if not f then
    log("-- Error opening script.lua: " .. tostring(err))
    output_file:close()
    os.exit(1)
end

local script_code = f:read("*a")
f:close()

log("-- Loaded script.lua: " .. #script_code .. " bytes")
log("-- Executing...")
log("")

-- Execute the script (this will trigger our hooks)
local ok, result = pcall(function()
    local fn, err = _G.loadstring(script_code, "script.lua")
    if fn then
        return fn()
    else
        return nil, err
    end
end)

log("")
log("-- Execution " .. (ok and "completed" or "failed"))
if not ok then
    log("-- Error: " .. tostring(result))
end

log("")
log("-- Captured " .. function_counter .. " functions total")
log("-- Data saved to captured_bytecode.lua")

output_file:close()
