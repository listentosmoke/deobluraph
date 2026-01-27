-- LuaJIT Trace Capture for Luraph VM
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

-- Hook ALL functions in VM to trace execution
local call_count = 0
local max_calls = 10000
local captured_data = {}

for name, func in pairs(VM) do
    if type(func) == "function" then
        local orig = func
        VM[name] = function(...)
            call_count = call_count + 1
            if call_count <= 50 or name == "E8" or call_count % 1000 == 0 then
                print(string.format("[%d] Calling %s", call_count, name))
                io.flush()
            end

            -- Special handling for E8 to capture bytecode
            if name == "E8" then
                local results = {orig(...)}
                -- After E8, check for interpreter in V table
                local self = select(1, ...)
                local V = select(2, ...)
                if type(V) == "table" and type(V[40]) == "function" then
                    print("[E8] Found interpreter at V[40]!")
                    local orig_interp = V[40]
                    V[40] = function(W, y, I)
                        print("[INTERP] Called!")
                        if type(W) == "table" then
                            for i = 1, 15 do
                                if W[i] ~= nil then
                                    local t = type(W[i])
                                    if t == "table" then
                                        local cnt = 0
                                        for _ in pairs(W[i]) do cnt = cnt + 1 end
                                        print(string.format("  W[%d] = table[%d]", i, cnt))
                                    else
                                        print(string.format("  W[%d] = %s", i, t))
                                    end
                                end
                            end

                            -- Store instructions
                            if type(W[10]) == "table" then
                                table.insert(captured_data, {
                                    instructions = W[10],
                                    strings = W[11],
                                    constants = W[9]
                                })
                            end
                        end
                        return orig_interp(W, y, I)
                    end
                    V[0x28] = V[40]
                end
                return unpack(results)
            end

            return orig(...)
        end
    end
end

print("All hooks installed")
print("Starting wS...")
io.flush()

local ok, err = pcall(function() VM:wS() end)
if ok then
    print("wS completed")
else
    print("wS error: " .. tostring(err))
end

print("Total calls: " .. call_count)
print("Captured functions: " .. #captured_data)

-- Write captured data
if #captured_data > 0 then
    local f = io.open("/home/user/deobluraph/captured_data.lua", "w")
    f:write("-- Captured bytecode data\nlocal data = {\n")
    for i, d in ipairs(captured_data) do
        f:write(string.format("  func_%d = {\n", i))
        if d.instructions then
            f:write("    instructions = {\n")
            local cnt = 0
            for j = 1, 2000 do
                if d.instructions[j] then
                    f:write(string.format("      [%d] = %s,\n", j, tostring(d.instructions[j])))
                    cnt = cnt + 1
                    if cnt >= 1000 then break end
                elseif cnt > 0 and j > cnt + 10 then break end
            end
            f:write("    },\n")
        end
        f:write("  },\n")
    end
    f:write("}\nreturn data\n")
    f:close()
    print("Data written to captured_data.lua")
end
