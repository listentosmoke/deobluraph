print("Starting VM test...")

-- Minimal mock
game = setmetatable({}, {__index = function() return function() end end})
workspace = {}
script = {}
Instance = {new = function() return {} end}
Vector3 = {new = function() return {} end, zero = {}}
CFrame = {new = function() return {} end, identity = {}}
Color3 = {new = function() return {} end, fromRGB = function() return {} end}
UDim2 = {new = function() return {} end}
Enum = {}
wait = function() return 0 end
task = {spawn = function() end, wait = function() return 0 end, delay = function() end}
spawn = function() end
delay = function() end
tick = function() return 0 end
time = function() return 0 end
typeof = function(v) return type(v) end
warn = print

print("Loading VM...")

local ok, result = pcall(dofile, "decompressed_vm_patched.lua")

print("VM returned:", ok, type(result))

if ok and type(result) == "table" then
    print("VM returned a table, checking keys...")
    local count = 0
    for k, v in pairs(result) do
        count = count + 1
        if count <= 20 then
            print("  Key:", k, "Type:", type(v))
        end
    end
    print("Total keys:", count)
elseif not ok then
    print("Error:", tostring(result))
end

print("Done!")
