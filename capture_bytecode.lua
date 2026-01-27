-- Bytecode Capture Script for Luraph VM
-- Captures decrypted bytecode by hooking the VM execution

-- Lua 5.4 bit32 compatibility layer
bit32 = {
    band = function(a, b, ...)
        a = a or 0
        b = b or 0
        local result = a & b
        for i = 1, select('#', ...) do
            local v = select(i, ...) or 0
            result = result & v
        end
        return result
    end,
    bor = function(a, b, ...)
        a = a or 0
        b = b or 0
        local result = a | b
        for i = 1, select('#', ...) do
            local v = select(i, ...) or 0
            result = result | v
        end
        return result
    end,
    bxor = function(a, b, ...)
        a = a or 0
        b = b or 0
        local result = a ~ b
        for i = 1, select('#', ...) do
            local v = select(i, ...) or 0
            result = result ~ v
        end
        return result
    end,
    bnot = function(a)
        a = a or 0
        return ~a & 0xFFFFFFFF
    end,
    lshift = function(a, b)
        a = a or 0
        b = b or 0
        return (a << b) & 0xFFFFFFFF
    end,
    rshift = function(a, b)
        a = a or 0
        b = b or 0
        return (a & 0xFFFFFFFF) >> b
    end,
    arshift = function(a, b)
        a = (a or 0) & 0xFFFFFFFF
        b = b or 0
        if a >= 0x80000000 then
            return ((a >> b) | (~(0xFFFFFFFF >> b))) & 0xFFFFFFFF
        end
        return a >> b
    end,
    lrotate = function(a, b)
        a = (a or 0) & 0xFFFFFFFF
        b = (b or 0) % 32
        return ((a << b) | (a >> (32 - b))) & 0xFFFFFFFF
    end,
    rrotate = function(a, b)
        a = (a or 0) & 0xFFFFFFFF
        b = (b or 0) % 32
        return ((a >> b) | (a << (32 - b))) & 0xFFFFFFFF
    end,
    extract = function(a, field, width)
        a = a or 0
        field = field or 0
        width = width or 1
        return (a >> field) & ((1 << width) - 1)
    end,
    replace = function(a, v, field, width)
        a = a or 0
        v = v or 0
        field = field or 0
        width = width or 1
        local mask = (1 << width) - 1
        return (a & ~(mask << field)) | ((v & mask) << field)
    end,
    btest = function(...)
        return bit32.band(...) ~= 0
    end,
    countlz = function(a)
        a = (a or 0) & 0xFFFFFFFF
        if a == 0 then return 32 end
        local n = 0
        if a <= 0x0000FFFF then n = n + 16; a = a << 16 end
        if a <= 0x00FFFFFF then n = n + 8; a = a << 8 end
        if a <= 0x0FFFFFFF then n = n + 4; a = a << 4 end
        if a <= 0x3FFFFFFF then n = n + 2; a = a << 2 end
        if a <= 0x7FFFFFFF then n = n + 1 end
        return n
    end,
    countrz = function(a)
        a = (a or 0) & 0xFFFFFFFF
        if a == 0 then return 32 end
        local n = 0
        if (a & 0x0000FFFF) == 0 then n = n + 16; a = a >> 16 end
        if (a & 0x000000FF) == 0 then n = n + 8; a = a >> 8 end
        if (a & 0x0000000F) == 0 then n = n + 4; a = a >> 4 end
        if (a & 0x00000003) == 0 then n = n + 2; a = a >> 2 end
        if (a & 0x00000001) == 0 then n = n + 1 end
        return n
    end
}

-- Luau compatibility
if not getgenv then
    getgenv = function() return _G end
end

-- Wrap string.pack to handle negative numbers for unsigned formats
local original_string_pack = string.pack
string.pack = function(fmt, ...)
    local args = {...}
    local new_args = {}

    -- Convert all numeric arguments that might be negative
    for i, v in ipairs(args) do
        if type(v) == "number" and v < 0 then
            -- Convert to unsigned 32-bit equivalent
            new_args[i] = math.floor(v) & 0xFFFFFFFF
        else
            new_args[i] = v
        end
    end

    local ok, result = pcall(original_string_pack, fmt, table.unpack(new_args))
    if ok then
        return result
    else
        -- If still failing, try to be more aggressive
        for i, v in ipairs(new_args) do
            if type(v) == "number" then
                new_args[i] = math.floor(v) % (2^32)
            end
        end
        return original_string_pack(fmt, table.unpack(new_args))
    end
end

-- Output file
local output = io.open("captured_bytecode.lua", "w")
local function log(msg)
    output:write(msg .. "\n")
    output:flush()
    print(msg)
end

log("-- Luraph VM Bytecode Capture")
log("-- " .. os.date())
log("")

-- Function counter
local func_count = 0

