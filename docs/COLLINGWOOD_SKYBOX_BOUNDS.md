# Collingwood skybox bounds schema (2026-10-13)

The newer Collingwood failure bundle (`...1791932539757373200 (1).zip`) gets
past dependency extraction and compiles the map scripts. Native map linking
then rejects `skybox_zm_cph_waw` with:

```
(/boneInfo/0/mins) type must be array, but is object
```

The generated skybox copies the BO2 Mod Tools donor model. Mod Tools exports
`boneInfo` vectors as `{x, y, z}` objects; the bridge model schema added for
authored hitboxes requires three-element arrays. Copying the donor definition
unchanged became incompatible with that schema. The linker still wrote a map
fastfile after warning that the skybox could not load, and the build correctly
rejected that incomplete result.

Skybox staging now normalizes `mins`, `maxs` and `offset` objects into arrays
in explicit x/y/z order. Existing arrays remain unchanged. Bone names, radius,
classification and other metadata stay in the generated definition. Both the
native donor path and source sky path use the same adapter. A malformed object
missing a coordinate raises an explicit staging error.

Validation uses the actual BO2 donor sky model and native bridge linker:
the unchanged definition reproduces the reported parsing failure; the corrected
definition links and extracts successfully. Extracted numeric bounds, offset
and radius match within floating-point precision. The fixture uses a tiny black
cube as its texture because it tests model loading, not the source sky pixels.
The rigid GLB's existing importer names its generated root `root`; the source
bone name is preserved in staged JSON, but this change does not alter that
pre-existing rigid-model import behavior.

Local logs and the verification receipt are in `work/collingwood_skybox_bounds`.
A full Collingwood build remains unverified: its source is not available here.
No map package was installed or desktop release published for this fix.
