print("Starting VM trace test...")

local missing_globals = {}
local call_log = {}

-- Create metatable that tracks nil accesses
local global_mt = {
    __index = function(t, k)
        if not missing_globals[k] then
            missing_globals[k] = true
            table.insert(call_log, "MISSING_GLOBAL: " .. tostring(k))
        end
        -- Return a callable mock
        return setmetatable({}, {
            __call = function(self, ...)
                table.insert(call_log, "CALLED: " .. tostring(k))
                return setmetatable({}, {
                    __index = function(self2, k2)
                        return function() return {} end
                    end,
                    __call = function() return {} end,
                })
            end,
            __index = function(self, k2)
                table.insert(call_log, "INDEX: " .. tostring(k) .. "." .. tostring(k2))
                return function(...) return {} end
            end,
        })
    end
}

-- Set up minimal globals first
local svc_mock = setmetatable({}, {
    __index = function(self, k)
        table.insert(call_log, "SERVICE_INDEX: " .. tostring(k))
        return setmetatable({}, {
            __index = function(self2, k2)
                return function() return {} end
            end,
            __call = function() return {} end,
        })
    end,
})

local game_mock = setmetatable({
    GetService = function(self, name)
        table.insert(call_log, "GetService: " .. tostring(name))
        return svc_mock
    end,
}, {
    __index = function(self, k)
        table.insert(call_log, "GAME_INDEX: " .. tostring(k))
        return svc_mock
    end,
})

-- Core globals
rawset(_G, "game", game_mock)
rawset(_G, "workspace", svc_mock)
rawset(_G, "script", svc_mock)
rawset(_G, "Instance", {new = function(c) table.insert(call_log, "Instance.new: " .. tostring(c)); return svc_mock end})
rawset(_G, "Vector3", {new = function() return {} end, zero = {}})
rawset(_G, "CFrame", {new = function() return {} end, identity = {}})
rawset(_G, "Color3", {new = function() return {} end, fromRGB = function() return {} end})
rawset(_G, "UDim2", {new = function() return {} end})
rawset(_G, "Enum", svc_mock)
rawset(_G, "wait", function(t) return t or 0 end)
rawset(_G, "task", {spawn = function(f) pcall(f) end, wait = function(t) return t or 0 end, delay = function() end})
rawset(_G, "spawn", function(f) pcall(f) end)
rawset(_G, "delay", function() end)
rawset(_G, "tick", function() return os.clock() end)
rawset(_G, "time", function() return os.clock() end)
rawset(_G, "typeof", function(v) return type(v) end)
rawset(_G, "warn", print)

-- Set metatable to catch undefined globals
setmetatable(_G, global_mt)

print("Loading VM...")

local ok, result = pcall(dofile, "decompressed_vm_patched.lua")

print("VM returned:", ok, type(result))

if not ok then
    print("Error:", tostring(result))
end

print("\nCall log (first 50):")
for i = 1, math.min(#call_log, 50) do
    print("  " .. call_log[i])
end

print("\nMissing globals:")
for k in pairs(missing_globals) do
    print("  " .. k)
end

print("\nDone!")
