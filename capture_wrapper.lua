-- Capture Wrapper - prepend this to the obfuscated script
-- Run with: cat capture_wrapper.lua script.lua | /tmp/luau-src/luau -

print("=== BYTECODE CAPTURE ACTIVE ===")

local func_count = 0
local max_funcs = 50
local output = {}

-- We need to intercept the VM after it's created
-- The script returns a table that is immediately called with :wS()
-- So we need to wrap the return value

local original_return = nil

-- Hook into table creation by wrapping the script's return
-- The script structure is: return({...}):wS()(...)

-- Since we can't easily intercept that, let's try a different approach:
-- Use debug.info to trace execution

local call_depth = 0
local trace_enabled = true

-- Store original functions we want to hook
local hooks_installed = false

-- Function to install hooks on a VM table
local function install_vm_hooks(vm)
    if hooks_installed then return end
    hooks_installed = true

    print("[HOOKS] Installing VM hooks...")

    -- Hook E8 (interpreter factory)
    local orig_E8 = vm.E8
    if orig_E8 then
        vm.E8 = function(z, V, B, L)
            print("[E8] Interpreter factory called")
            orig_E8(z, V, B, L)

            -- V[40] should now have the interpreter
            if type(V) == "table" and type(V[40]) == "function" then
                print("[E8] Found interpreter at V[40]")
                local orig_interp = V[40]

                V[40] = function(W, y, I)
                    func_count += 1
                    if func_count <= max_funcs then
                        print("\n--- Function " .. func_count .. " ---")

                        if type(W) == "table" then
                            -- Show structure
                            for i = 1, 12 do
                                local v = W[i]
                                if v ~= nil then
                                    if type(v) == "table" then
                                        local cnt = 0
                                        for _ in pairs(v) do cnt += 1 end
                                        print(string.format("W[%d]: table[%d]", i, cnt))
                                    else
                                        print(string.format("W[%d]: %s", i, type(v)))
                                    end
                                end
                            end

                            -- Dump instructions (W[10])
                            if type(W[10]) == "table" then
                                local instrs = W[10]
                                local cnt = 0
                                for _ in pairs(instrs) do cnt += 1 end
                                print("Instructions: " .. cnt)

                                -- Store for output
                                local instr_list = {}
                                for j = 1, math.min(cnt, 500) do
                                    if instrs[j] ~= nil then
                                        table.insert(instr_list, instrs[j])
                                    end
                                end
                                table.insert(output, {
                                    func_id = func_count,
                                    instructions = instr_list
                                })

                                -- Print first 20
                                print("First 20 instructions:")
                                for j = 1, math.min(20, #instr_list) do
                                    print(string.format("  [%d] = %d", j, instr_list[j]))
                                end
                            end

                            -- Dump strings (W[11])
                            if type(W[11]) == "table" then
                                local strs = W[11]
                                local cnt = 0
                                for _ in pairs(strs) do cnt += 1 end
                                print("Strings: " .. cnt)

                                for j = 1, math.min(10, cnt) do
                                    if strs[j] ~= nil then
                                        local s = tostring(strs[j])
                                        if #s > 50 then s = string.sub(s, 1, 50) .. "..." end
                                        s = string.gsub(s, "\n", "\\n")
                                        print(string.format('  [%d] = "%s"', j, s))
                                    end
                                end
                            end
                        end
                    elseif func_count == max_funcs + 1 then
                        print("\n[LIMIT] Max functions reached")
                    end

                    return orig_interp(W, y, I)
                end
                V[0x28] = V[40]
            end
        end
        print("[HOOKS] E8 hooked")
    end
end

-- The trick: wrap the return value
-- We redefine how the script's returned table behaves

-- Create a proxy that intercepts method calls
local function create_proxy(target)
    return setmetatable({}, {
        __index = function(_, key)
            local val = target[key]

            -- Install hooks when we first access the VM
            if not hooks_installed and type(target) == "table" then
                if target.E8 or target.wS then
                    install_vm_hooks(target)
                end
            end

            if type(val) == "function" then
                return function(self, ...)
                    print("[CALL] " .. tostring(key) .. "()")
                    return val(target, ...)
                end
            end
            return val
        end,
        __call = function(_, ...)
            print("[CALL] table called")
            if type(target) == "function" then
                return target(...)
            end
        end
    })
end

-- Now we need the script to be loaded after this wrapper
-- The simplest way: this file should be concatenated with script.lua
-- and run as one file

print("[INIT] Hooks ready, loading main script...")
print("")

-- ============================================
-- MAIN SCRIPT FOLLOWS (concatenate script.lua below this line)
-- ============================================
