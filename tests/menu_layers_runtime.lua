-- Run with a Lua 5.1+ interpreter (or lupa). Engine-independent state/zoom test.
local function element()
    local e = {}
    function e:setAlpha(a) self.alpha = a end
    function e:setScale(s) self.scale = s end
    function e:setImage(i) self.image = i end
    return e
end
local selected = 'custom'
local stock = {}
function stock.Init(e, _) stock.gameMap = e end
function stock.SwitchToMapDirect(s, blur, duration)
    stock.gameMap:setScale(s)
    stock.gameMap.image = blur and 'blur' or 'large'
end
function stock.MoveUpAnim(_) stock.gameMap:setScale(2) end
function stock.MoveDownAnim(_) stock.gameMap:setScale(1) end
function stock.DefaultAnim(_) stock.gameMap:setScale(1) end
CoD = {GameMapZombie = stock, Zombie = {GetUIMapName = function() return selected end}}
UIExpression = {TableLookup = function(_, table, col, key, value)
    assert(table == 'zm/waw_menu_layers.csv' and col == 0 and value == 1)
    if key == 'custom' then return 'custom_blit' end
    return ''
end}
require = function(name) assert(name == 'T6.Zombie.Waw_GameMap_Base') end
dofile('src/waw2bo2/compat/menu_layers.lua')
local background = element()
stock.Init(background, 'default')
-- Registered maps: the baked images keep the full frame at half the stock zoom.
stock.SwitchToMapDirect(2, false, 500)
assert(background.scale == 1 and background.image == 'large')
stock.SwitchToMapDirect(2, true, 500)
assert(background.scale == 1 and background.image == 'blur')
stock.MoveDownAnim(100)
assert(background.scale == 0.5)
stock.MoveUpAnim(100)
assert(background.scale == 1)
-- Stock maps keep the stock zoom.
selected = 'stock'
stock.SwitchToMapDirect(2, false, 500)
assert(background.scale == 2)
stock.MoveUpAnim(100)
assert(background.scale == 2)
selected = 'custom'
stock.SwitchToMapDirect(2, false, 500)
stock.DefaultAnim(0)
stock.MoveUpAnim(100)
assert(background.scale == 2)
print('Menu layer runtime transitions passed')
