-- LuaJIT Debug Capture for Luraph VM
io.stdout:setvbuf("no")  -- Unbuffered output

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

print("1. Loading VM...")
local VM = dofile("/home/user/deobluraph/deobfuscated_standard.lua")
print("2. VM loaded")

-- Output file
local outfile = io.open("/home/user/deobluraph/captured_luajit.lua", "w")
outfile:write("-- Captured bytecode\nlocal captured = {\n")

local func_count = 0
local max_funcs = 50

-- Hook E8
local E8 = VM.E8
print("3. E8 found, hooking...")

VM.E8 = function(z, V, B, L)
    print("4. E8 called")
    E8(z, V, B, L)
    print("5. Original E8 returned")

    local interp = V[40]
    if interp and type(interp) == "function" then
        print("6. Found interpreter at V[40]")
        local orig_interp = interp

        V[40] = function(W, y, I)
            func_count = func_count + 1
            if func_count <= max_funcs then
                print("7. Function " .. func_count .. " called")

                outfile:write(string.format("  func_%d = {\n", func_count))

                if type(W) == "table" and type(W[10]) == "table" then
                    local cnt = 0
                    for _ in pairs(W[10]) do cnt = cnt + 1 end
                    print("   Instructions: " .. cnt)
                    outfile:write("    instructions = {\n")
                    local written = 0
                    for i = 1, 5000 do
                        if W[10][i] ~= nil then
                            outfile:write(string.format("      [%d] = %s,\n", i, tostring(W[10][i])))
                            written = written + 1
                            if written >= 1000 then break end
                        elseif written > 0 and i > written + 10 then
                            break
                        end
                    end
                    outfile:write("    },\n")
                end

                if type(W) == "table" and type(W[11]) == "table" then
                    local cnt = 0
                    for _ in pairs(W[11]) do cnt = cnt + 1 end
                    print("   Strings: " .. cnt)
                    outfile:write("    strings = {\n")
                    local written = 0
                    for i = 1, 500 do
                        if W[11][i] ~= nil then
                            local s = tostring(W[11][i]):sub(1, 80)
                            s = s:gsub("\\", "\\\\"):gsub("\n", "\\n"):gsub('"', '\\"')
                            outfile:write(string.format('      [%d] = "%s",\n', i, s))
                            written = written + 1
                            if written >= 200 then break end
                        elseif written > 0 and i > written + 10 then
                            break
                        end
                    end
                    outfile:write("    },\n")
                end

                outfile:write("  },\n")
                outfile:flush()
            end

            return orig_interp(W, y, I)
        end

        V[0x28] = V[40]
        print("8. Hook installed")
    else
        print("6. Interpreter NOT found at V[40]")
    end
end

print("9. Starting wS...")
local ok, err = pcall(function() VM:wS() end)
if ok then
    print("10. wS completed normally")
else
    print("10. wS error: " .. tostring(err))
end

outfile:write("}\nreturn captured\n")
outfile:close()

print("Done! Captured " .. func_count .. " functions")
