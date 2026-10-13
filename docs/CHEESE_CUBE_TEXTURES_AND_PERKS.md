# Cheese Cube texture and perk investigation

The converter changes preserve source assets and behavior without naming this
map, its weapons, or its perks in the implementation.

## Double Dew

The source defines `specialty_shades` as a multiplier on **kill points** in
`_zombiemode_score::player_add_points`. It does not multiply every award. The
bridge retained the perk marker but replaced the source scoring framework with
native BO2 scoring, losing the authored arithmetic.

`scorebehavior.py` extracts pure perk-conditioned point arithmetic and retains
its source event and condition. An owned copy of native BO2 scoring applies
those rules before the native final multiplier. Owned spawn/death callbacks
route to it; native statistics and team bookkeeping remain intact. Rules with
other side effects or unknown local state are not copied.

## Default interaction hints

The photographed arm pickup is an authored `trigger_use` with no explicit hint.
WaW supplies its default use prompt; BO2 instead displays
`MISSING_ACTIVATE_TRIGGER_TEXT`. A generated initializer applies the source
`PLATFORM_HOLD_TO_USE` localization key to unnamed-hint trigger groups before
the source scripts initialize. Authored hints remain authoritative, and scripts
can replace or clear the generated default.

## Cheese materials

The supplied Cheese-o-matic machine image is the intended source appearance.
Its pixels were already recovered from the map's IWD. Its model materials,
however, retained names shared by cached BO2 materials. Converted materials
whose names collide with the extracted stock set now receive isolated asset
identities; GLTF, world FBX, FX and HUD references follow the rename.

The upgraded Cheese Gun's `mc/mtl_cheese` material has reveal and scrolling
texture layers represented by `nameHash`, `nameStart`, and `nameEnd`, without
a readable texture parameter name. The shader adapter previously ignored those
entries and reported absent native texture bindings. It now resolves those
bindings by the authored hash and preserves the opaque name fields supported
by the T6 material loader.

The previously installed unupgraded `cheese_gun` uses the converted MP40 model
and `weapon_mp40_mp_c` image; that image is pixel-identical to the source IWD's
cheese texture. The upgraded custom weapon uses `cheese_pap_col`. The stock
`zombie_mp40_upgraded` is a separate source weapon with a gold material. The
reported weapon's upgrade state is unknown. An in-game check is still required
to identify whether the unupgraded custom weapon has a further runtime issue.

## Related transpiler repair

A full rebuild exposed rejection of the source's braced `if` guard around its
zombie speed update. The speed-state slice now retains recognized ancestor
guards. Unbraced or unsupported conditional control flow still fails explicitly;
unrelated loop effects are not copied.

## Validation

Evidence and the rebuilt candidate are under `work/cheese_visuals_perks`.
All 512 tests pass. Native linking reports no missing assets. The material
audits check 31,150 map arguments and 45,822 mod arguments with zero violations;
5,210 authored bone hitboxes are preserved across 115 models. All 107 compiled
scripts match the linked map byte-for-byte. The upgraded cheese material keeps
16 shader slots, including the previously rejected lit passes; both opaque
texture hashes and their source image references survive native linking.

The MP40, upgraded cheese camo and Cheese-o-matic machine images match the
previously extracted source PNG pixels exactly. Terrain vertices and triangles
match the verified water-fix build; cmodel 242 retains 16 roots and water
contents `0x20`. The default prompt resolves from WaW localization, and owned
spawn/death callbacks reference the new native score adapter.

The candidate is staged separately while the user tests the installed water
collision fix. Gameplay outcomes and visual appearance require a map restart
and live verification.
