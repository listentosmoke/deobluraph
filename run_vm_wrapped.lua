-- Wrapped VM execution with safe string operations
-- Note: Can't patch string.pack directly in Luau, so we'll use environment modification

-- Tracing
local traces = {}
local trace_count = 0

local function log(...)
    trace_count = trace_count + 1
    if trace_count <= 10000 then
        local parts = {}
        for i = 1, select("#", ...) do
            local v = select(i, ...)
            if type(v) == "string" and #v > 80 then
                parts[i] = '"' .. v:sub(1,80):gsub("\n", "\\n") .. '..."'
            elseif type(v) == "string" then
                parts[i] = '"' .. v:gsub("\n", "\\n") .. '"'
            elseif type(v) == "table" then
                parts[i] = "<table>"
            elseif type(v) == "function" then
                parts[i] = "<func>"
            else
                parts[i] = tostring(v)
            end
        end
        traces[trace_count] = table.concat(parts, "\t")
    end
end

-- Mock environment
local mock = {}
setmetatable(mock, {
    __index = function(self, k) log("mock_idx", k); return mock end,
    __newindex = function(self, k, v) log("mock_set", k, type(v)) end,
    __call = function(self, ...) log("mock_call"); return mock end,
    __tostring = function() return "Mock" end,
    __add = function() return 0 end,
    __sub = function() return 0 end,
    __mul = function() return 0 end,
    __div = function() return 1 end,
    __eq = function() return false end,
    __lt = function() return false end,
    __le = function() return false end,
})

local game_mock = setmetatable({}, {
    __index = function(self, k)
        if k == "GetService" then
            return function(_, name) log("GetService", name); return mock end
        end
        log("game_idx", k)
        return mock
    end
})

-- Globals to expose
_G.game = game_mock
_G.workspace = mock
_G.script = mock
_G.Instance = { new = function(c) log("Instance.new", c); return mock end }
_G.Vector3 = { new = function(...) return mock end, zero = mock }
_G.CFrame = { new = function(...) return mock end, identity = mock }
_G.Color3 = { new = function(...) return mock end, fromRGB = function(...) return mock end }
_G.UDim2 = { new = function(...) return mock end }
_G.Enum = mock
_G.wait = function(t) log("wait", t); return t or 0 end
_G.task = {
    spawn = function(f) log("task.spawn"); pcall(f) end,
    wait = function(t) log("task.wait", t); return t or 0 end,
    delay = function(t, f) log("task.delay", t) end,
}
_G.spawn = function(f) log("spawn"); pcall(f) end
_G.delay = function(t, f) log("delay", t) end
_G.tick = function() return os.clock() end
_G.time = function() return os.clock() end
_G.typeof = function(v) return type(v) end

-- Wrap print to capture output
local original_print = print
_G.print = function(...)
    log("print", ...)
    original_print(...)
end

print("Starting VM execution...")

-- Load and run the fixed VM
local ok, result = xpcall(function()
    return dofile("decompressed_vm_fixed.lua")
end, function(err)
    log("ERROR", tostring(err))
    print("Error: " .. tostring(err))
    print(debug.traceback())
    return err
end)

print("Execution result: " .. tostring(ok))

if ok and type(result) == "table" then
    print("Result is a table with keys:")
    local count = 0
    for k, v in pairs(result) do
        count = count + 1
        print("  " .. tostring(k) .. " = " .. type(v))
        log("result_key", tostring(k), type(v))
        if count > 30 then
            print("  ... (more keys)")
            break
        end
    end
end

print("\n=== TRACES ===")
for i = 1, math.min(trace_count, 200) do
    print(traces[i])
end
print("Total traces: " .. trace_count)
