-- Luraph VM Dynamic Tracer
-- This runs the VM with comprehensive logging to capture execution

local trace = {}
local trace_count = 0
local MAX_TRACES = 100000

local function log(...)
    if trace_count >= MAX_TRACES then return end
    trace_count = trace_count + 1
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
            parts[i] = "<table>"
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

local function save_trace()
    local f = io.open("/home/user/deobluraph/execution_trace.txt", "w")
    if f then
        for i, line in ipairs(trace) do
            f:write(line .. "\n")
        end
        f:close()
        print("Saved " .. trace_count .. " trace entries")
    end
end

-- Create comprehensive mock environment
local mock_instance = {}
local instance_mt = {
    __index = function(self, key)
        log("INSTANCE_GET", key)
        return mock_instance
    end,
    __newindex = function(self, key, value)
        log("INSTANCE_SET", key, value)
    end,
    __call = function(self, ...)
        log("INSTANCE_CALL", ...)
        return mock_instance
    end,
    __tostring = function() return "MockInstance" end
}
setmetatable(mock_instance, instance_mt)

-- Mock game services
local services = {}
local service_mt = {
    __index = function(self, key)
        log("SERVICE_GET", key)
        return mock_instance
    end,
}

local function mock_service(name)
    if not services[name] then
        services[name] = setmetatable({_name = name}, service_mt)
    end
    return services[name]
end

-- Mock game object
local mock_game = setmetatable({}, {
    __index = function(self, key)
        if key == "GetService" then
            return function(_, name)
                log("GetService", name)
                return mock_service(name)
            end
        end
        log("GAME_GET", key)
        return mock_instance
    end,
})

-- Create mock environment
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
        log("PCALL")
        return pcall(f, ...)
    end end
    if k == "xpcall" then return xpcall end
    if k == "error" then return function(msg) log("ERROR", msg) error(msg) end end
    if k == "assert" then return assert end
    if k == "setmetatable" then return setmetatable end
    if k == "getmetatable" then return getmetatable end
    if k == "rawget" then return rawget end
    if k == "rawset" then return rawset end
    if k == "rawequal" then return rawequal end
    if k == "setfenv" then return setfenv or function() end end
    if k == "getfenv" then return getfenv or function() return env end end
    if k == "loadstring" then
        return function(code, name)
            log("LOADSTRING", #code, name or "")
            return nil, "loadstring disabled"
        end
    end
    if k == "newproxy" then return function() return {} end end

    -- Standard libraries
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
        clear = function(t) for k in pairs(t) do t[k]=nil end end,
    } end
    if k == "math" then return math end
    if k == "coroutine" then return coroutine end
    if k == "bit32" then return bit32 end
    if k == "debug" then return nil end  -- Disabled
    if k == "os" then return nil end     -- Disabled
    if k == "io" then return nil end     -- Disabled

    -- Roblox globals
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
        }
    end
    if k == "CFrame" then
        return {
            new = function(...) log("CFrame.new", ...); return mock_instance end,
        }
    end
    if k == "Color3" then
        return {
            new = function(r,g,b) log("Color3.new", r,g,b); return {r or 0, g or 0, b or 0} end,
            fromRGB = function(r,g,b) log("Color3.fromRGB", r,g,b); return {r/255, g/255, b/255} end,
        }
    end
    if k == "UDim2" then
        return {
            new = function(...) log("UDim2.new", ...); return mock_instance end,
        }
    end
    if k == "Enum" then return mock_instance end
    if k == "wait" then return function(t) log("wait", t) end end
    if k == "spawn" then return function(f) log("spawn"); pcall(f) end end
    if k == "delay" then return function(t,f) log("delay", t) end end
    if k == "tick" then return function() return os.time() end end
    if k == "time" then return function() return os.time() end end
    if k == "typeof" then return function(v) return type(v) end end

    return mock_instance
end})

-- Read the VM code
local f = io.open("/home/user/deobluraph/decompressed_vm.lua", "r")
if not f then
    print("Cannot open VM file")
    return
end
local vm_code = f:read("*all")
f:close()

print("VM code size: " .. #vm_code)
log("VM_SIZE", #vm_code)

-- Load and run the VM
local vm_func, err = load(vm_code, "VM", "t", env)
if not vm_func then
    print("Load error: " .. tostring(err))
    log("LOAD_ERROR", err)
    save_trace()
    return
end

log("VM_LOADED")
print("VM loaded, executing...")

-- Execute with error handling
local ok, result = xpcall(vm_func, function(err)
    log("RUNTIME_ERROR", tostring(err))
    log("TRACEBACK", debug.traceback())
    return err
end)

log("VM_RESULT", ok, result)

if ok then
    print("Execution completed successfully")
else
    print("Execution failed: " .. tostring(result))
end

-- Save trace
save_trace()
print("Done!")
