# WaW zombie speed authority

Converted zombies use their source WaW speed selector and movement clips. BO2's
round-speed calculations and later requests to walk must not replace that choice.
The contracts are defined in `compat/gsc_api.json`; the shared implementation is
in `zombiebehavior.py` and the GSC transpiler. There are no map-name speed presets.

Source `level.zombie_move_speed` and entity `.zombie_move_speed` are translated to
`waw_zombie_move_speed`. Native AI retains its own field. The translator follows
selector dependencies, preserves their initialization and round inputs, and
prepares those inputs once per native round before invoking the source selector.
Round-end updates use the previous source round number. Conditional scalar
round-end updates currently produce an explicit diagnostic: they require a
control-flow slice rather than an unconditional guessed update.

The owned native spawn initializer applies source speed before zombie thinking.
Later bootstrap requests go through `refresh_speed()`. Cached native movement
requests are intercepted through the actor's `setanimstatefromspeed` callback,
which restores source speed and the corresponding animation state. Any existing
callback is retained. Staging validates the native callback contract.

Movement tables are read from the source initializer, including uniquely
recognized initializers with different names. Their original clips and variant
weights populate owned server/client animation trees and state definitions.
Both actor scripts reference those clips explicitly: T6 otherwise discards
animation-tree nodes mentioned only as strings in an animation state definition.

## Validation (2026-10-13)

- 499 tests pass, covering field isolation, round-state dependencies, native
  contracts, speed restoration, authored clip binding and initializer discovery.
- Dead Sand Elite and McDonald's were rebuilt and installed locally. Their map
  links report zero missing assets.
- All 93 Dead Sand and 91 McDonald's compiled server/client scripts match after
  extracting the final fastfiles. Final material audits report zero violations
  or missing technique sets (Dead Sand: 23,778 map / 42,018 mod arguments;
  McDonald's: 25,983 map / 44,738 mod arguments).
- Dedicated Plutonium engine probes exercise the actual source selector and
  native speed setter on script structs. Each probe selects 32 round-one speeds,
  requests native walk, then checks that the shared runtime restores the source
  choice. McDonald's selects sprint in every sample. Dead Sand's original rule
  selects run or sprint, with no walkers; a universal sprint override would
  change that source rule.
- These probes validate script execution and animation-tree loading. They do
  not verify live zombie locomotion, window traversal or player-facing gameplay.

Local evidence lives under `work/dead_sand_elite/speed_final_*` and
`work/mcdonalds_spawns_speed/speed_final_*`. Probe scripts are temporary and are
removed from installed mods after validation.
