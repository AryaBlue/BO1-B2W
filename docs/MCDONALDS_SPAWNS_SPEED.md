# McDonald's zombie spawn and speed translation

## Follow-up after the first playtest

The player confirmed faster zombies, but reported a remaining pace difference
and few arrivals at the window. The first change preserved the speed label;
native actor states still selected BO2's sprint v1/v2 animations. The source
movement table assigns every sprint variant to WaW's `ai_zombie_sprint_v4`.

The converter now reads the authored movement table and binds its converted
clips through an owned actor animation tree and state definition on both
server and client. Other native states, including window traversals, remain
in that state definition. Conditional table assignments are reported explicitly
rather than evaluated by guessing. This changes the movement animation itself;
no speed multiplier is invented.

Spawner selection is now extracted from the source round loop and translated
as a regular script. McDonald's rerolls once when the chosen spawner matches
the previous one; it can still choose that spawner again. History resets each
round. The native round manager calls that source sampler when selecting actor
spawners. Authored positions remain spread around the map; no near-window bias
is added. Arrival rate and physical movement need another playtest.

Follow-up validation: 491 tests passed; native linking and both material/hitbox
audits passed; 91 compiled scripts matched after extraction. The owned actor
tree and state definition matched their staged bytes after extraction from
`mod.ff`, and the linked asset list contains `waw_anim_ai_zombie_sprint_v4`.
The extracted sprint state references only that source clip. This Unlinker
does not export T6 xanim payloads, so a payload round trip was not performed.
The updated build is installed as `zm_mcdonalds_waw`; restart the game so its
mod fastfile and animation assets reload.

Branch: `codex/mcdonalds-spawns-speed`. Local conversion and native validation
completed on 2026-10-12 with converter 0.2.14 plus branch changes.

## Source evidence

The original map's `mcdonald's.iwd:maps/_zombiemode_spawner.gsc` overrides
`set_run_speed()` with `self.zombie_move_speed = "sprint";`. Its spawn initializer
calls the run-cycle setup before zombie thinking. A stock BO2 speed selector
therefore loses the map's authored speed even on Original difficulty.

The compiled WaW entity data has four plain zombie spawners and no
`exterior_goal` structs. It has ten negotiation pairs, including four
`wall_hop` window traversals. Their graph links have zero disconnect counts.
This does not support adding artificial barricades to make those windows work.
The converter's existing no-barricade `find_flesh` route remains in use.

Native BO2 `do_zombie_spawn()` chooses a random active zone location independently
of the selected actor spawner, and copies that location's target and zone state.
A plain WaW `spawn_zombie()` instead spawns at its selected spawner's origin.

## Converter change

`compat/gsc_api.json` now defines the source speed-selector contract and native
spawn callback/location adaptation. The translator extracts the actual source
function and its reachable dependencies into the shared core. This preserves
conditional or computed speed rules as source code rather than inferring a
speed preset from a map name or a literal.

The shared runtime replaces registered native spawn-initializer pointers with
an owned copy of that native script. Other registered callbacks remain intact.
The copied initializer applies the source selector through BO2's animation
run-cycle support before starting zombie thinking. The native framework stays
on Original so its Easy branch does not alter the shared round speed state.

Plain spawners bind to their matching active spawn location by origin. That
location is selected before target, zone and spawn-point metadata are copied.
Risers continue through native zone-based placement; inactive or unmatched
locations do not receive a forced override. Source spawner targets are carried
onto generated location structs. Native runtime sources and map input files
are not modified. Changed native callback contracts produce explicit errors.

## Validation and remaining uncertainty

- 486 tests passed, including source speed dependencies, callback ordering, location metadata, native contract diagnostics and spawner targets.
- Map, gameplay and lobby fastfiles compiled and linked; map linking reported zero missing assets.
- 90 compiled server/client scripts matched byte for byte after extracting the linked map.
- All 2,323 source path nodes, their link destinations/distances/disconnect counts, all ten negotiation links and the source visibility table were retained in staged paths. Native extraction confirms the linked node count.
- Four spawn locations match the four source actor origins and use the existing no-barricade chase route.
- Material audits checked 25,983 map and 66,785 mod arguments with zero violations or missing technique sets.
- 5,598 authored bone hitboxes across 122 models matched after linking.
- Installed locally as `zm_mcdonalds_waw` for testing. Evidence: `work/mcdonalds_spawns_speed/build.log` and `verification.json`.

Gameplay has not been verified. Graph preservation and compilation do not prove
that every window traversal succeeds at runtime. The next playtest should check
round-one sprinting, arrivals at the reported window, roof/drop spawns, and
later-round riser or zone behavior. Reported unsupported script calls remain
visible in the stage report.
