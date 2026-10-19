-- Preserve the installed game's original implementation, then extend it only
-- for maps explicitly registered in the converter's layer table.
require("T6.Zombie.Waw_GameMap_Base")
local map = CoD.GameMapZombie
local originalSwitch = map.SwitchToMapDirect
local originalDefault = map.DefaultAnim
local originalUp = map.MoveUpAnim
local originalDown = map.MoveDownAnim
local layered = false

-- Both menu states are baked at build time (Map = Large + Blit, Map Blur =
-- sharp Blit over Blur): a separately streamed full-canvas foreground showed
-- unfocused but vanished on focus. Only the zoom differs from stock maps.
map.SwitchToMapDirect = function(scale, blurred, duration)
    local material = UIExpression.TableLookup(nil, "zm/waw_menu_layers.csv", 0, CoD.Zombie.GetUIMapName(), 1)
    layered = material ~= nil and material ~= ""
    originalSwitch(scale, blurred, duration)
    if layered then
        -- Stock selection zoom is 2x. Authored canvases contain the full frame.
        map.gameMap:setScale(scale * 0.5)
    end
end

map.MoveUpAnim = function(duration)
    originalUp(duration)
    if layered then
        map.gameMap:setScale(1)
    end
end

map.MoveDownAnim = function(duration)
    originalDown(duration)
    if layered then
        map.gameMap:setScale(0.5)
    end
end

map.DefaultAnim = function(duration)
    layered = false
    originalDefault(duration)
end
