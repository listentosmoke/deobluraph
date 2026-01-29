print("Starting VM trace test...")

local call_log = {}

-- Create mock that logs and returns itself
local function make_mock(name)
    local m = {}
    return setmetatable(m, {
        __index = function(self, k)
            if #call_log < 500 then
                table.insert(call_log, "GET " .. name .. "." .. tostring(k))
            end
            return make_mock(name .. "." .. tostring(k))
        end,
        __newindex = function(self, k, v)
            if #call_log < 500 then
                table.insert(call_log, "SET " .. name .. "." .. tostring(k))
            end
        end,
        __call = function(self, ...)
            if #call_log < 500 then
                table.insert(call_log, "CALL " .. name)
            end
            return make_mock(name .. "()")
        end,
        __tostring = function() return "Mock:" .. name end,
        __add = function() return 0 end,
        __sub = function() return 0 end,
        __mul = function() return 0 end,
        __div = function() return 1 end,
        __eq = function() return false end,
        __lt = function() return false end,
        __le = function() return false end,
        __len = function() return 0 end,
        __unm = function() return 0 end,
        __concat = function(a, b) return tostring(a) .. tostring(b) end,
    })
end

-- Game with GetService
local game_mock = make_mock("game")
game_mock.GetService = function(self, svc)
    if #call_log < 500 then
        table.insert(call_log, "GetService(" .. tostring(svc) .. ")")
    end
    return make_mock("service:" .. tostring(svc))
end

-- Set globals directly (no rawset)
game = game_mock
workspace = make_mock("workspace")
script = make_mock("script")
Instance = { new = function(c) table.insert(call_log, "Instance.new(" .. tostring(c) .. ")"); return make_mock("Instance:" .. tostring(c)) end }
Vector3 = { new = function(...) return {X=0,Y=0,Z=0} end, zero = {X=0,Y=0,Z=0} }
CFrame = { new = function(...) return make_mock("CFrame") end, identity = make_mock("CFrame.identity") }
Color3 = { new = function(...) return {R=0,G=0,B=0} end, fromRGB = function(...) return {R=0,G=0,B=0} end }
UDim2 = { new = function(...) return make_mock("UDim2") end }
Enum = make_mock("Enum")
wait = function(t) return t or 0 end
task = { spawn = function(f) pcall(f) end, wait = function(t) return t or 0 end, delay = function() end }
spawn = function(f) pcall(f) end
delay = function() end
tick = function() return os.clock() end
time = function() return os.clock() end
typeof = function(v) return type(v) end
warn = function(...) table.insert(call_log, "warn(...)") end

print("Loading VM...")

local ok, result = xpcall(function()
    return dofile("decompressed_vm_patched.lua")
end, function(err)
    return tostring(err) .. "\n" .. debug.traceback()
end)

print("VM result:", ok, type(result))

if not ok then
    print("Error:", tostring(result))
end

if ok and type(result) == "table" then
    print("\nResult table keys:")
    local count = 0
    for k, v in pairs(result) do
        count = count + 1
        if count <= 30 then
            print("  " .. tostring(k) .. " = " .. type(v))
        end
    end
    print("Total keys:", count)
end

print("\nCall log (first 100):")
for i = 1, math.min(#call_log, 100) do
    print("  " .. call_log[i])
end

print("\nTotal logged calls:", #call_log)
print("Done!")
