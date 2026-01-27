-- Luraph VM Decompiler Skeleton
-- Generated from opcode analysis

local opcodes = {
    [0x35] = 'MOVE',  -- 53
    [0x44] = 'FORPREP',  -- 68
    [0x9B] = 'JMP',  -- 155
    [0xBC] = 'SETTABLE',  -- 188
}

-- Decompile function
local function decompile(bytecode, constants)
    local output = {}
    local pc = 1
    
    while pc <= #bytecode do
        local instr = bytecode[pc]
        local op = instr & 0xFF  -- Extract opcode
        local A = (instr >> 8) & 0xFF
        local B = (instr >> 16) & 0xFF
        local C = (instr >> 24) & 0xFF
        
        local op_name = opcodes[op] or 'UNKNOWN'
        table.insert(output, string.format('%d: %s A=%d B=%d C=%d', pc, op_name, A, B, C))
        pc = pc + 1
    end
    
    return table.concat(output, '\n')
end

return { opcodes = opcodes, decompile = decompile }