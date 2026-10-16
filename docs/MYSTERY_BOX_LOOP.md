# Mystery box regression, 2026-10-15

The installed game's Plutonium console reports
`WAW2BO2 UNSUPPORTED GSC maps\mp\waw\_waw2bo2_compat::waw_zombie_weapon_keys`
immediately before repeated `potential infinite loop in script` warnings.
The staged `_waw2bo2_core.gsc` confirms that the box chooser calls a returning
stub instead of the weapon-list helper. That stub supplies no array to the
chooser's `keys.size` loop.

The weapon-list lowering emitted a complete qualified target call in a token
still classified as a source identifier. Reference resolution subsequently
treated the entire qualified text as an unknown source builtin and stubbed it.
The lowering also ran only for whole scripts, missing extracted framework
functions such as the stock box chooser.

The fix marks the generated call as target code and runs this lowering in the
shared reference-resolution path. Both map scripts and extracted framework
functions now call the compatibility helper. The branch starts at main and
includes the existing box FX/weapon-filter change from `6246166`, which was
previously only on the gameplay branch, to retain the requested glow and lights.

Validation:

- All 615 unit tests pass, including reference-resolution regressions for both
  ordinary scripts and extracted framework functions.
- Fresh retail Shi No Numa and Der Riese box chooser/glow functions translate
  without unsupported calls. Their generated core, compatibility runtime and
  stub file compile with the native BO2 linker for each map.
- Both outputs retain the real weapon-list helper, `chest_light`, its framework
  initializer and the glow's `waw_playfxontag` call.
- Local evidence: `work/mystery_box_loop_20261015/verify.py`, per-map native
  compiler logs and `verification.json`. No installed map was overwritten;
  live box purchases and relocation have not been retested.
