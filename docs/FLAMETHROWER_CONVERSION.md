# WaW flame weapons and the T6 overheat HUD

Gas weapons retain their original weapon definitions, heat rates and flame
tables. The two flame-table names in a WEAPONFILE are nested dependencies,
not standalone zone assets. The native T6 loader must populate both pointers;
preserving their names alone produces null pointers in the linked weapon.
The native dumper exports those tables so final fastfiles can be audited.

Material and sound references are namespaced. Its effect materials use the effect translator,
and their images are included explicitly because the baseline mod-tools
linker does not traverse these tables.

WaW supplies 119 table fields; T6 adds fire and drip brightness multipliers.
Absent multipliers become one, retaining T4's unscaled brightness. Explicit
values, including zero, remain intact. The outer fuel/flame ribbon length
also bounds the gas weapon's otherwise unlimited range values and the native
carrier's travel lifetime (`length / speed`). Shorter authored lifetimes and
range values remain intact. This prevents a held shot from becoming a long
damaging beam while retaining the source textures, speed, heat and damage.

T6's stock `ui_mp/t6/zombie/otherammocounters.lua` contains two misspelled
constants: `beingAnimation` in the transition out of overheating, and
`pluse_low` in the pulse animation. The former causes a fatal LUI error when
the weapon cools after overheating. `overheathud.py` extracts the installed
stock bytecode and applies equal-length constant corrections. It runs only
for carried source weapons with `overheatWeapon=1`; it does not change their
heat values or disable overheating. Explicit project rawfiles override stock
disk files and the loaded gameplay baseline during both link phases.

Native flame initialization is a separate runtime requirement. T6 defaults
`flame_system_enabled` to zero. The CSC builtin `enableflamesystem()` allocates
the source/lookup, stream, chunk, fire, drip and smoke pools, then sets the
enabled flag. Setting that flag directly makes the allocator return early;
the native reset subsequently writes through null pointers. The generated
environment CSC calls the initializer only for carried gas weapons with
source flame tables. No launch-time dvar override is used.

Native addresses in the mapped T6 executable: CSC wrapper `0x7CE3A0`, full
allocator `0x6F9980`, source-pool allocator `0x5FCA40`, reset `0x4AE180`.
Visible flames, damage, and repeated human overheat cycles still require
runtime verification. Bot heating tests do not exercise the human LUI and
cannot validate this crash correction.
