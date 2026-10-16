# WaW gameplay semantics on the BO2 runtime

Branch `shi-no-numa-gameplay`. Found on Shi No Numa; every rule is generic and
keyed on WaW source data, never on a map name.

## Player health

- WaW raises a player's maximum health by assigning `.maxhealth` (Jugg: 160).
  A T6 player's cap lives in its player state and only `setmaxhealth` changes
  it, so health stayed clamped at 100 and regenerated only that far.
  `lower_maxhealth_assignments` routes assignments to compat
  `waw_set_maxhealth` (players: `setmaxhealth`; AI keep the field). This also
  explains electric traps killing Jugg players: Shi No Numa's
  `player_elec_damage` kills unless the player has Jugg and `health - 100 >= 1`.
- WaW's `Callback_PlayerDamage` applies the player's own explosive/projectile
  damage in full; BO2's 75 cap is removed (`WAW_SELF_DAMAGE_CAP`).
- T4 notifies the victim `weapon_pvp_attack` (attacker, weapon, damage, mod)
  for player weapon hits. WaW's Wunderwaffe self-zap (`tesla_pvp_thread`:
  25% of max health, never below 1, electrocution) waits for it; T6 never
  sends it. The owned `callback_playerdamage` raises it with the WaW weapon
  name. The Waffe projectile itself deals 1 damage.
- Measured equal, unchanged: zombie hits 60 (WaW weaponless actors melee with
  `defaultweapon`, meleeDamage 150, times `player_meleeDamageMultiplier` 0.4),
  dog bites 40 (`dog_MeleeDamage` 100 x 0.4), and normal-difficulty regen and
  invulnerability windows (2400 ms delay, 0.2 overlay cutoff, 0.35/0.5/0.3 s,
  1700 ms death invulnerability). Kept: BO2's 0.4 s same-attacker window.

## Power-ups

- WaW `zombie_death_points` rolls a drop for every death before checking the
  attacker (flogger kills drop); zombies `marked_for_death` (electric traps)
  never drop. BO2 also required a player attacker and its "emerged into the
  playable area" flag. `zombiebehavior.waw_drop_rules` applies WaW's rule.
- Drops land only inside WaW `playable_area` triggers (compat
  `waw_powerup_drop`). BO2 checked its zone volumes, which the converter
  synthesizes around spawner groups and which reach outside the playable area.
- Tesla kills skip the ordinary drop in WaW; the Waffe's only drop needs
  `tesla_kills_for_powerup` hits in one chain. Every shipped WaW copy of
  `_zombiemode_tesla.gsc` (Shi No Numa, its patch, Der Riese's patch) sets
  `tesla_max_enemies_killed` 20 and `tesla_kills_for_powerup` 15, and no
  `mp/zombiemode.csv` row overrides them. At the user's request the port caps
  chains at 10 (`tesla_runtime.max_targets`) and drops when a shot reaches it.

## Mystery box

- WaW's chooser offers every key of `level.zombie_weapons`; the port's array
  also holds BO2's framework `m1911_zm` and native helper names. WaW scripts
  read `waw_zombie_weapon_keys()` (WaW-registered keys only).
- WaW `_zombiemode::init_fx` effects (box `chest_light`, eye glow, window
  chunks...) are extracted for keys ported scripts read but never assign.
- Looping effects on a moving parent (box sky marker, Waffe bolt between
  zombies) leave their static FX entity for the parent's tag once it moves.

## Zombies

- `zombie_spawn_delay` is 3 in WaW, 2.0 in BO2's init and stock
  `mp/zombiemode.csv`. Variables WaW's framework sets keep WaW's literal value
  (`framework_zombie_vars`, owned `waw2bo2_set_zombie_var`); only the map's
  own WaW table overrides them.
- Linked-trigger contacts (the flogger) test AI as WaW's 72 x 15 actor across
  the angles swept since the previous frame.

## Client scripts, effects and HUD

- Effect-only client listeners that a map's client `main()` threads (Shi No
  Numa's electric trap arcs) run on the server: `SpawnFx`/`PlayFx` lose the
  local client argument, `level waittill( msg )` waits for `"waw_client_" +
  msg`, raised by compat `waw_clientnotify`; their client effects load on the
  server. Listeners with other client calls stay unported and are reported.
- Owned BO2 dog rounds load WaW's converted dog effects (spawn lightning)
  through `waw_loadfx_native`; BO2's paths name Tranzit assets.
- HUD: `left/right/top/bottom` anchors become T6 safe-area `user_*` anchors;
  WaW HUD hides in menus (T4's opaque pause menu covered it).
- Two-sided source materials keep `cullFace none` on every converted pass.

## Weapons and effects (2026-10-15/16)

- T6 keeps clip and stock per held weapon. An `altmode` weapon resolves to its
  primary's slot unless the alternate sets `ignoreAttachments` (t6zm
  sub_5CC300 -> sub_4E1D20, WeaponVariantDef+472; stock gl_m16_upgraded_zm
  sets it). The box M1 Garand held one round: the M7's clip of 1 overwrote
  the rifle's 8. `weapons.separate_alt_ammo` sets it for alternates with their
  own WaW ammoName. Measured: rifle 8/128, launcher 1/19, independent.
- The Wunderwaffe arc is a trail drawn with a WaW zfeather falloff material.
  T6 trail vertices carry the trail definition's cross-section normal
  untransformed, so WaW's dot(view, normal)^2 falloff was ~0 and the arc
  almost invisible. Trail elements use a `__w2b_trail` material variant whose
  falloff is evaluated face-on. Verified: bright jagged arcs in game.
- Measured in game: the Waffe zaps its shooter for 25% of max health (+1 from
  the bolt), the flogger killed 8 of 8 zombies placed in its sweep.

## Suspensions

- Peter (`hanging_dead_guy`): the source kicks him every 0-7 s with impulses
  up to 20 per axis. Free copies of his and the swamp lamp's models launched
  with forces up to 50000 (centred or off centre) only fall in T6; the engine
  gives these kicks no measurable velocity. The rope solver now gives them the
  same response instead of adding them to velocity (which piled energy up).
  Measured: Peter still for 60 s.

## Open

- Comm room (south-west hut, around 7495 -1239): zombies reported coming
  through boarded windows. Path links through its windows are only the
  barricade traversals; spawns are not inside. Needs an observed entry: the
  user has scripts/zm/waw2bo2_entry_watch.gsc (crouch + knife or
  `set w2b_watch 1`, logs `W2B ENTRY`).
- Zombies under boardwalk planks: WaW fills under-deck space with
  player+monster clip (0x8030200); T6 actors test 0x20000 (mask 0x2820011).
  A 72-unit zombie body stalled at upstairs windows and was reverted. Needs
  the location (location HUD: melee prints `WAW2BO2 LOCATION`).
- Zombies stuck near the flogger: zombies recycled by round_spawn_failsafe in
  probes were all meleeing an invulnerable test player (the WaW failsafe does
  the same). Not reproduced; the compat STUCK monitor logs real positions.
- Zombies through world barriers: needs a location.
