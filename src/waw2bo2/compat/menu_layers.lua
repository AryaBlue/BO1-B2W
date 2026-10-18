-- Preserve the installed game's original implementation, then extend it only
-- for maps explicitly registered in the converter's layer table.
require("T6.Zombie.Waw_GameMap_Base")
local map = CoD.GameMapZombie
local originalInit = map.Init
local originalSwitch = map.SwitchToMapDirect
local originalDefault = map.DefaultAnim
local originalUp = map.MoveUpAnim
local originalDown = map.MoveDownAnim
local foreground = nil
local currentMaterial = nil

map.Init = function(element, material)
    originalInit(element, material)
    currentMaterial = nil
    foreground = LUI.UIImage.new()
    foreground:setLeftRight(true, true, 0, 0)
    foreground:setTopBottom(true, true, 0, 0)
    foreground:setAlpha(0)
    element:addElement(foreground)
end

map.SwitchToMapDirect = function(scale, blurred, duration)
    local name = CoD.Zombie.GetUIMapName()
    local material = UIExpression.TableLookup(nil, "zm/waw_menu_layers.csv", 0, name, 1)
    currentMaterial = nil
    foreground:setAlpha(0)
    if material ~= nil and material ~= "" then
        currentMaterial = material
        foreground:setImage(RegisterMaterial(material))
        foreground:registerEventHandler("streamed_image_ready", function(element, event)
            if currentMaterial == material then
                element:setAlpha(1)
            end
        end)
        foreground:setupUIStreamedImage(0)
    end
    originalSwitch(scale, blurred, duration)
    if currentMaterial ~= nil then
        -- Stock selection zoom is 2x. Authored canvases contain the full frame.
        map.gameMap:setScale(scale * 0.5)
    end
end

map.MoveUpAnim = function(duration)
    originalUp(duration)
    if currentMaterial ~= nil then
        map.gameMap:setScale(1)
    end
end

map.MoveDownAnim = function(duration)
    originalDown(duration)
    if currentMaterial ~= nil then
        map.gameMap:setScale(0.5)
    end
end

map.DefaultAnim = function(duration)
    currentMaterial = nil
    if foreground ~= nil then
        foreground:setAlpha(0)
    end
    originalDefault(duration)
end
