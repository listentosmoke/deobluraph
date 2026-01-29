#!/usr/bin/env python3
"""
Run the Luraph VM in Luau by embedding the code directly.
Capture execution traces via stdout.
"""

import subprocess
import sys

def main():
    # Read the VM code
    with open('/home/user/deobluraph/decompressed_vm.lua', 'r') as f:
        vm_code = f.read()

    # Escape for embedding in Lua long string
    # Replace ]==] patterns to avoid breaking our long string
    vm_code_escaped = vm_code.replace(']=', ']=\0=')

    # Create runner script
    runner_script = '''
-- Luraph VM Runner for Luau
local trace = {}
local trace_count = 0

local function log(...)
    trace_count = trace_count + 1
    if trace_count <= 50000 then
        local args = {...}
        local parts = {}
        for i = 1, select("#", ...) do
            local v = args[i]
            if type(v) == "string" and #v > 100 then
                parts[i] = string.format("%%q...", v:sub(1,100))
            elseif type(v) == "string" then
                parts[i] = string.format("%%q", v)
            elseif type(v) == "table" then
                parts[i] = "<table:" .. tostring(v) .. ">"
            elseif type(v) == "function" then
                parts[i] = "<func>"
            else
                parts[i] = tostring(v)
            end
        end
        table.insert(trace, table.concat(parts, "\\t"))
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
        log("INST_SET", key, type(value))
    end,
    __call = function(self, ...)
        log("INST_CALL", ...)
        return mock_instance
    end,
    __tostring = function() return "MockInstance" end
}
setmetatable(mock_instance, mock_mt)

local services = {}
local mock_game = setmetatable({}, {
    __index = function(self, key)
        if key == "GetService" then
            return function(_, service_name)
                log("GetService", service_name)
                return mock_instance
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
    if k == "loadstring" then return function(code, name) log("LOADSTRING", #code); return nil, "disabled" end end
    if k == "newproxy" then return function() return {} end end

    if k == "string" then return string end
    if k == "table" then return {
        insert = table.insert, remove = table.remove, concat = table.concat,
        sort = table.sort, unpack = table.unpack or unpack,
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
    if k == "os" then return {time = os.time or function() return 0 end, clock = os.clock or function() return 0 end} end
    if k == "io" then return nil end

    if k == "game" then return mock_game end
    if k == "workspace" then return mock_instance end
    if k == "script" then return mock_instance end
    if k == "Instance" then return { new = function(class, parent) log("Instance.new", class); return mock_instance end } end
    if k == "Vector3" then return { new = function(x,y,z) log("Vector3.new", x,y,z); return {x or 0, y or 0, z or 0} end, zero = {0,0,0} } end
    if k == "CFrame" then return { new = function(...) log("CFrame.new"); return mock_instance end, identity = mock_instance } end
    if k == "Color3" then return { new = function(r,g,b) log("Color3.new",r,g,b); return {r or 0,g or 0,b or 0} end, fromRGB = function(r,g,b) log("Color3.fromRGB",r,g,b); return {(r or 0)/255,(g or 0)/255,(b or 0)/255} end } end
    if k == "UDim2" then return { new = function(...) log("UDim2.new"); return mock_instance end } end
    if k == "Enum" then return mock_instance end
    if k == "wait" then return function(t) log("wait", t); return t or 0 end end
    if k == "spawn" then return function(f) log("spawn"); pcall(f) end end
    if k == "delay" then return function(t,f) log("delay", t) end end
    if k == "tick" then return function() return 0 end end
    if k == "time" then return function() return 0 end end
    if k == "typeof" then return function(v) return type(v) end end
    if k == "task" then return { spawn = function(f) log("task.spawn"); pcall(f) end, wait = function(t) log("task.wait",t); return t or 0 end, delay = function(t,f) log("task.delay",t) end } end

    return mock_instance
end})

log("VM_SIZE", %d)

-- The VM code will be passed via stdin or as argument
-- For now, let's use loadstring from a heredoc

local vm_func, err = loadstring(%s)
if not vm_func then
    log("LOAD_ERROR", tostring(err))
    print("TRACE_START")
    for _, line in ipairs(trace) do print(line) end
    print("TRACE_END")
    print("Load error: " .. tostring(err))
    return
end

log("VM_LOADED")

-- Set environment
if setfenv then
    setfenv(vm_func, env)
end

local ok, result = xpcall(vm_func, function(e)
    log("RUNTIME_ERROR", tostring(e))
    return e
end)

log("VM_RESULT", ok, tostring(result))

-- Output trace
print("TRACE_START")
for _, line in ipairs(trace) do
    print(line)
end
print("TRACE_END")

if ok then
    print("Execution completed")
else
    print("Execution failed: " .. tostring(result))
end
''' % (len(vm_code), repr(vm_code))

    print(f"Runner script size: {len(runner_script)}")

    # Write runner script
    with open('/home/user/deobluraph/luau_runner_generated.lua', 'w') as f:
        f.write(runner_script)

    print("Running with Luau...")

    # Run with luau
    result = subprocess.run(
        ['luau', '/home/user/deobluraph/luau_runner_generated.lua'],
        capture_output=True,
        text=True,
        timeout=60
    )

    print(f"Return code: {result.returncode}")
    print(f"Stdout length: {len(result.stdout)}")
    print(f"Stderr length: {len(result.stderr)}")

    if result.stderr:
        print(f"Stderr:\n{result.stderr[:2000]}")

    # Extract trace
    stdout = result.stdout
    if "TRACE_START" in stdout and "TRACE_END" in stdout:
        start = stdout.index("TRACE_START") + len("TRACE_START\n")
        end = stdout.index("TRACE_END")
        trace_data = stdout[start:end]

        # Save trace
        with open('/home/user/deobluraph/luau_trace.txt', 'w') as f:
            f.write(trace_data)

        trace_lines = trace_data.strip().split('\n')
        print(f"Captured {len(trace_lines)} trace lines")
        print("\nFirst 50 trace lines:")
        for line in trace_lines[:50]:
            print(f"  {line}")
    else:
        print("No trace markers found")
        print(f"Output:\n{stdout[:5000]}")

if __name__ == '__main__':
    main()
