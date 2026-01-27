-- LuaJIT Minimal Capture - no hook overhead during decompression
io.stdout:setvbuf("no")

local bit = require("bit")
bit32 = {
    band = bit.band, bor = bit.bor, bxor = bit.bxor, bnot = bit.bnot,
    lshift = bit.lshift, rshift = bit.rshift, arshift = bit.arshift,
    lrotate = bit.rol, rrotate = bit.ror,
    btest = function(a, b) return bit.band(a, b) ~= 0 end,
    extract = function(n, field, width)
        width = width or 1
        return bit.band(bit.rshift(n, field), bit.lshift(1, width) - 1)
    end,
    replace = function(n, v, field, width)
        width = width or 1
        local mask = bit.lshift(1, width) - 1
        return bit.bor(bit.band(n, bit.bnot(bit.lshift(mask, field))),
                       bit.lshift(bit.band(v, mask), field))
    end,
    countlz = function(a)
        a = bit.band(a or 0, 0xFFFFFFFF)
        if a == 0 then return 32 end
        local n = 0
        if bit.band(a, 0xFFFF0000) == 0 then n = n + 16; a = bit.lshift(a, 16) end
        if bit.band(a, 0xFF000000) == 0 then n = n + 8; a = bit.lshift(a, 8) end
        if bit.band(a, 0xF0000000) == 0 then n = n + 4; a = bit.lshift(a, 4) end
        if bit.band(a, 0xC0000000) == 0 then n = n + 2; a = bit.lshift(a, 2) end
        if bit.band(a, 0x80000000) == 0 then n = n + 1 end
        return n
    end,
    countrz = function(a)
        a = bit.band(a or 0, 0xFFFFFFFF)
        if a == 0 then return 32 end
        local n = 0
        if bit.band(a, 0x0000FFFF) == 0 then n = n + 16; a = bit.rshift(a, 16) end
        if bit.band(a, 0x000000FF) == 0 then n = n + 8; a = bit.rshift(a, 8) end
        if bit.band(a, 0x0000000F) == 0 then n = n + 4; a = bit.rshift(a, 4) end
        if bit.band(a, 0x00000003) == 0 then n = n + 2; a = bit.rshift(a, 2) end
        if bit.band(a, 0x00000001) == 0 then n = n + 1 end
        return n
    end
}

if not table.move then
    table.move = function(a1, f, e, t, a2)
        a2 = a2 or a1
        if t <= f or a1 ~= a2 then
            for i = f, e do a2[t + (i - f)] = a1[i] end
        else
            for i = e, f, -1 do a2[t + (i - f)] = a1[i] end
        end
        return a2
    end
end

print("Loading VM...")
local VM = dofile("/home/user/deobluraph/deobfuscated_standard.lua")
print("VM loaded")

-- Only hook E8 - no other hooks to maintain speed
local E8_orig = VM.E8
local captured = {}
local func_count = 0

VM.E8 = function(z, V, B, L)
    print("E8 called!")
    E8_orig(z, V, B, L)

    -- Hook the interpreter
    local interp = V[40]
    if interp and type(interp) == "function" then
        print("Interpreter found!")
        local orig_interp = interp

        V[40] = function(W, y, I)
            func_count = func_count + 1
            if func_count <= 100 then
                print("Function " .. func_count)
                if type(W) == "table" then
                    captured[func_count] = {
                        instructions = W[10],
                        strings = W[11],
                        constants = W[9],
                        operandA = W[4],
                        operandB = W[7],
                        operandC = W[5]
                    }
                end
            end
            return orig_interp(W, y, I)
        end
        V[0x28] = V[40]
    end
end

print("Starting execution (decompression may take a while)...")
local start_time = os.time()
local ok, err = pcall(function() VM:wS() end)
local elapsed = os.time() - start_time

if ok then
    print("Execution completed in " .. elapsed .. "s")
else
    print("Error after " .. elapsed .. "s: " .. tostring(err))
end

print("Functions captured: " .. func_count)

-- Write captured data
if func_count > 0 then
    local f = io.open("/home/user/deobluraph/captured_bytecode.lua", "w")
    f:write("-- Captured bytecode from Luraph VM\n")
    f:write("-- Functions: " .. func_count .. "\n\n")
    f:write("local bytecode = {\n")

    for fid, data in pairs(captured) do
        f:write(string.format("\n  -- Function %d\n", fid))
        f:write(string.format("  [%d] = {\n", fid))

        if data.instructions then
            f:write("    instructions = {\n")
            local cnt = 0
            for i = 1, 5000 do
                if data.instructions[i] then
                    f:write(string.format("      [%d] = %s,\n", i, tostring(data.instructions[i])))
                    cnt = cnt + 1
                    if cnt >= 2000 then break end
                elseif cnt > 0 and i > cnt + 10 then
                    break
                end
            end
            f:write("    },\n")
        end

        if data.strings then
            f:write("    strings = {\n")
            local cnt = 0
            for i = 1, 500 do
                if data.strings[i] then
                    local s = tostring(data.strings[i]):sub(1, 100)
                    s = s:gsub("\\", "\\\\"):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub('"', '\\"')
                    f:write(string.format('      [%d] = "%s",\n', i, s))
                    cnt = cnt + 1
                    if cnt >= 200 then break end
                elseif cnt > 0 and i > cnt + 10 then
                    break
                end
            end
            f:write("    },\n")
        end

        if data.constants then
            f:write("    constants = {\n")
            local cnt = 0
            for i = 1, 500 do
                if data.constants[i] ~= nil then
                    local v = data.constants[i]
                    if type(v) == "string" then
                        local s = v:sub(1, 100)
                        s = s:gsub("\\", "\\\\"):gsub("\n", "\\n"):gsub('"', '\\"')
                        f:write(string.format('      [%d] = "%s",\n', i, s))
                    elseif type(v) == "number" or type(v) == "boolean" then
                        f:write(string.format("      [%d] = %s,\n", i, tostring(v)))
                    end
                    cnt = cnt + 1
                    if cnt >= 200 then break end
                elseif cnt > 0 and i > cnt + 10 then
                    break
                end
            end
            f:write("    },\n")
        end

        f:write("  },\n")
    end

    f:write("}\n\nreturn bytecode\n")
    f:close()
    print("Data written to captured_bytecode.lua")
end
