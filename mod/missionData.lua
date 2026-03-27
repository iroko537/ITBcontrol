-- ITBcontrol entry point
-- This file is loaded by the game via scripts/scripts.lua: "user/missionData.lua"
-- Place (or symlink) this file at:
--   /home/iroko/Games/Heroic/IntoTheBreach/user/missionData.lua

local ok, err = pcall(function()
    local dir = GetWorkingDir()
    dofile(dir .. "user/itbcontrol.lua")
end)

if not ok then
    local f = io.open(GetWorkingDir() .. "itbcontrol_error.log", "a")
    if f then
        f:write("ITBcontrol load error: " .. tostring(err) .. "\n")
        f:close()
    end
end
