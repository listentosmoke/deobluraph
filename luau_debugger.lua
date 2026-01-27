-- Luau Runtime Debugger for Luraph VM
-- Captures decrypted bytecode by hooking VM execution
-- Output goes to stdout (pipe to file)

local function log(msg)
    print(msg)
end

log("-- Luraph Runtime Capture via Luau")
log("-- Timestamp: " .. os.date())
log("")

-- Function counter
local func_count = 0
local max_funcs = 50  -- Limit to avoid huge output

-- Helper to serialize arrays
local function dump_array(arr, name, max_len)
    max_len = max_len or 5000
    if type(arr) ~= "table" then
        log(name .. " = " .. tostring(arr))
        return
    end

    local len = 0
    for _ in pairs(arr) do len += 1 end

    log(name .. " = {  -- " .. len .. " entries")

    local count = 0
    for i = 1, max_len do
        local v = arr[i]
        if v ~= nil then
            count += 1
            if type(v) == "string" then
                local s = v
                if #s > 80 then s = string.sub(s, 1, 80) .. "..." end
                s = string.gsub(s, "\\", "\\\\")
                s = string.gsub(s, "\n", "\\n")
                s = string.gsub(s, "\r", "\\r")
                s = string.gsub(s, '"', '\\"')
                s = string.gsub(s, "[%c]", function(c) return string.format("\\x%02X", string.byte(c)) end)
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
        log("  -- ... " .. (len - max_len) .. " more entries")
    end
    log("}")
    log("")
end

-- We need to load the VM code
-- Since Luau doesn't have io.open, we'll embed it or use require

-- Try to use require with a custom loader
-- Actually, let's use the fact that Luau can read files via require
-- But require expects module format...

-- Alternative: read via debug library if available
-- Or: we can concatenate the files before running

log("-- This script needs the VM code embedded")
log("-- Run with: cat deobfuscated.lua luau_hook.lua | luau -")
log("")

-- The actual hook code will be appended below
-- It expects VM to be defined as the result of the deobfuscated.lua