-- Helper to dump arrays
local function dump_array(arr, name, max_len)
    max_len = max_len or 5000
    if type(arr) ~= "table" then
        log(name .. " = " .. tostring(arr))
        return
    end

    local entries = {}
    for i = 1, max_len do
        if arr[i] ~= nil then
            local v = arr[i]
            local vs
            if type(v) == "string" then
                local s = v:sub(1, 100)
                s = s:gsub("\\", "\\\\"):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub('"', '\\"')
                s = s:gsub("[%c]", function(c) return string.format("\\x%02X", string.byte(c)) end)
                vs = string.format('"%s"', s)
                if #v > 100 then vs = vs .. " --[[" .. #v .. " chars]]" end
            elseif type(v) == "number" then
                vs = tostring(v)
            elseif type(v) == "boolean" then
                vs = tostring(v)
            elseif type(v) == "function" then
                vs = "<function>"
            elseif type(v) == "table" then
                vs = "<table:" .. #v .. ">"
            else
                vs = "<" .. type(v) .. ">"
            end
            table.insert(entries, string.format("  [%d] = %s,", i, vs))
        end
    end

    log(name .. " = {")
    for _, e in ipairs(entries) do
        log(e)
    end
    log("}")
    log("")
end

-- Load the VM
log("-- Loading VM code...")
local f = io.open("deobfuscated_lua54.lua", "r")
if not f then
    log("ERROR: Could not open deobfuscated_lua54.lua")
    os.exit(1)
end
local vm_code = f:read("*a")
f:close()
log("-- Loaded " .. #vm_code .. " bytes")

local vm_loader, err = load(vm_code, "vm")
if not vm_loader then
    log("ERROR loading VM: " .. tostring(err))
    os.exit(1)
end

log("-- Executing VM loader...")
local VM = vm_loader()

if type(VM) ~= "table" then
    log("ERROR: VM result is " .. type(VM))
    os.exit(1)
end

log("-- Got VM table")
log("")

-- List VM keys
log("-- VM table structure:")
for k, v in pairs(VM) do
    log("  " .. tostring(k) .. " = " .. type(v))
end
log("")

-- Find the E8 function (main interpreter creator)
local E8 = VM.E8
if not E8 then
    log("ERROR: E8 not found")
    os.exit(1)
end

log("-- Found E8 function, hooking...")

-- Hook E8 to capture bytecode
VM.E8 = function(z, V, B, L)
    log("")
    log("-- E8 called!")
    log("--   z: " .. type(z))
    log("--   V: " .. type(V))

    -- Call original E8
    local ok, err = pcall(E8, z, V, B, L)
    if not ok then
        log("-- E8 error: " .. tostring(err))
    end

    -- Hook the interpreter at V[40]
    local interp = V[40] or V[0x28]
    if interp then
        log("-- Found interpreter, hooking...")

        local orig_interp = interp
        V[40] = function(W, y, I)
            func_count = func_count + 1
            local fid = func_count

            log("")
            log("-- ================================================")
            log("-- FUNCTION PROTOTYPE " .. fid)
            log("-- ================================================")

            if type(W) == "table" then
                log("-- W table has " .. #W .. " array entries")

                -- Capture all W entries
                for i = 1, 15 do
                    local v = W[i]
                    if v ~= nil then
                        if type(v) == "table" then
                            local desc = ""
                            if i == 4 then desc = "operand_A (N)" end
                            if i == 5 then desc = "operand_C (_)" end
                            if i == 7 then desc = "operand_B (d)" end
                            if i == 8 then desc = "constants_m" end
                            if i == 9 then desc = "constants_U" end
                            if i == 10 then desc = "INSTRUCTIONS (q)" end
                            if i == 11 then desc = "constants_S" end
                            log("-- W[" .. i .. "]: table with " .. #v .. " entries  " .. desc)
                            dump_array(v, "W" .. fid .. "_" .. i .. "_" .. desc:gsub("[^%w]", "_"), 3000)
                        else
                            log("-- W[" .. i .. "]: " .. type(v) .. " = " .. tostring(v))
                        end
                    end
                end
            end

            log("-- Calling original interpreter...")
            local results = {pcall(orig_interp, W, y, I)}
            if results[1] then
                log("-- Interpreter returned normally")
                return table.unpack(results, 2)
            else
                log("-- Interpreter error: " .. tostring(results[2]))
                error(results[2])
            end
        end
        V[0x28] = V[40]
    end
end

-- Try to run the VM
log("-- Looking for entry point...")

local wS = VM.wS
if wS then
    log("-- Found wS, attempting to execute...")
    local ok, err = pcall(function()
        VM:wS()
    end)
    if not ok then
        log("-- Execution error: " .. tostring(err))
    else
        log("-- Execution completed")
    end
else
    log("-- wS not found")

    -- Try to find and call any entry function
    for k, v in pairs(VM) do
        if type(v) == "function" and type(k) == "string" then
            log("-- Found function: " .. k)
        end
    end
end

log("")
log("-- ================================================")
log("-- CAPTURE COMPLETE")
log("-- Captured " .. func_count .. " function prototypes")
log("-- ================================================")

output:close()
print("\nData saved to captured_bytecode.lua")
