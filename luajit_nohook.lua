-- LuaJIT No Hook Test - just run and see what happens
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

print("Loading...")
local VM = dofile("/home/user/deobluraph/deobfuscated_standard.lua")
print("Loaded. Running wS()...")
io.flush()

local start = os.time()
local ok, err = pcall(function() VM:wS() end)
local elapsed = os.time() - start

print("Result after " .. elapsed .. "s:")
if ok then
    print("SUCCESS!")
else
    print("Error: " .. tostring(err))
end
