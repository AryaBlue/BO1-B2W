-- Run with a Lua 5.1+ interpreter (or lupa). Engine-independent layout test.
local selected = 'zm_custom'
local stock = {MapImageBottom = -57, MapImageHeight = 136}
function stock.ZombieUpdate(self, event)
    self.updated = event
    self.mapImage:setTopBottom(false, true, -193, -57)
end
CoD = {MapInfoImage = stock, Zombie = {GetUIMapName = function() return selected end}}
UIExpression = {TableLookup = function(_, table, col, key, value)
    assert(table == 'zm/waw_menu_preview.csv' and col == 0 and value == 0)
    if key == 'zm_custom' then return 'zm_custom' end
    return ''
end}
require = function(name) assert(name == 'T6.Waw_MapInfoImage_Base') end
dofile('src/waw2bo2/compat/menu_preview.lua')
local image = {}
function image:setTopBottom(a, b, top, bottom) self.tb = {a, b, top, bottom} end
local widget = {mapImage = image}
-- Converted maps: the picture extends under the 46-unit name strip.
CoD.MapInfoImage.ZombieUpdate(widget, 'refresh')
assert(widget.updated == 'refresh')
assert(image.tb[3] == -193 and image.tb[4] == -11)
-- Stock maps keep the stock layout.
selected = 'zm_transit'
CoD.MapInfoImage.ZombieUpdate(widget, 'refresh')
assert(image.tb[3] == -193 and image.tb[4] == -57)
-- No image yet: nothing to lay out.
CoD.MapInfoImage.ZombieUpdate({}, 'refresh')
print('Menu preview runtime layout passed')
