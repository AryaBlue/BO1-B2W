# WaW dog rounds

Branch: `codex/dog-rounds`. Evidence: `work/flogger_qr_rounds` (dogs*, probe*).

## What was missing

- WaW starts dog rounds from `_zombiemode::main` -> `_zombiemode_dogs::init`
  (only when the map set `level.dogs_enabled`). Both are framework scripts
  BO2's `_zm` replaces, and nothing started BO2's counterpart.
- Every WaW `actor_*zombie*` spawner was built on BO2's human zombie actor, so
  the 112 Shi No Numa dog spawners became human-skeleton zombies.
- The map's client scripts are not ported; Shi No Numa's dog fog lives in
  `nazi_zombie_sumpf_fx.csc` (`level waittill( "dog_start" ); SetVolFog(...)`).
- The build never used the map's `_patch` zone as a script root, so updated
  framework scripts in it (here the dog health table 350/700/1000/1250) fell
  back to a different stock copy (Der Riese's 400/900/1300/1600).

## Conversion

- `zombie_runtime.actor_templates`: the WaW aitype's engine AI type
  (`self.type = "dog"`) selects the native T6 family. Dogs use BO2's TranZit
  dog actor (`zombie_dog`) with WaW's appearance scripts, on an owned tree
  `waw2bo2_dog_actor` = TranZit's shipped graph + Nuketown's
  `zm_traverse_barrier` window state. Measured: Nuketown's unshipped dog graph
  lacks `restart` on its attack states; a dog bit once and then stood still.
- `zombie_runtime.dog_rounds`: the framework hook starts an owned copy of
  BO2's `_zm_ai_dogs` (same round counts, first dog round 5-7, then every 4-5)
  guarded by `level.dogs_enabled`; the source's spawn selection
  (`dog_spawn_sumpf_logic`) runs over the spawners the map opened
  (`level.enemy_dog_spawns`), and the source health table is applied by a
  spawn function. The owned copy plays the WaW aliases the source plays at the
  same points (`pre_spawn`, `bolt`, `spawn`, `dog_round_start`,
  `ann_vox_dog_start`, trail loops, `zombie_dog_death`, `zdog_close`, and
  `dark_sting`/`bright_sting` instead of BO2's dog music). BO2's stalking
  growl has no WaW counterpart and stays silent.
- Client fog monitors of the source map run on the server at the moments the
  dog runtime sends the clientnotify (`dog_round_starting`; `last_dog_down`
  + 2 s and `dog_round_ending`), using the converted `waw_setvolfog`.
- `--waw-patch-script-root`: a map's `_patch` zone scripts take priority over
  the map zone's (WaW loads the patch zone after the map).

## Live check (forced dog round, stationary player)

Two dogs spawned near the player with WaW health 350, bit repeatedly (25+
bites, no freeze; before: one bite each, then frozen for 50 s), all WaW dog
aliases exist, the grey dog fog applied, zero script runtime errors.
Not verified: window jumps by dogs, multi-player dog counts, the max-ammo drop.
