-- Luau Debug Capture Script (requires unsandboxed Luau)
-- Uses debug library to hook into VM execution and capture bytecode

print("=== LUAU DEBUG CAPTURE ===")
print("debug library:", debug)

-- Storage for captured data
local captured_functions = {}
local captured_strings = {}
local func_count = 0
local max_funcs = 100

-- Helper to dump a table
local function dump_table(t, name, max_items)
    max_items = max_items or 100
    if type(t) ~= "table" then
        print(name .. " = " .. tostring(t))
        return
    end

    local count = 0
    for _ in pairs(t) do count += 1 end
    print(name .. " = { -- " .. count .. " entries")

    local written = 0
    for i = 1, 10000 do
        if t[i] ~= nil and written < max_items then
            local v = t[i]
            if type(v) == "string" then
                local s = v
                if #s > 60 then s = string.sub(s, 1, 60) .. "..." end
                s = string.gsub(s, "\n", "\\n")
                s = string.gsub(s, "\r", "\\r")
                print(string.format('  [%d] = "%s",', i, s))
            elseif type(v) == "number" or type(v) == "boolean" then
                print(string.format("  [%d] = %s,", i, tostring(v)))
            elseif type(v) == "table" then
                local tlen = 0
                for _ in pairs(v) do tlen += 1 end
                print(string.format("  [%d] = <table:%d>,", i, tlen))
            else
                print(string.format("  [%d] = <%s>,", i, type(v)))
            end
            written += 1
        end
        if written >= max_items then break end
    end

    if count > max_items then
        print("  -- ... " .. (count - max_items) .. " more entries")
    end
    print("}")
end

-- Load the script and get the VM table
print("\nLoading obfuscated script...")
local chunk = loadstring(game and "" or [[
-- Load script.lua content
]] .. (function()
    -- Read file manually since no io library
    -- The script is loaded via command line argument
    return ""
end)())

-- Since we can't use io, we'll load the script via dofile equivalent
-- The unsandboxed Luau should be able to run the script directly

print("\nAttempting to load VM from script...")

-- Try to capture the VM before it executes
-- We'll modify loadstring to intercept

local original_loadstring = loadstring
rawset(_G, "loadstring", function(code, name)
    print("[HOOK] loadstring called with " .. #code .. " bytes")

    local fn, err = original_loadstring(code, name)
    if fn then
        -- Wrap the function to capture its execution
        return function(...)
            print("[HOOK] Executing loaded chunk")
            return fn(...)
        end, err
    end
    return fn, err
end)

-- Create a metatable to intercept global access
local global_mt = {
    __newindex = function(t, k, v)
        print("[GLOBAL] Setting _G." .. tostring(k) .. " = " .. type(v))
        rawset(t, k, v)

        -- If setting VM-like table, hook into it
        if type(v) == "table" and type(k) == "string" then
            local has_E8 = rawget(v, "E8")
            local has_wS = rawget(v, "wS")
            if has_E8 or has_wS then
                print("[DETECT] Found VM-like table: " .. k)
                print("  E8:", has_E8)
                print("  wS:", has_wS)

                -- Hook E8 if present
                if has_E8 and type(has_E8) == "function" then
                    local orig_E8 = has_E8
                    rawset(v, "E8", function(z, V, B, L)
                        print("[E8] Called!")
                        local result = orig_E8(z, V, B, L)

                        -- Check for interpreter at V[40]
                        if type(V) == "table" then
                            local interp = V[40] or V[0x28]
                            if type(interp) == "function" then
                                print("[E8] Found interpreter at V[40]!")
                                local orig_interp = interp

                                V[40] = function(W, y, I)
                                    func_count += 1
                                    if func_count <= max_funcs then
                                        print("\n=== FUNCTION " .. func_count .. " ===")

                                        if type(W) == "table" then
                                            print("Prototype structure:")
                                            for i = 1, 15 do
                                                if W[i] ~= nil then
                                                    local t = type(W[i])
                                                    if t == "table" then
                                                        local cnt = 0
                                                        for _ in pairs(W[i]) do cnt += 1 end
                                                        print(string.format("  W[%d] = table[%d]", i, cnt))
                                                    else
                                                        print(string.format("  W[%d] = %s", i, t))
                                                    end
                                                end
                                            end

                                            -- Capture instructions
                                            if type(W[10]) == "table" then
                                                print("\nINSTRUCTIONS:")
                                                dump_table(W[10], "instructions", 50)
                                            end

                                            -- Capture strings
                                            if type(W[11]) == "table" then
                                                print("\nSTRINGS:")
                                                dump_table(W[11], "strings", 30)
                                            end

                                            -- Store for later
                                            captured_functions[func_count] = {
                                                instructions = W[10],
                                                strings = W[11],
                                                constants = W[9]
                                            }
                                        end
                                    end

                                    return orig_interp(W, y, I)
                                end
                                V[0x28] = V[40]
                            end
                        end

                        return result
                    end)
                end
            end
        end
    end
}

-- Note: Can't set metatable on _G in Luau, so we use a different approach

print("\nScript loaded. Will execute via command line.")
print("Run with: /tmp/luau-src/luau script.lua")

-- Print instructions for manual execution
print([[

To capture bytecode:
1. Copy this script's hooks into script.lua
2. Or use the modified Luau to run the original script with hooks

The VM structure we're looking for:
- E8: interpreter factory function
- V[40]: actual bytecode interpreter
- W[10]: instructions array
- W[11]: strings array
- W[9]: constants array
]])
