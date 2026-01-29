-- Run the converted VM with comprehensive instrumentation
-- This captures all global accesses, function calls, and string operations

local trace = {}
local trace_count = 0
local MAX_TRACES = 200000

local function log(...)
    trace_count = trace_count + 1
    if trace_count <= MAX_TRACES then
        local args = {...}
        local parts = {}
        for i = 1, select("#", ...) do
            local v = args[i]
            local t = type(v)
            if t == "string" then
                if #v > 100 then
                    parts[i] = string.format("%q...", v:sub(1, 100))
                else
                    parts[i] = string.format("%q", v)
                end
            elseif t == "table" then
                -- Try to show some table content
                local count = 0
                local items = {}
                for k, val in pairs(v) do
                    count = count + 1
                    if count > 5 then
                        items[#items+1] = "..."
                        break
                    end
                    local ks = type(k) == "number" and tostring(k) or string.format("%q", tostring(k))
                    local vs
                    if type(val) == "string" and #val < 30 then
                        vs = string.format("%q", val)
                    elseif type(val) == "number" then
                        vs = tostring(val)
                    else
                        vs = "<" .. type(val) .. ">"
                    end
                    items[#items+1] = "[" .. ks .. "]=" .. vs
                end
                parts[i] = "{" .. table.concat(items, ",") .. "}"
            elseif t == "function" then
                parts[i] = "<func>"
            elseif t == "userdata" then
                parts[i] = "<userdata>"
            else
                parts[i] = tostring(v)
            end
        end
        trace[trace_count] = table.concat(parts, "\t")
    end
end

local function save_trace()
    local f = io.open("/home/user/deobluraph/vm_execution_trace.txt", "w")
    if f then
        for i, line in ipairs(trace) do
            f:write(line .. "\n")
        end
        f:close()
        print("Saved " .. trace_count .. " trace entries")
    end
end

-- Create mock Roblox objects
local mock_instance = {}
local mock_mt = {
    __index = function(self, key)
        log("INST_INDEX", key)
        return mock_instance
    end,
    __newindex = function(self, key, value)
        log("INST_NEWINDEX", key, value)
    end,
    __call = function(self, ...)
        log("INST_CALL", ...)
        return mock_instance
    end,
    __tostring = function() return "MockInstance" end,
    __concat = function(a, b) return tostring(a) .. tostring(b) end,
    __eq = function(a, b) return false end,
    __lt = function(a, b) return false end,
    __le = function(a, b) return false end,
    __add = function(a, b) return 0 end,
    __sub = function(a, b) return 0 end,
    __mul = function(a, b) return 0 end,
    __div = function(a, b) return 1 end,
    __unm = function(a) return 0 end,
}
setmetatable(mock_instance, mock_mt)

-- Create services table
local services = {}
local function create_service(name)
    log("CREATE_SERVICE", name)
    local svc = setmetatable({_name = name}, {
        __index = function(self, key)
            log("SVC_INDEX", name, key)
            return mock_instance
        end,
    })
    return svc
end

local mock_game = setmetatable({}, {
    __index = function(self, key)
        if key == "GetService" then
            return function(_, service_name)
                log("GetService", service_name)
                if not services[service_name] then
                    services[service_name] = create_service(service_name)
                end
                return services[service_name]
            end
        end
        log("GAME_INDEX", key)
        return mock_instance
    end,
})

-- Build the environment
local env = {}

-- Add standard Lua functions
env.print = function(...)
    log("PRINT", ...)
end
env.type = type
env.tostring = tostring
env.tonumber = tonumber
env.pairs = pairs
env.ipairs = ipairs
env.next = next
env.select = select
env.unpack = unpack or table.unpack
env.pcall = function(f, ...)
    log("PCALL_START")
    local results = {pcall(f, ...)}
    log("PCALL_RESULT", results[1])
    return table.unpack(results)
end
env.xpcall = xpcall
env.error = function(msg, level)
    log("ERROR", msg)
    error(msg, level)
end
env.assert = assert
env.setmetatable = setmetatable
env.getmetatable = getmetatable
env.rawget = rawget
env.rawset = rawset
env.rawequal = rawequal
env.setfenv = setfenv or function() end
env.getfenv = getfenv or function() return env end
env.loadstring = function(code, name)
    log("LOADSTRING", #code, name or "<unnamed>")
    return nil, "loadstring disabled"
end
env.newproxy = function(mt)
    return setmetatable({}, mt and {} or nil)
end

-- Libraries
env.string = string
env.table = {
    insert = table.insert,
    remove = table.remove,
    concat = table.concat,
    sort = table.sort,
    unpack = table.unpack or unpack,
    create = function(n, v)
        local t = {}
        for i = 1, n do t[i] = v end
        return t
    end,
    move = table.move or function(a1, f, e, t, a2)
        a2 = a2 or a1
        for i = f, e do
            a2[t + i - f] = a1[i]
        end
        return a2
    end,
    find = function(t, v, init)
        for i = init or 1, #t do
            if t[i] == v then return i end
        end
        return nil
    end,
    clear = function(t)
        for k in pairs(t) do t[k] = nil end
    end,
    pack = table.pack or function(...)
        return {n = select("#", ...), ...}
    end,
}
env.math = math
env.coroutine = coroutine
env.bit32 = bit32
env.debug = nil
env.os = {
    time = os.time,
    clock = os.clock,
    date = os.date,
    difftime = os.difftime,
}
env.io = nil

-- Roblox globals
env.game = mock_game
env.workspace = mock_instance
env.script = mock_instance
env.Instance = {
    new = function(class, parent)
        log("Instance.new", class)
        return mock_instance
    end
}
env.Vector3 = {
    new = function(x, y, z)
        log("Vector3.new", x, y, z)
        return setmetatable({X = x or 0, Y = y or 0, Z = z or 0}, {
            __tostring = function(self)
                return string.format("Vector3(%s,%s,%s)", self.X, self.Y, self.Z)
            end,
            __add = function(a, b) return env.Vector3.new(0, 0, 0) end,
            __sub = function(a, b) return env.Vector3.new(0, 0, 0) end,
            __mul = function(a, b) return env.Vector3.new(0, 0, 0) end,
        })
    end,
    zero = {X = 0, Y = 0, Z = 0},
}
env.CFrame = {
    new = function(...)
        log("CFrame.new", ...)
        return mock_instance
    end,
    identity = mock_instance,
}
env.Color3 = {
    new = function(r, g, b)
        log("Color3.new", r, g, b)
        return {R = r or 0, G = g or 0, B = b or 0}
    end,
    fromRGB = function(r, g, b)
        log("Color3.fromRGB", r, g, b)
        return {R = (r or 0)/255, G = (g or 0)/255, B = (b or 0)/255}
    end,
}
env.UDim2 = {
    new = function(...)
        log("UDim2.new", ...)
        return mock_instance
    end,
}
env.Enum = mock_instance
env.wait = function(t)
    log("wait", t)
    return t or 0
end
env.spawn = function(f)
    log("spawn")
    pcall(f)
end
env.delay = function(t, f)
    log("delay", t)
end
env.tick = function()
    return os.clock()
end
env.time = function()
    return os.clock()
end
env.typeof = function(v)
    return type(v)
end
env.task = {
    spawn = function(f)
        log("task.spawn")
        pcall(f)
    end,
    wait = function(t)
        log("task.wait", t)
        return t or 0
    end,
    delay = function(t, f)
        log("task.delay", t)
    end,
}

-- Set metatable to catch undefined globals
setmetatable(env, {
    __index = function(t, k)
        log("GLOBAL_UNDEFINED", k)
        return mock_instance
    end,
    __newindex = function(t, k, v)
        log("GLOBAL_SET", k, v)
        rawset(t, k, v)
    end,
})

-- Load the converted VM
log("LOADING_VM")
print("Loading VM...")

local vm_func, err = loadfile("/home/user/deobluraph/vm_standard_lua.lua", "t", env)
if not vm_func then
    log("LOAD_ERROR", err)
    print("Load error: " .. tostring(err))
    save_trace()
    return
end

log("VM_LOADED")
print("VM loaded, executing...")

-- Execute
local ok, result = xpcall(vm_func, function(e)
    log("RUNTIME_ERROR", tostring(e))
    log("TRACEBACK", debug.traceback())
    return e
end)

log("EXECUTION_RESULT", ok, result)

if ok then
    print("Execution completed successfully")
    if type(result) == "table" then
        log("RESULT_TABLE_KEYS")
        for k, v in pairs(result) do
            log("RESULT_KEY", k, type(v))
        end
    end
else
    print("Execution failed: " .. tostring(result))
end

-- Save trace
save_trace()
print("Done!")
