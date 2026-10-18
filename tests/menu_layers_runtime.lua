-- Run with a Lua 5.1+ interpreter (or lupa). Engine-independent state/placement test.
local function element()
    local e = {handlers = {}, children = {}}
    function e:setLeftRight(...) self.lr = {...} end
    function e:setTopBottom(...) self.tb = {...} end
    function e:setAlpha(a) self.alpha = a end
    function e:setScale(s) self.scale = s end
    function e:addElement(c) self.children[#self.children + 1] = c end
    function e:setImage(i) self.image = i end
    function e:registerEventHandler(k, v) self.handlers[k] = v end
    function e:setupUIStreamedImage(_) self.streaming = true end
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
LUI = {UIImage = {new = element}}
UIExpression = {TableLookup = function(_, table, col, key, value)
    assert(table == 'zm/waw_menu_layers.csv' and col == 0 and value == 1)
    if key == 'custom' then return 'custom_blit' end
    return ''
end}
RegisterMaterial = function(name) return name end
require = function(name) assert(name == 'T6.Zombie.Waw_GameMap_Base') end
dofile('src/waw2bo2/compat/menu_layers.lua')
local background = element()
stock.Init(background, 'default')
assert(#background.children == 1)
local front = background.children[1]
assert(front.lr[1] and front.lr[2] and front.lr[3] == 0 and front.lr[4] == 0)
assert(front.tb[1] and front.tb[2] and front.tb[3] == 0 and front.tb[4] == 0)
stock.SwitchToMapDirect(2, false, 500)
assert(background.scale == 1 and background.image == 'large' and front.image == 'custom_blit')
front.handlers.streamed_image_ready(front, {})
assert(front.alpha == 1)
-- Focus re-selects the same map; the engine does not raise the event again.
local ready = front.handlers.streamed_image_ready
front.handlers.streamed_image_ready = nil
stock.SwitchToMapDirect(2, true, 500)
assert(background.scale == 1 and background.image == 'blur' and front.alpha == 1)
stock.MoveDownAnim(100)
assert(background.scale == 0.5)
stock.MoveUpAnim(100)
assert(background.scale == 1)
local stale = ready
selected = 'stock'
stock.SwitchToMapDirect(2, false, 500)
assert(background.scale == 2 and front.alpha == 0)
stale(front, {})
assert(front.alpha == 0)
stock.MoveUpAnim(100)
assert(background.scale == 2)
stock.DefaultAnim(0)
assert(background.scale == 1 and front.alpha == 0)
selected = 'custom'
stock.SwitchToMapDirect(2, false, 500)
assert(background.scale == 1 and front.alpha == 1 and front.handlers.streamed_image_ready == nil)
print('Menu layer runtime transitions passed')
