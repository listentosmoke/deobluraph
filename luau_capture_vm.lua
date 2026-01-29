-- Run with Luau to capture VM execution data
-- Creates hooks to capture the deserialized bytecode

local trace = {}
local trace_count = 0

local function log(...)
    trace_count = trace_count + 1
    if trace_count <= 100000 then
        local args = {...}
        local parts = {}
        for i = 1, select("#", ...) do
            local v = args[i]
            if type(v) == "string" and #v > 200 then
                parts[i] = string.format("%q...", v:sub(1,200))
            elseif type(v) == "string" then
                parts[i] = string.format("%q", v)
            elseif type(v) == "table" then
                -- Try to dump table contents
                local items = {}
                local count = 0
                for k, val in pairs(v) do
                    count = count + 1
                    if count > 20 then
                        table.insert(items, "...")
                        break
                    end
                    local key_str = tostring(k)
                    local val_str
                    if type(val) == "number" then
                        val_str = tostring(val)
                    elseif type(val) == "string" and #val < 50 then
                        val_str = string.format("%q", val)
                    else
                        val_str = "<" .. type(val) .. ">"
                    end
                    table.insert(items, string.format("[%s]=%s", key_str, val_str))
                end
                parts[i] = "{" .. table.concat(items, ",") .. "}"
            elseif type(v) == "function" then
                parts[i] = "<function>"
            else
                parts[i] = tostring(v)
            end
        end
        trace[trace_count] = table.concat(parts, "\t")
    end
end

-- Mock Roblox environment
local mock_instance = {}
local mock_mt = {
    __index = function(self, key)
        log("INST_GET", key)
        return mock_instance
    end,
    __newindex = function(self, key, value)
        log("INST_SET", key, type(value) == "table" and "<table>" or tostring(value))
    end,
    __call = function(self, ...)
        log("INST_CALL", ...)
        return mock_instance
    end,
    __tostring = function() return "MockInstance" end
}
setmetatable(mock_instance, mock_mt)

local function create_service(name)
    local svc = setmetatable({_name = name}, {
        __index = function(self, key)
            log("SVC_GET", name, key)
            return mock_instance
        end,
    })
    return svc
end

local services = {}
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
        log("GAME_GET", key)
        return mock_instance
    end,
})

-- Build environment
local env = {}
setmetatable(env, {__index = function(t, k)
    log("GLOBAL_READ", k)

    -- Standard Lua
    if k == "print" then return function(...) log("PRINT", ...) end end
    if k == "type" then return type end
    if k == "tostring" then return tostring end
    if k == "tonumber" then return tonumber end
    if k == "pairs" then return pairs end
    if k == "ipairs" then return ipairs end
    if k == "next" then return next end
    if k == "select" then return select end
    if k == "unpack" then return unpack or table.unpack end
    if k == "pcall" then return function(f, ...)
        log("PCALL_START")
        local results = table.pack(pcall(f, ...))
        log("PCALL_END", results[1])
        return table.unpack(results)
    end end
    if k == "xpcall" then return xpcall end
    if k == "error" then return function(msg) log("ERROR", msg); error(msg) end end
    if k == "assert" then return assert end
    if k == "setmetatable" then return setmetatable end
    if k == "getmetatable" then return getmetatable end
    if k == "rawget" then return rawget end
    if k == "rawset" then return rawset end
    if k == "rawequal" then return rawequal end
    if k == "setfenv" then return function() end end
    if k == "getfenv" then return function() return env end end
    if k == "loadstring" then
        return function(code, name)
            log("LOADSTRING", #code, name or "")
            return nil, "disabled"
        end
    end
    if k == "newproxy" then return function() return {} end end

    -- Libraries
    if k == "string" then return string end
    if k == "table" then return {
        insert = table.insert,
        remove = table.remove,
        concat = table.concat,
        sort = table.sort,
        unpack = table.unpack or unpack,
        create = function(n, v) local t = {}; for i=1,n do t[i]=v end; return t end,
        move = table.move or function(a1,f,e,t,a2) a2=a2 or a1; for i=f,e do a2[t+i-f]=a1[i] end; return a2 end,
        find = function(t,v,i) for j=i or 1,#t do if t[j]==v then return j end end end,
        clear = function(t) for key in pairs(t) do t[key]=nil end end,
        pack = table.pack or function(...) return {n=select("#",...), ...} end,
    } end
    if k == "math" then return math end
    if k == "coroutine" then return coroutine end
    if k == "bit32" then return bit32 end
    if k == "debug" then return nil end
    if k == "os" then return {time = os.time, clock = os.clock, difftime = os.difftime, date = os.date} end
    if k == "io" then return nil end

    -- Roblox
    if k == "game" then return mock_game end
    if k == "workspace" then return mock_instance end
    if k == "script" then return mock_instance end
    if k == "Instance" then
        return {
            new = function(class, parent)
                log("Instance.new", class)
                return mock_instance
            end
        }
    end
    if k == "Vector3" then
        return {
            new = function(x,y,z) log("Vector3.new", x,y,z); return {x or 0, y or 0, z or 0} end,
            zero = {0, 0, 0},
        }
    end
    if k == "CFrame" then
        return {
            new = function(...) log("CFrame.new", ...); return mock_instance end,
            identity = mock_instance,
        }
    end
    if k == "Color3" then
        return {
            new = function(r,g,b) log("Color3.new", r,g,b); return {r or 0, g or 0, b or 0} end,
            fromRGB = function(r,g,b) log("Color3.fromRGB", r,g,b); return {(r or 0)/255, (g or 0)/255, (b or 0)/255} end,
        }
    end
    if k == "UDim2" then
        return {
            new = function(...) log("UDim2.new", ...); return mock_instance end,
        }
    end
    if k == "Enum" then return mock_instance end
    if k == "wait" then return function(t) log("wait", t); return t or 0 end end
    if k == "spawn" then return function(f) log("spawn"); pcall(f) end end
    if k == "delay" then return function(t,f) log("delay", t) end end
    if k == "tick" then return function() return os.clock() end end
    if k == "time" then return function() return os.clock() end end
    if k == "typeof" then return function(v) return type(v) end end
    if k == "task" then
        return {
            spawn = function(f) log("task.spawn"); pcall(f) end,
            wait = function(t) log("task.wait", t); return t or 0 end,
            delay = function(t, f) log("task.delay", t) end,
        }
    end

    return mock_instance
end})

-- Load the VM code
local f = io.open("/home/user/deobluraph/decompressed_vm.lua", "r")
if not f then
    print("Cannot open VM file")
    return
end
local vm_code = f:read("*all")
f:close()

print("VM code size: " .. #vm_code)
log("VM_SIZE", #vm_code)

-- Execute VM
local vm_func, err = load(vm_code, "VM", "t", env)
if not vm_func then
    print("Load error: " .. tostring(err))
    log("LOAD_ERROR", tostring(err))
else
    log("VM_LOADED")
    print("VM loaded, executing...")

    local ok, result = xpcall(vm_func, function(e)
        log("RUNTIME_ERROR", tostring(e))
        log("TRACEBACK", debug.traceback())
        return e
    end)

    log("VM_RESULT", ok, result)

    if ok then
        print("Execution completed")
    else
        print("Execution failed: " .. tostring(result))
    end
end

-- Save trace
local outf = io.open("/home/user/deobluraph/luau_trace.txt", "w")
if outf then
    for i, line in ipairs(trace) do
        outf:write(line .. "\n")
    end
    outf:close()
    print("Saved " .. trace_count .. " trace entries to luau_trace.txt")
end
