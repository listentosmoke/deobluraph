-- Luau-native execution wrapper
-- This file will be run with Luau interpreter

local traces = {}
local trace_count = 0

local function log(...)
    trace_count = trace_count + 1
    if trace_count <= 100000 then
        local parts = {}
        for i = 1, select("#", ...) do
            local v = select(i, ...)
            if type(v) == "string" and #v > 50 then
                parts[i] = string.format('"%s..."', v:sub(1,50):gsub("\n", "\\n"))
            elseif type(v) == "string" then
                parts[i] = string.format('"%s"', v:gsub("\n", "\\n"))
            elseif type(v) == "table" then
                parts[i] = "<table>"
            elseif type(v) == "function" then
                parts[i] = "<function>"
            else
                parts[i] = tostring(v)
            end
        end
        traces[trace_count] = table.concat(parts, "\t")
    end
end

-- Mock Roblox environment
local mock = {}
setmetatable(mock, {
    __index = function(self, k)
        log("MOCK_INDEX", k)
        return mock
    end,
    __newindex = function(self, k, v)
        log("MOCK_NEWINDEX", k, type(v))
    end,
    __call = function(self, ...)
        log("MOCK_CALL", ...)
        return mock
    end,
    __tostring = function() return "Mock" end,
})

local game_mock = setmetatable({}, {
    __index = function(self, k)
        if k == "GetService" then
            return function(_, name)
                log("GetService", name)
                return mock
            end
        end
        log("game_index", k)
        return mock
    end
})

-- Create the sandboxed environment
local env = {
    print = function(...) log("print", ...) end,
    warn = function(...) log("warn", ...) end,
    error = function(msg) log("error", msg); error(msg) end,
    assert = assert,
    type = type,
    typeof = function(v) return type(v) end,
    tostring = tostring,
    tonumber = tonumber,
    pairs = pairs,
    ipairs = ipairs,
    next = next,
    select = select,
    unpack = unpack or table.unpack,
    pcall = function(f, ...)
        log("pcall_start")
        local ok, err = pcall(f, ...)
        log("pcall_end", ok, err)
        return ok, err
    end,
    xpcall = xpcall,
    setmetatable = setmetatable,
    getmetatable = getmetatable,
    rawget = rawget,
    rawset = rawset,
    rawequal = rawequal,
    newproxy = function() return {} end,

    string = string,
    table = table,
    math = math,
    bit32 = bit32,
    coroutine = coroutine,
    os = { time = os.time, clock = os.clock, date = os.date },
    debug = nil,

    game = game_mock,
    workspace = mock,
    script = mock,
    Instance = { new = function(c) log("Instance.new", c); return mock end },
    Vector3 = { new = function(...) log("Vector3.new", ...); return mock end, zero = mock },
    CFrame = { new = function(...) log("CFrame.new", ...); return mock end, identity = mock },
    Color3 = { new = function(...) log("Color3.new", ...); return mock end, fromRGB = function(...) log("Color3.fromRGB", ...); return mock end },
    UDim2 = { new = function(...) log("UDim2.new", ...); return mock end },
    Enum = mock,
    wait = function(t) log("wait", t); return t or 0 end,
    task = { spawn = function(f) log("task.spawn"); pcall(f) end, wait = function(t) log("task.wait", t); return t or 0 end },
    spawn = function(f) log("spawn"); pcall(f) end,
    delay = function(t, f) log("delay", t) end,
    tick = function() return os.clock() end,
    time = function() return os.clock() end,
}

setmetatable(env, {
    __index = function(t, k)
        log("GLOBAL_UNDEF", k)
        return mock
    end,
})

-- Read and execute the VM
local f = io.open("decompressed_vm.lua", "r")
if not f then
    print("Cannot open VM file")
    return
end
local code = f:read("*all")
f:close()

log("VM_SIZE", #code)
print("VM size: " .. #code)

local func, err = loadstring(code)
if not func then
    log("LOAD_ERROR", tostring(err))
    print("Load error: " .. tostring(err))
else
    log("VM_LOADED")
    print("VM loaded, setting environment...")

    if setfenv then
        setfenv(func, env)
    end

    print("Executing VM...")
    local ok, result = xpcall(func, function(e)
        log("ERROR", tostring(e))
        return e
    end)

    log("RESULT", ok, tostring(result))
    print("Execution result: " .. tostring(ok))

    if ok and type(result) == "table" then
        log("RESULT_IS_TABLE")
        for k, v in pairs(result) do
            log("TABLE_KEY", tostring(k), type(v))
        end
    end
end

-- Output traces
print("\n=== TRACE OUTPUT ===")
for i = 1, math.min(trace_count, 500) do
    print(traces[i])
end
print("=== END TRACE (" .. trace_count .. " total) ===")
