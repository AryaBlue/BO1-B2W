# Converted zombie headshot hitboxes

McDonald's characters attach a separate head with `attach(headModel, "", true)`.
The third argument disables collision on that attachment. Their headless body
models therefore carry authored head and helmet hitboxes even though no head
vertices are visible in the body mesh.

The importer reconstructed bone bounds from vertices assigned to each bone.
That reduced a headless body's head and helmet bounds to zero. The bone names
and hit-location classifications were correct; the invisible collision volume
had been lost during asset conversion.

For `bo2_c_zom_zombie3_body05_g_upclean`, the original WaW `j_head` has:

- Minimum: `[-1.4751332, -4.1106834, -3.7408929]`
- Maximum: `[7.7169375, 5.8517523, 3.7395332]`
- Offset: `[3.1209021, 0.8705344, -0.00067985]`
- Radius squared: `59.9252663`

Before this fix, every one of these values was zero in the converted body.
The original helmet radius squared is `101.8206711`; that was also zero.

The T4 exporter now writes authored `boneInfo` to model JSON. The T6 importer
matches it by bone name, preserves bounds, offset, and radius, and maps the
source hit-location name to T6's enum. Names matter because T6 inserts
`torso_middle` into its hit-location enum and GLTF import can reorder bones.
Geometry-derived bounds remain the fallback for sources without this metadata.
Invalid authored bounds fail linking instead of silently collapsing.

The desktop build pipeline automatically compares authored animated-model
hitboxes against the unlinked map fastfile. This detects missing bones and
changed bounds after linking. Old extraction caches refresh through the native
tool digest when the updated T4 exporter is used.

Evidence is under `work/dlc3_20261012`: the original model dump, the pre-fix
T6 collision diagnostics, build logs, and post-link hitbox audit. This diagnosis
and fix were made entirely through source and binary data; gameplay testing is
still required to confirm the result in the running game.
