# Dead Sand Elite build check

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
