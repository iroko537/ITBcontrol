-- ITBcontrol Lua Mod
-- Injected via user/missionData.lua
-- Dumps board state to state.json each turn, reads action.json to execute moves
--
-- How it works:
--   1. Monkey-patches Mission:UpdateMission() to dump state after each update
--   2. Reads action.json written by the Python agent
--   3. Executes the action via SkillEffect

local function get_dir()
    local d = GetWorkingDir()
    if d and d ~= "" then return d end
    return ""
end

local function STATE_FILE()  return get_dir() .. "itbcontrol_state.json" end
local function ACTION_FILE() return get_dir() .. "itbcontrol_action.json" end
local function LOG_FILE()    return get_dir() .. "itbcontrol.log" end

-- ── Helpers ────────────────────────────────────────────────────────────────

local function log(msg)
    local f = io.open(LOG_FILE(), "a")
    if f then f:write("[ITBcontrol] " .. tostring(msg) .. "\n"); f:close() end
end

local function write_file(path, content)
    local f = io.open(path, "w")
    if f then f:write(content); f:close(); return true end
    log("ERROR: cannot write " .. path)
    return false
end

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local s = f:read("*all"); f:close()
    return s
end

local function delete_file(path)
    os.remove(path)
end

-- ── Simple JSON serialiser (no dependencies) ──────────────────────────────

