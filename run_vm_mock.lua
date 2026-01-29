-- Mock Roblox environment for VM execution
local traces = {}
local log_count = 0

local function log(...)
    log_count = log_count + 1
    if log_count > 1000 then return end  -- Limit logging
    local parts = {}
    for i = 1, select("#", ...) do
        local v = select(i, ...)
        if type(v) == "string" and #v > 50 then
            parts[i] = '"' .. v:sub(1,50) .. '..."'
        elseif type(v) == "string" then
            parts[i] = '"' .. v .. '"'
        else
            parts[i] = tostring(v)
        end
    end
    local line = table.concat(parts, "\t")
    table.insert(traces, line)
end

-- Mock creator
local function make_mock(name)
    local m = {}
    setmetatable(m, {
        __index = function(self, k)
            log("GET", name, k)
            return make_mock(name .. "." .. tostring(k))
        end,
        __newindex = function(self, k, v)
            log("SET", name, k, type(v))
        end,
        __call = function(self, ...)
            log("CALL", name, ...)
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
    })
    return m
end

-- Setup globals
local g_mock = make_mock("game")
rawset(g_mock, "GetService", function(self, svc)
    log("GetService", svc)
    return make_mock("svc:" .. svc)
end)

game = g_mock
workspace = make_mock("workspace")
script = make_mock("script")
Instance = { new = function(c, p) log("Instance.new", c); return make_mock("inst:" .. c) end }
Vector3 = { new = function(...) return make_mock("Vec3") end, zero = {X=0,Y=0,Z=0} }
CFrame = { new = function(...) return make_mock("CF") end, identity = make_mock("CF.id") }
Color3 = { new = function(...) return {R=0,G=0,B=0} end, fromRGB = function(...) return {R=0,G=0,B=0} end }
UDim2 = { new = function(...) return make_mock("UDim2") end }
Enum = make_mock("Enum")
wait = function(t) log("wait", t); return t or 0 end
task = {
    spawn = function(f) log("task.spawn"); pcall(f) end,
    wait = function(t) log("task.wait", t); return t or 0 end,
    delay = function(t, f) log("task.delay", t) end,
}
spawn = function(f) log("spawn"); pcall(f) end
delay = function(t, f) log("delay", t) end
tick = function() return os.clock() end
time = function() return os.clock() end
typeof = function(v) return type(v) end
warn = function(...) log("warn", ...) end

local orig_print = print
print = function(...) log("print", ...) end

log("INIT_DONE")

-- Execute VM
local ok, result = pcall(dofile, "decompressed_vm_patched.lua")
if ok then
    log("VM_OK", type(result))
    if type(result) == "table" then
        local count = 0
        for k, v in pairs(result) do
            count = count + 1
            if count <= 50 then
                log("RESULT_KEY", tostring(k), type(v))
            end
        end
        log("RESULT_TOTAL_KEYS", count)
    end
else
    log("VM_ERROR", tostring(result))
end

-- Output traces at the end
for i = 1, math.min(#traces, 200) do
    print(traces[i])
end
print("Total traces:", #traces)
