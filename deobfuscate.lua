-- Luraph v14.5.2 Deobfuscator
-- Hooks loadstring to capture decompressed code before execution

local output_file = "deobfuscated.lua"
local captured_code = nil

-- Lua 5.4 compatibility: unpack is now table.unpack
if not unpack then
    rawset(_G, "unpack", table.unpack)
end

-- Provide required Roblox/executor globals if missing
if not getgenv then
    rawset(_G, "getgenv", function() return _G end)
end

-- Store original functions
local original_loadstring = loadstring or load
local original_load = load

-- Hook loadstring to capture the decompressed code
local function hooked_loadstring(code, chunkname, ...)
    if type(code) == "string" and #code > 100 then
        -- Check if this looks like actual Lua code (not bytecode)
        if code:sub(1, 4) ~= "\27Lua" then
            captured_code = code
            print("[Deobfuscator] Captured decompressed code (" .. #code .. " bytes)")

            -- Write to file
            local f = io.open(output_file, "w")
            if f then
                f:write(code)
                f:close()
                print("[Deobfuscator] Written to: " .. output_file)
            end
        else
            print("[Deobfuscator] Captured Lua bytecode (" .. #code .. " bytes)")
            -- For bytecode, we'll need to handle it differently
            captured_code = code

            local f = io.open(output_file .. ".luac", "wb")
            if f then
                f:write(code)
                f:close()
                print("[Deobfuscator] Bytecode written to: " .. output_file .. ".luac")
            end
        end
    end

    -- Return a function that does nothing to prevent execution
    return function()
        print("[Deobfuscator] Execution blocked - code captured successfully")
        return nil
    end, nil
end

-- Hook load function as well
local function hooked_load(chunk, chunkname, mode, env)
    if type(chunk) == "string" then
        return hooked_loadstring(chunk, chunkname)
    end
    return original_load(chunk, chunkname, mode, env)
end

-- Replace global functions
rawset(_G, "loadstring", hooked_loadstring)
rawset(_G, "load", hooked_load)

-- Also patch string.pack if it doesn't exist (Lua 5.1/5.2 compatibility)
if not string.pack then
    string.pack = function(fmt, ...)
        local args = {...}
        if fmt == ">I4" then
            local n = args[1]
            local b1 = math.floor(n / 16777216) % 256
            local b2 = math.floor(n / 65536) % 256
            local b3 = math.floor(n / 256) % 256
            local b4 = n % 256
            return string.char(b1, b2, b3, b4)
        end
        return ""
    end
end

print("[Deobfuscator] Hooks installed, loading obfuscated script...")
print("=" .. string.rep("=", 59))

-- Load and execute the obfuscated script
local success, err = pcall(function()
    dofile("script.lua")
end)

if not success then
    print("[Deobfuscator] Script execution error (expected): " .. tostring(err))
end

print("=" .. string.rep("=", 59))

if captured_code then
    print("[Deobfuscator] SUCCESS - Code captured!")
    print("[Deobfuscator] Output file: " .. output_file)
    print("[Deobfuscator] Code size: " .. #captured_code .. " bytes")
else
    print("[Deobfuscator] WARNING - No code was captured")
    print("[Deobfuscator] The script may use a different loading mechanism")
end
