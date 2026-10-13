# Map texture priority

WaW maps can package skins in `images/*.iwi` inside their own IWD while
referencing stock-named models and materials. If the map's zone dump has no
pixels for that image, recovering a stock zone first must not hide the map's
packaged texture.

The shared image resolver uses this order:

1. The map's supplied compiled-zone image pixels.
2. Images in the map's IWD directories.
3. Recovered stock-zone image pixels.
4. Stock-game IWD images when no zone pixels are available.

The build passes the map image roots and mod IWD directories explicitly.
The stock script/image cache and the stock game's `main` IWD directory are
excluded from those preferred sources by their supplied paths. There are no
map names, image names, or cache-folder-name heuristics in the rule.

World, actor, effect and weapon image staging share this priority. Recovered
images record their archive and entry in the stage report. A map override
that exists but cannot be decoded is reported rather than silently replaced
with stock pixels. Recovery is fresh for each build; old decoded DDS files
do not establish a source.

Cheese Cube Unlimited exposes this with its Pack-a-Punch colour textures and
honorguard zombie body textures: the prior build chose stock factory/asylum
recovery dumps instead of those images in the map's own IWD. The source
models, materials and zombie character selection need no map-specific edits.

Regression coverage checks actual output pixels in world and weapon staging,
map-zone precedence, stock-IWD exclusion, changed archive contents between
builds, and explicit failure for an undecodable map override.
