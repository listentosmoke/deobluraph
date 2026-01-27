-- Luau Runtime Capture for Luraph VM
-- This file should be concatenated with the VM code
-- Usage: (echo "local VM = "; cat deobfuscated.lua; cat luau_capture.lua) | luau -

local function log(msg)
    print(msg)
end

log("-- ============================================")
log("-- LURAPH RUNTIME BYTECODE CAPTURE")
log("-- Using Luau interpreter")
log("-- ============================================")
log("")

-- Function counter
local func_count = 0
local max_funcs = 100

-- Captured data storage
local captured = {}

-- Helper to dump arrays
local function dump_array(arr, name, max_len)
    max_len = max_len or 3000
    if type(arr) ~= "table" then
        log(name .. " = " .. tostring(arr))
        return
    end

    local len = 0
    for _ in pairs(arr) do len += 1 end

    log(name .. " = {  -- " .. len .. " entries")

    for i = 1, math.min(len, max_len) do
        local v = arr[i]
        if v ~= nil then
            if type(v) == "string" then
                local s = v
                if #s > 60 then s = string.sub(s, 1, 60) .. "..." end
                s = string.gsub(s, "\\", "\\\\")
                s = string.gsub(s, "\n", "\\n")
                s = string.gsub(s, "\r", "\\r")
                s = string.gsub(s, '"', '\\"')
                s = string.gsub(s, "[%c]", function(c)
                    return string.format("\\x%02X", string.byte(c))
                end)
                log(string.format('  [%d] = "%s",', i, s))
            elseif type(v) == "number" then
                log(string.format("  [%d] = %s,", i, tostring(v)))
            elseif type(v) == "boolean" then
                log(string.format("  [%d] = %s,", i, tostring(v)))
            elseif type(v) == "function" then
                log(string.format("  [%d] = <function>,", i))
            elseif type(v) == "table" then
                local tlen = 0
                for _ in pairs(v) do tlen += 1 end
                log(string.format("  [%d] = <table:%d>,", i, tlen))
            else
                log(string.format("  [%d] = <%s>,", i, type(v)))
            end
        end
    end

    if len > max_len then
        log("  -- ... " .. (len - max_len) .. " more entries truncated")
    end
    log("}")
    log("")
end

-- Check if VM is defined
if not VM or type(VM) ~= "table" then
    log("-- ERROR: VM not defined or not a table")
    log("-- Make sure to prepend 'local VM = ' before the deobfuscated code")
    return
end

log("-- VM table loaded successfully")

-- Count VM entries
local vm_count = 0
for k, v in pairs(VM) do
    vm_count += 1
end
log("-- VM has " .. vm_count .. " entries")
log("")

-- Find E8 (main interpreter setup function)
local E8 = VM.E8
if not E8 then
    log("-- ERROR: E8 function not found")
    log("-- Available keys:")
    for k, v in pairs(VM) do
        if type(k) == "string" then
            log("  " .. k .. " = " .. type(v))
        end
    end
    return
end

log("-- Found E8 function")
log("-- Installing bytecode capture hooks...")
log("")

-- Hook E8
VM.E8 = function(z, V, B, L)
    log("-- [HOOK] E8 called")

    -- Call original E8
    E8(z, V, B, L)

    -- V[40] (0x28 = 40) should now contain the interpreter function
    local interp = V[40] or V[0x28]
    if interp and type(interp) == "function" then
        log("-- [HOOK] Found interpreter at V[40]")

        local orig_interp = interp

        -- Hook the interpreter to capture each function's bytecode
        V[40] = function(W, y, I)
            func_count += 1
            local fid = func_count

            if fid <= max_funcs then
                log("")
                log("-- ============================================")
                log("-- FUNCTION " .. fid)
                log("-- ============================================")

                if type(W) == "table" then
                    -- W contains the function prototype data:
                    -- W[1] = info/stack size
                    -- W[4] = operand A array (N)
                    -- W[5] = operand C array (_)
                    -- W[7] = operand B array (d)
                    -- W[8] = constants m (numbers)
                    -- W[9] = constants U (mixed)
                    -- W[10] = INSTRUCTIONS (q) - the bytecode opcodes!
                    -- W[11] = constants S (strings)

                    log("-- Prototype structure:")
                    for i = 1, 15 do
                        local v = W[i]
                        if v ~= nil then
                            local desc = ""
                            if i == 1 then desc = " (info)" end
                            if i == 4 then desc = " (operand_A)" end
                            if i == 5 then desc = " (operand_C)" end
                            if i == 7 then desc = " (operand_B)" end
                            if i == 8 then desc = " (constants_m)" end
                            if i == 9 then desc = " (constants_U)" end
                            if i == 10 then desc = " (INSTRUCTIONS)" end
                            if i == 11 then desc = " (constants_S)" end

                            if type(v) == "table" then
                                local tlen = 0
                                for _ in pairs(v) do tlen += 1 end
                                log("--   W[" .. i .. "]: table[" .. tlen .. "]" .. desc)
                            else
                                log("--   W[" .. i .. "]: " .. type(v) .. " = " .. tostring(v) .. desc)
                            end
                        end
                    end
                    log("")

                    -- Dump the important arrays
                    if type(W[10]) == "table" then
                        dump_array(W[10], "instructions_" .. fid, 2000)
                    end

                    if type(W[11]) == "table" then
                        dump_array(W[11], "strings_" .. fid, 500)
                    end

                    if type(W[9]) == "table" then
                        dump_array(W[9], "constants_" .. fid, 500)
                    end

                    if type(W[4]) == "table" then
                        dump_array(W[4], "operandA_" .. fid, 2000)
                    end

                    if type(W[7]) == "table" then
                        dump_array(W[7], "operandB_" .. fid, 2000)
                    end

                    if type(W[5]) == "table" then
                        dump_array(W[5], "operandC_" .. fid, 2000)
                    end

                    -- Store for later
                    captured[fid] = {
                        instructions = W[10],
                        strings = W[11],
                        constants = W[9],
                        operandA = W[4],
                        operandB = W[7],
                        operandC = W[5]
                    }
                end

                log("-- End function " .. fid)
            elseif fid == max_funcs + 1 then
                log("")
                log("-- [LIMIT] Reached " .. max_funcs .. " functions, stopping capture")
            end

            -- Call original interpreter
            return orig_interp(W, y, I)
        end

        V[0x28] = V[40]  -- Also update hex-indexed version
        log("-- [HOOK] Interpreter hook installed")
    else
        log("-- [WARNING] Interpreter not found at V[40]")
    end
end

-- Try to find and call the entry point
log("")
log("-- Looking for entry point...")

local wS = VM.wS
if wS then
    log("-- Found wS entry function")
    log("-- Starting VM execution...")
    log("")

    local success, err = pcall(function()
        VM:wS()
    end)

    if success then
        log("")
        log("-- VM execution completed normally")
    else
        log("")
        log("-- VM execution error: " .. tostring(err))
    end
else
    log("-- wS not found")
    log("-- Available entry points:")
    for k, v in pairs(VM) do
        if type(v) == "function" and type(k) == "string" then
            log("  " .. k .. "()")
        end
    end
end

log("")
log("-- ============================================")
log("-- CAPTURE SUMMARY")
log("-- ============================================")
log("-- Total functions captured: " .. func_count)
log("-- Data stored in 'captured' table")
log("")
