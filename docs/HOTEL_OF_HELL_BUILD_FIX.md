# Hotel of Hell animation notification build failure

The supplied `zm_a_room_waw-failure-1792336427614730500.zip` stops during
staging with `WeaponError: raw animation has no valid notification suffix`.

The map's localized zone supplies `zombie_bo2_perk_bottles`, whose raise,
quick-raise and empty-raise fields use `bo2_viewmodel_zombie_perksacola_drink`.
Its valid raw v17 notification section contains these native sound events:

| Event | Frame |
| --- | --- |
| `sndnt#evt_perk_bottle_open` | 16 |
| `sndnt#evt_perk_swallow` | 29 |
| `sndnt#evt_bottle_break` | 57 |

The weapon's sound map includes `bottle_break`. The initial byte search in
`animnotes.add_sound_events` finds that key inside `sndnt#evt_bottle_break`,
but the suffix validator previously required an exact mapped event name.
It rejected the valid section because none of its events needed translation.

Suffix validation now runs independently of sound-map matching. The existing
translation loop matches whole event names, preserving native events and
leaving animations with no mapped events byte-for-byte unchanged. This rule
applies globally, without map or weapon name exceptions.

Regression tests cover native event suffix matches, mixed native and mapped
events, and continued rejection of truncated notification sections. The full
suite ran 684 tests successfully (one skipped). A source-asset audit checked
1,087 animation references and confirmed that the drinking animation stays
unchanged. Local build evidence is in `work/hotel_build_fix_20261018/`.

## Subsequent soundbank linker failure

After staging succeeded, the gameplay linker rejected `EntityLimitCount=256`
with the accepted range `[0, 128]`. The affected aliases are
`wpn_fnp45_fire`, `wpn_fnp45_fire_pap`, `wpn_shell_default_rifle` and
`wpn_shell_eject_rifle`; some also have `LimitCount=256`.
The native `LoaderSoundBankT6.cpp` enforces that range for both columns.
The existing sound CSV range conversion now saturates both counts to 128
and records each change in `sounds.bank.json` (22 count changes on this map).
Limit policies, including `none`, remain unchanged. A limiting policy with
a count above 128 cannot retain its original threshold in this output format.

## Completed build validation

- Gameplay zone linking and map script compilation completed.
- Map linker exit code 0, zero distinct missing assets.
- Material audits: 38,009 map arguments and 46,932 gameplay arguments,
  zero violations or missing technique sets.
- Authored bone hitboxes: 4,387 checked, zero violations.
- Mod package: `work/hotel_build_fix_20261018/package/zm_a_room_waw/`.

Build validation does not establish gameplay compatibility. Existing staging
warnings remain, including unsupported Widow's Wine grenade/bottle model flags
and shader translation failures. No in-game playtest was performed.