local function json_val(v)
    local t = type(v)
    if t == "nil"     then return "null"
    elseif t == "boolean" then return tostring(v)
    elseif t == "number"  then return tostring(v)
    elseif t == "string"  then
        v = v:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('\n', '\\n')
        return '"' .. v .. '"'
    elseif t == "table" then
        -- check if array
        local is_array = (#v > 0)
        if is_array then
            local parts = {}
            for _, item in ipairs(v) do parts[#parts+1] = json_val(item) end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            local parts = {}
            for k, item in pairs(v) do
                parts[#parts+1] = '"' .. tostring(k) .. '":' .. json_val(item)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    end
    return "null"
end

-- ── Board state extractor ─────────────────────────────────────────────────

local function pawn_to_table(pawn, point)
    if not pawn then return nil end
    return {
        id        = pawn:GetId(),
        type      = tostring(pawn),
        team      = pawn:GetTeam(),
        x         = point.x,
        y         = point.y,
        health    = pawn:IsAbility("GetHealth") and pawn:GetHealth() or -1,
        max_hp    = pawn:IsAbility("GetMaxHealth") and pawn:GetMaxHealth() or -1,
        move      = pawn:GetMoveSpeed(),
        is_dead   = pawn:IsDead() or false,
        is_flying = pawn:IsAbility("IsFlying") and pawn:IsFlying() or false,
        shields   = pawn:IsAbility("GetShields") and pawn:GetShields() or 0,
    }
end

local function dump_state()
    log("dump_state called")

    -- step 1: board size
    local size
    local ok, err = pcall(function() size = Board:GetSize() end)
    if not ok then log("ERROR GetSize: " .. tostring(err)); return end
    log("board size: " .. tostring(size.x) .. "x" .. tostring(size.y))

    -- step 2: build state table (safe getters)
    local turn = 0
    pcall(function() turn = Game:GetTurnCount() end)

    local state = {
        turn      = turn,
        board_w   = size.x,
        board_h   = size.y,
        tiles     = {},
        pawns     = {},
        buildings = {},
    }

    -- step 3: tiles
    local tok, terr = pcall(function()
        for x = 0, size.x - 1 do
            for y = 0, size.y - 1 do
                local p = Point(x, y)
                state.tiles[#state.tiles+1] = {
                    x = x, y = y,
                    terrain     = Board:GetTerrain(p),
                    is_fire     = Board:IsFire(p),
                    is_frozen   = Board:IsFrozen(p),
                    is_acid     = Board:IsAcid(p),
                    is_building = Board:IsBuilding(p),
                }
            end
        end
    end)
    if not tok then log("ERROR tiles: " .. tostring(terr)); return end
    log("tiles ok: " .. tostring(#state.tiles))

    -- step 4: pawns
    local pok, perr = pcall(function()
        local teams = {TEAM_PLAYER, TEAM_ENEMY, TEAM_MECH}
        for _, team in ipairs(teams) do
            local pawn_list = Board:GetPawns(team)
            if pawn_list then
                for i = 1, pawn_list:size() do
                    local pawn_id = pawn_list:index(i)
                    local pawn = Board:GetPawn(pawn_id)
                    if pawn then
                        local pt   = pawn:GetSpace()
                        local pd   = pawn_to_table(pawn, pt)
                        if pd then state.pawns[#state.pawns+1] = pd end
                    end
                end
            end
        end
    end)
    if not pok then log("ERROR pawns: " .. tostring(perr)); return end
    log("pawns ok: " .. tostring(#state.pawns))

    -- step 5: buildings
    pcall(function()
        local bldgs = Board:GetBuildings()
        if bldgs then
            for i = 1, bldgs:size() do
                local pt = bldgs:index(i)
                state.buildings[#state.buildings+1] = {
                    x = pt.x, y = pt.y,
                    damaged = Board:IsDamaged(pt),
                }
            end
        end
    end)

    -- step 6: write
    local wok, werr = pcall(function() write_file(STATE_FILE(), json_val(state)) end)
    if wok then
        log("State dumped OK, turn=" .. tostring(state.turn))
    else
        log("ERROR write_file: " .. tostring(werr))
    end
end

-- ── Action executor ────────────────────────────────────────────────────────
-- Action JSON format:
--   {"type": "move",   "pawn_id": 1, "from": [x,y], "to": [x,y]}
--   {"type": "attack", "pawn_id": 1, "skill": 0,    "target": [x,y]}
--   {"type": "end_turn"}
--   {"type": "wait"}

local function execute_action()
    local raw = read_file(ACTION_FILE())
    if not raw or raw == "" then return end

    -- very simple JSON key extraction
    local function get_str(key)
        return raw:match('"' .. key .. '":%s*"([^"]+)"')
    end
    local function get_num(key)
        local v = raw:match('"' .. key .. '":%s*(%-?%d+)')
        return v and tonumber(v) or nil
    end
    local function get_arr(key)
        local s = raw:match('"' .. key .. '":%s*%[([^%]]+)%]')
        if not s then return nil end
        local a, b = s:match('(%d+),%s*(%d+)')
        return a and {tonumber(a), tonumber(b)} or nil
    end

    local action_type = get_str("type")
    log("Executing action: " .. tostring(action_type))

    if action_type == "end_turn" then
        -- Signal end turn — the UI button press is handled by Python xdotool
        -- We just log it here
        log("End turn signalled")

    elseif action_type == "move" then
        local from_arr = get_arr("from")
        local to_arr   = get_arr("to")
        if from_arr and to_arr then
            local from_p = Point(from_arr[1], from_arr[2])
            local to_p   = Point(to_arr[1],   to_arr[2])
            local pawn   = Board:GetPawn(from_p)
            if pawn and not Board:IsBlocked(to_p, pawn:GetPathProf()) then
                local path = Board:GetPath(from_p, to_p, pawn:GetPathProf())
                local effect = SkillEffect()
                effect:AddCharge(path, NO_DELAY)
                Board:AddEffect(effect)
                log("Move executed: " .. from_arr[1]..","..from_arr[2] .. " -> " .. to_arr[1]..","..to_arr[2])
            else
                log("Move blocked or no pawn at from location")
            end
        end

    elseif action_type == "wait" then
        log("Wait action - no move")
    end

    delete_file(ACTION_FILE())
end

-- ── Hook via BaseStart: wrap the instance's UpdateMission at mission start ──
-- Each mission subclass overrides UpdateMission directly, so patching
-- Mission.UpdateMission does nothing. Instead we intercept BaseStart
-- (which IS the shared base) and wrap self's UpdateMission per-instance.

local _orig_base_start = Mission.BaseStart
function Mission:BaseStart(...)
    if _orig_base_start then _orig_base_start(self, ...) end

    -- Wrap this instance's UpdateMission
    local _orig = self.UpdateMission
    self.UpdateMission = function(s, ...)
        if _orig then _orig(s, ...) end
        pcall(dump_state)
        pcall(execute_action)
    end

    delete_file(ACTION_FILE())
    log("ITBcontrol hooked into mission: " .. tostring(self))
    pcall(dump_state)
end

log("ITBcontrol mod parsed successfully")
