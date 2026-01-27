-- Luau Runner for Luraph VM
-- Sets up necessary globals and captures bytecode

-- Set up Roblox-like globals
if not getgenv then
    getgenv = function() return _G end
end

if not getrenv then
    getrenv = function() return _G end
end

if not getrawmetatable then
    getrawmetatable = getmetatable
end

if not setrawmetatable then
    setrawmetatable = setmetatable
end

if not hookfunction then
    hookfunction = function(old, new) return old end
end

if not checkcaller then
    checkcaller = function() return true end
end

if not islclosure then
    islclosure = function(f) return type(f) == "function" end
end

if not iscclosure then
    iscclosure = function(f) return false end
end

if not newcclosure then
    newcclosure = function(f) return f end
end

-- Track function prototypes
local captured_functions = {}
local func_count = 0
local max_capture = 50

local function log(msg)
    print(msg)
end

local function dump_array(arr, name, maxlen)
    maxlen = maxlen or 2000
    if type(arr) ~= "table" then
        log(name .. " = " .. tostring(arr))
        return
    end

    local len = 0
    for _ in pairs(arr) do len += 1 end

    log(name .. " = {  -- " .. len .. " entries")

    for i = 1, math.min(len, maxlen) do
        local v = arr[i]
        if v ~= nil then
            if type(v) == "string" then
                local s = string.sub(v, 1, 60)
                s = string.gsub(s, "[%c\\]", function(c)
                    if c == "\n" then return "\\n"
                    elseif c == "\r" then return "\\r"
                    elseif c == "\\" then return "\\\\"
                    else return string.format("\\x%02X", string.byte(c))
                    end
                end)
                log(string.format('  [%d] = "%s",', i, s))
            elseif type(v) == "number" then
                log(string.format("  [%d] = %g,", i, v))
            elseif type(v) == "boolean" then
                log(string.format("  [%d] = %s,", i, tostring(v)))
            else
                log(string.format("  [%d] = <%s>,", i, type(v)))
            end
        end
    end

    if len > maxlen then
        log("  -- (" .. (len - maxlen) .. " more)")
    end
    log("}")
    log("")
end

log("-- ========================================")
log("-- LURAPH RUNTIME CAPTURE")
log("-- ========================================")
log("")

-- Load the VM code
-- The deobfuscated.lua file returns a table
local vm_code = [[VM_CODE_PLACEHOLDER]]

log("-- Loading VM...")
local loader, err = loadstring(vm_code, "vm")
if not loader then
    log("-- ERROR: " .. tostring(err))
    return
end

local VM = loader()
if type(VM) ~= "table" then
    log("-- ERROR: VM is not a table")
    return
end

log("-- VM loaded successfully")

-- Count entries
local count = 0
for _ in pairs(VM) do count += 1 end
log("-- VM has " .. count .. " entries")
log("")

-- Find E8
local E8 = VM.E8
if not E8 then
    log("-- ERROR: E8 not found")
    return
end

log("-- Hooking E8...")

VM.E8 = function(z, V, B, L)
    E8(z, V, B, L)

    local interp = V[40]
    if interp then
        local orig = interp
        V[40] = function(W, y, I)
            func_count += 1

            if func_count <= max_capture then
                log("")
                log("-- FUNCTION " .. func_count)

                if type(W) == "table" then
                    -- W[10] = instructions
                    -- W[11] = strings
                    -- W[9] = constants
                    -- W[4], W[7], W[5] = operands A, B, C

                    if W[10] then dump_array(W[10], "instr_" .. func_count, 1000) end
                    if W[11] then dump_array(W[11], "strings_" .. func_count, 200) end
                    if W[9] then dump_array(W[9], "const_" .. func_count, 200) end
                end
            end

            return orig(W, y, I)
        end
        V[0x28] = V[40]
    end
end

-- Run
log("-- Executing VM...")
local ok, err = pcall(function()
    if VM.wS then
        VM:wS()
    end
end)

if not ok then
    log("-- Error: " .. tostring(err))
end

log("")
log("-- Captured " .. func_count .. " functions")
