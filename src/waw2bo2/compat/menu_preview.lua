-- Preserve the installed game's original implementation, then extend it only
-- for maps explicitly registered in the converter's preview table.
require("T6.Waw_MapInfoImage_Base")
local info = CoD.MapInfoImage
local originalZombieUpdate = info.ZombieUpdate
-- Stock ZM leaves the 46-unit strip under the picture empty (the frame's dark
-- gradient behind the map name text). Converted maps fill the whole frame.
local TextBarHeight = 46

-- Read by the constructor (element.update = CoD.MapInfoImage.ZombieUpdate), so
-- replacing the field here covers every lobby map preview.
info.ZombieUpdate = function(self, ...)
    originalZombieUpdate(self, ...)
    if self.mapImage == nil then
        return
    end
    local name = CoD.Zombie.GetUIMapName()
    local registered = UIExpression.TableLookup(nil, "zm/waw_menu_preview.csv", 0, name, 0)
    local bottom = info.MapImageBottom
    if registered ~= nil and registered ~= "" then
        bottom = bottom + TextBarHeight
    end
    self.mapImage:setTopBottom(false, true, info.MapImageBottom - info.MapImageHeight, bottom)
end
