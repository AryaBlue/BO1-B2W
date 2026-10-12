# DLC3 template script translation

The converter recursively extracts functions from the source map's
`maps/dlc3_code`, `maps/dlc3_teleporter`, and `maps/createfx/dlc3_fx` scripts.
This preserves the map's own template edits and brings in power switches,
electric traps, teleporter linking and movement, Pack-a-Punch doors, intro
HUD, bridge logic, and createFX initialization when the source calls them.

Template functions take precedence over similarly named compatibility APIs,
after explicit API renames. DLC3's argumentless `spawnFX()` invokes the map's
createFX callback and DLC3 exploder setup; it must not become a call to the
engine `spawnfx(fx, origin, ...)` wrapper.

Extracted functions contribute FX, model, model-precache, and HUD-material
dependencies. Raw stock animation helpers are classified as framework code
even when the map carries its own copy, so extracting a small helper does
not accidentally port the whole WaW AI framework.

Two initialization calls deliberately preserve BO2 ownership:

- `manage_zones` resolves to a no-op because the generated map main already
  starts BO2's zone manager. Initial zones written directly into
  `level.DLC3.initialZones` are included in zone-graph discovery.
- `_callbacksetup::SetupCallbacks` resolves to a no-op because BO2's Zombies
  gametype owns engine callbacks. The existing damage-prelude translation
  handles supported source damage overrides separately.

## Remaining engine behavior

This is broader script translation, not a guarantee of full gameplay fidelity.
Animation discovery now runs the same recursive function resolver used for
translation, including function pointers, framework state, actor appearance,
and the player loadout. Each function retains the `#using_animtree` active at
its definition. Original clips are staged as `waw_anim_<name>` and trees as
`waw2bo2_<tree>` so stock BO2 names cannot replace their contents.
`script_anims_init`, `anim_override_func`, and `factory_playanim` now translate
with their original animation references when those clips are available.
Missing clips remain explicit conversion-report entries. Extracting an AI
override does not establish full WaW AI animation playback: native BO2 actor
state machines still require their own animation bindings.

`settransported(seconds)` also remains an explicit reported stub. Inspection
of the mapped WaW executable at `0x5225C0` shows that it sends client command
41 with a duration in milliseconds (the multiplier at `0x8E4714` is 1000).
It does not move the player. The template's physical teleport uses separate
source operations, which are translated. Recreating the client transport
effect requires a verified T6 implementation; an unrelated blur or shellshock
would not preserve the original effect. Further inspection found T6's retained
transport renderer (`0x76A000`) and generic client filter APIs, including
`set_filter_pass_constant` (`0x7C7A30`). The source overlay uses animated atlas
frames, scene distortion, tint/bias constants, and a timed fade. The mapping
between generic-filter script parameters and renderer shader constants is not
yet verified, so this remaining client-effect gap is not marked fixed.

## Validation, 2026-10-12

- 468 unit tests pass, including method resolution after caller-parenthesis
  removal, template function precedence, recursive extraction, model/HUD
  staging, raw stock overrides, callback ownership, and initial zones.
- Native BO2 script compilation passes for Nuketown Remastered 1.2 (82
  scripts), Empty Walls (94), Abandoned School (73), Asylum v2 (97), and
  Alcatraz (110), using the current stock-script cache.
- Local evidence: `work/dlc3_20261012/tests.log`, `native_compile.log`, and
  `complete_regressions.json` in that directory.
- A complete McDonald's build with all 42 reachable source animations passed
  native linking and material audits. The subsequent headshot build compiles 88 scripts and preserves all 5,598
  authored hitboxes across 122 animated models with zero audit violations.
  Both material audits pass. The verified fastfiles are installed; one changed
  streaming-audio bank waits for the existing COD process to exit before copying.
  In-game gameplay remains unverified.
