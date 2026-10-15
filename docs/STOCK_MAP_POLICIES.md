# Stock WaW map policies, round count, flogger contacts

Branch: `codex/flogger-qr-rounds`. Evidence: `work/flogger_qr_rounds`.

## Stock map policies (retail WaW levels only)

`builddriver` passes `--waw-stock-map` when the source fastfile sits in the WaW
install's `zone/` folder (the signal `all2raw.source_dumps` already uses).
Only then does `gscport.port_map(stock_map=True)` apply
`gsc_api.json` `stock_map_policies`. Custom maps keep their own logic.

- `solo_quick_revive` (user request 2026-10-14): BO-style solo Quick Revive.
  The source cost assignment under `case "specialty_quickrevive":` asks
  `waw_stock_perk_cost`, which returns 500 in a solo game and the source cost
  otherwise. A solo purchase registers one BO2 life (`self.lives = 1`), BO2's
  native last stand spends it on a self revive, and after three purchases the
  machine stops selling (`level.solo_lives_given`, like BO1/BO2). The machine
  hint uses BO2's own `ZOMBIE_PERK_QUICKREVIVE_SOLO` text with the solo price.
- `waw_health_overflow` (user request 2026-10-14): WaW's `ai_calculate_health`
  adds `int(health * 0.1)` per round with no guard, so the 32-bit value wraps;
  a wrapped round spawns at round-1 health ("insta-kill rounds"). BO2 clamps
  instead. After BO2 sets the round's health (`zombie_total_set`) the WaW
  sequence replaces it. Live: round 159 = 1,529,408,993; 163, 165, 167, 169
  = 150; 164 = 2,033,631,761 (WaW's alternating pattern). Der Riese is
  excluded by the user's explicit `excluded_levels` list: its source health
  code is identical to the other retail maps, so no source signal exists.

Custom maps used to get a solo self-revive life from any WaW Quick Revive
purchase (`waw_setperk`). That is now registered only by the stock policy.

## WaW round counter (stock maps)

Measured: BO2 draws rounds from `setroundsplayed` in its Lua HUD, an 8-bit
value (`setroundsplayed(300)` draws 43), and `round_think` clamps
`level.round_number` at 255. `setroundsplayed(0)` does not reliably hide it
(the previous tally stayed). `waw_round_counter` therefore:

- extracts the source display: `chalk_one_up` runs on BO2's
  `level.zombie_round_change_custom` hook (where WaW's round_think called it;
  BO2's round-start music call is kept), `chalk_round_hint` on `end_of_round`,
  and the HUD objects come from the source `round_start` assignments that
  create them with the framework's own functions (`create_chalk_hud`), never
  round state such as `round_number`/`first_round`;
- patches the owned `_waw2bo2_zm.gsc` so `setroundsplayed` and the 255 clamp
  are skipped only while `level.waw2bo2_waw_round_counter` is set, and points
  `level.round_think_func` at that owned `round_think` (BO2's gametype starts
  the stock one through this hook; the first build showed BO2's chalk on top
  of WaW's and still capped at 255);
- converts WaW's `hud_chalk_1..5` (precached by the source
  `precache_shaders`) although BO2 ships materials of those names; material
  isolation renames them `waw_world/hud_chalk_*`, and names built at run time
  (`"hud_chalk_" + n`) resolve through the generated
  `_waw2bo2_hud_materials.gsc` table (`waw_hud_material`).

Shared fixes found on the way: `extract()` now honours entries deliberately
extracted from no-extract framework scripts, and `extract_level_state` splits
whole top-level statements (an assignment right after a `for {}` block was
silently dropped).

BO2's game-over text uses `level.round_number`, not the 8-bit value.

Live check (work/flogger_qr_rounds/hud_waw2): only WaW's red chalk is drawn;
a forced end of round 299 starts round 300. Jumping rounds by script past 11
from 6-10 leaves WaW's second tally on screen, because the source deletes it
only at round 11; normal play never skips it.

## Round count from source

`Translator.extract_round_total` takes the source `round_spawning` statements
from the first assignment of the local stored into `level.zombie_total` up to
that store and registers them as BO2's `level.max_zombie_func`. Earlier locals
read by the formula are reported, not guessed. Solo WaW: round 1 = 4 zombies
(BO2 gave 6), rounds 5+ stay at `zombie_max_ai` (24). Live probe: round 1
total 4.

## Explicit `player_damage_override` calls

A map script calling WaW's `_zombiemode::player_damage_override` (the solo
flogger) used to reach BO2's damage callback of the same name, which needs a
weapon name (`freezegun_zm` comparison error). `function_renames` routes it to
`waw_player_damage_override`: below current health it only marks the attacker
(WaW never takes health there); otherwise native damage lets BO2's last stand,
solo revive and game over decide. Live: 160 HP (Jugg) under the spinning log =
no damage; 100 HP + QR = downed, self revive, life spent; again without a life
= game over.

## Linked trigger contacts

Measured: T6 does rotate a linked brush trigger (its absolute bounds follow
the log's pitch), but the fast-spinning flogger (~470 deg/s) misses most
contacts with the oriented box. `linkto` is a compat wrapper; for a
`trigger_multiple` it threads `waw_linked_trigger_contacts`, which, only while
the parent rotates, tests entities the spawnflags admit (1/2/4 AI teams, 8 no
players) against the oriented box with their live bounds and sends the WaW
`trigger` notify when `istouching` misses. Live: a zombie on the real floor
under the log (T6 actor bounds 50 units tall, top 8 units inside the swept
volume) dies 3.35 s after activation; a floating zombie took ~6 s before.

## Limits

- T6 zombie bounds are 50 units tall; WaW actors are taller. Contacts use the
  live T6 bounds, so a zombie at the edge of WaW's reach may still be missed.
- The solo QR hint text and the machine shutdown after three buys were not
  visually checked in game.
- Earlier "flogger verified" probes held victims in mid air (z -640; the
  floor under the log is z -681). Probe artifact: a player held 1 unit inside
  the floor takes fall damage, which sets BO2's `self.intermission` and makes
  the player immune for the rest of the test.

## Live ragdolls die at frame end (all maps)

User report: the flogger needed two hits. Measured: one hit killed, but
0.75 s later (the source's delayed `dodamage`); WaW throws the zombie as a
live ragdoll at once, while T6 cannot ragdoll a living actor, so the zombie
kept walking about one log revolution. Every WaW use found ragdolls a doomed
actor: flogger and KF2 zeds kill it 0.75 s later, the bridge 1 s later (all
without an attacker); zipline, shield and baby-gun kicks kill it in the same
frame, with the player credited. `waw_startragdoll` now kills a live actor
its script did not kill within that frame at frame end (no attacker) and the
body takes the launch; same-frame kills keep their attribution. `dodamage`
goes through `waw_dodamage`, which ignores an actor T6 already removed (the
source's later kill). Live: hit and death at the same server time
(26200 ms; before: death 750 ms after the hit), zero script runtime errors.
A source branch that ragdolls without ever killing now ends in that frame-end
death instead of a permanent live ragdoll.
