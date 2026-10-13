# Dead Sand Elite build check

## Weapon registry overflow repair (2026-10-13)

A fresh-process crash at `0x0095238A` occurred during perk bottle precaching.
The matching Plutonium executable shows this address is the weapon-name hash
comparator used by `bsearch`. A local dedicated-server reproduction recorded
the registry reaching 256 entries, then becoming corrupted. Restarting alone
did not resolve this failure.

The converter now removes unused BO2 template weapon entries, retains native
runtime equipment and weapon dependencies, and generates matching client
registration. BO2 also automatically registers weapon rows from
`zm/zm_statstable.csv`, including weapons obtainable through parent zones/raw
lookup. Unused weapon rows retain their indices and names but have their weapon
category cleared, matching the inactive rows already present in the stock table.
The generated table is linked through the existing priority override layer.

485 tests pass on the isolated `codex/dead-sand-elite` branch. The local server
load test reached 148 registered weapons
without an access violation or configstring-limit error. The rebuilt mod removes
52 unused template entries and preserves all 73 carried converted weapons.
This verifies server loading; interactive client gameplay remains unverified.
Evidence is under `work/dead_sand_elite/load_fix*`, `registry_before_fix.json`
and `registry_after_pruning.json`.

## Shared ammo cap repair (2026-10-13)

After the initializer repair, launch reported a shared ammo cap mismatch for
`WEAPON_BETTY`: `bouncing_betty` specifies 4, while `mine_bouncing_betty`
specifies 2. Both are converted WaW definitions carried by the gameplay zone.
The same source group conflict exists between `60mm` (4) and `mortar_round` (1).

Weapon translation now namespaces `sharedAmmoCapName` and includes the authored
capacity in the group key. Matching source names and capacities continue to
share a group; incompatible capacities use separate groups. The numeric limits,
ammo names and clip sharing retain their source conversion. Regression coverage
checks isolation from stock BO2 groups, compatible sharing and unchanged limits.
493 unit tests passed. The rebuilt gameplay fastfile was installed locally.
Extraction verified all 176 weapon definitions: only the 13 intended shared
cap names changed, every numeric capacity remained intact, and no shared-cap
group contains conflicting limits. The mod material audit checked 64,065
arguments with zero violations. Gameplay has not been verified.
Local repair evidence is under
`work/dead_sand_elite/ammo_fix*`.

## Launch initializer repair (2026-10-13)

The reported launch error was `Unresolved external: "init" with 0 parameters`
in `maps/mp/zm_dead_sand_elite_waw.gsc`. The map retained an
`_waw2bo2_animtrees::init()` hook from an earlier conversion, but the current
script dependency graph required no script-model animtrees. Re-porting cleared
the server initializer while the empty-tree hook pass left the old call and
client initializer intact.

The shared hook pass now removes both calls and obsolete registration scripts
when the tree list becomes empty. Script compilation also validates generated
map initializer targets before invoking the native linker. Regression coverage
reproduces a rebuild after the server initializer has been cleared.

Validation: 492 unit tests passed. The repaired map was recompiled and linked
with zero missing assets and installed in the local Plutonium mod folder.
All 86 compiled scripts matched the linked fastfile after extraction;
23,778 material arguments and 3,509 authored bone hitboxes passed their audits.
Gameplay has not been verified. Further local evidence is saved under
`work/dead_sand_elite/init_fix*`.

Tested on 2026-10-12 from main `fb45af2`, with the general framework detection
changes on `codex/dead-sand-elite`. Converter version: 0.2.14 plus those changes.
Source: [Dead Sand Elite on CodRepo](https://callofdutyrepo.com/2009/05/16/dead-sand-elite/).
The NSIS download was extracted as an archive; the installer was not executed.

Input `dead_sand_elite.ff` SHA-256:
`f2c7cd0c39955c353e54392f00fa64aa257965f2034e98a04e47a567641f4aa7`.
Its sibling IWD, `mod.ff` and loading fastfile were used without editing them.
Source-only effects, remastering and BO2 stock perks were disabled.

## Failure and converter change

The supplied older failure report used 0.2.10 and stopped because there were
no `add_adjacent_zone` calls. The current converter already handles that layout
through its spawner-derived zone graph. On current main, the next failure was
the absence of a `maps\_zombiemode::main()` call: the map calls a renamed copy
of the WaW zombie framework instead.

The converter now identifies a directly called startup script from its
framework functions, `_load::main()` call and wait for `all_players_connected`.
It binds that script to the existing framework override translation, including
qualified calls, function pointers and includes. Ambiguous startup frameworks
fail explicitly. Detection does not use map names or filename patterns.
Startup hooks retain their receiver and `thread` invocation, so the map's
background light-flicker loop remains asynchronous. The generated startup
comment also ends with a newline so inline map scripts keep their following code.

## Verification

- 482 unit tests passed, including renamed-framework, ambiguity, alias and inline-startup regressions.
- Native map, gameplay and lobby fastfiles linked successfully. Map linking reported zero missing assets.
- 87 compiled server/client scripts matched byte for byte after extracting the linked map fastfile.
- Map and mod material audits checked 23,778 and 64,065 arguments respectively, with zero violations or missing technique sets.
- 3,509 authored bone hitboxes across 91 models matched after native linking.
- Installed as `zm_dead_sand_elite_waw` in the local Plutonium T6 mods folder.

Local build evidence is under `work/dead_sand_elite/`: `fixed_build.log`,
`verification.json`, `build/stage/` and `build/mod_build/`.

Gameplay has not been verified. Reported script gaps remain: `oktospawn`,
`stalingradspawn`, `badplace_cylinder`, `getdebugdvar` and
`maps\_arcademode::arcademode_assignpoints_toplayer`. A successful build and
asset audit do not establish that every custom gameplay path works.
