# Stock WaW Shi No Numa conversion

Branch: `codex/shi-no-numa-dlc2-port`. Input is the stock World at War
`zone/english/nazi_zombie_sumpf.ff`, not the BO1 or BO2 remake.

## Shared conversion changes

- Stock map selection no longer treats the shared language-zone directory as
  a custom mod folder and imports every unrelated sibling fastfile.
- Movement-table extraction resolves immutable `level.script` comparisons
  against the selected source map. DLC2 Japanese movement clips and their
  authored weights survive alongside the common movement entries.
- The shared spawn adapter supports the source controller's active
  `level.enemy_spawns` membership, its simple random-index selection, and its
  separate riser array. The chosen actor stays associated with its selected
  location. Source nearby-team respawn logic is registered through the native
  callback, and source anchor points are excluded from native zone spawn lists.
- Native shadow samplers use GREATER depth comparisons. Translated SM3 shaders
  load depth texels directly and reverse the sampled/reference relationship
  while retaining the original comparison instructions.
- Source water programs can request scene depth (native code texture 18) and
  scene color (9) even when the donor program lacks those inputs. A stock
  reciprocal-depth decoder establishes the camera-depth conversion. Shi No
  Numa's source water material includes `case64blue`, but its actual water
  shader does not read that debug color map; a generic lit fallback did.
- Barricades match the source plank depth using the measured final root
  translations of native repair animations. The entry struct remains the
  repair trigger; attack slots stay outside. The earlier entry-based anchor
  double-counted the animated board offset and moved attack slots into the wall.
- Shadow-only helper surfaces retain geometry but carry native `NO_DRAW`.
  A stock BO2 world audit shows shadow-caster surfaces use flags 25, including
  that bit; the bridge previously assigned 17 to every surface. The source
  has nine shadow-caster surfaces, including thin panels and a floor strip.
- WaW clipmap physics constraints are exported as a versioned JSON sidecar,
  staged with explicit attachment validation, and linked into the T6 clipmap.
  Named entity attachments rebind in T6 instead of retaining source entity
  indices. This preserves Peter's rope and the hanging swamp light's rope.
  Dynamic-entity attachments fail explicitly until dynent conversion exists.
- Renamed material identities also propagate into lightmap and constraint
  manifests, preventing references to cached stock materials.

## Evidence and remaining validation

Local evidence is under `work/shi_no_numa_dlc2`. All 543 Python tests pass, and
both native tools rebuild. The source contains two rope constraints: Peter's
34-unit rope and the swamp ceiling light's 60-unit rope. These were previously
lost because the exporter omitted the table and the linker created an empty one.

The earlier live spawn probe observed six Japanese zombies with source spawn
locations and walk speed. Source/native lightmap triangle assignments and UVs
match; extracted secondary image pixels match the generated source pixels.
The separate `zm_shi_no_numa_waw_shadowdiag` package bypasses dynamic shadow
comparisons while retaining baked lightmaps. The user's diagnostic test made
the shadows somewhat better, but did not remove all reported artifacts.

The investigated cutout plank material already emits discard instructions in
its visible translated passes. Later user screenshots locate opaque black
panels at doorways and outside buildings. The helper surfaces needed both
`NO_DRAW` and exclusion from camera color ranges; the user confirmed the panels
are gone after the range correction. Final shadow, water and barricade behavior
still need broader visual validation.

Peter's rope remains unresolved and the user explicitly deferred it. Both
constraints round-trip, and live native tables bind the named entities and
initialize two server/client ropes, but Peter still falls after PhysicsLaunch.
Preserving the constraint data is not a verified hanging-body fix.

The Wunderwaffe's source Tesla chain is now explicitly extracted and registered
with T6's zombie damage callback for hip fire and ADS. Previously only the
mystery-box availability function was reached. Its electric trail is retained,
and the T4 placeholder `tank_shell` impact is translated to `none` when the
Tesla bolt has no authored explosion effect. The requested ten-zombie limit
caps the source chain's twenty-target default. Source Tesla deaths bypass the
ordinary native death-points/drop path, preserving the source chain's ownership.
The clean live probe fired one Tesla projectile into twelve 10,000-health
zombies: exactly ten died and two remained, with no script runtime errors.
An earlier probe observed barriers opening and zombies entering the playable
area. Nineteen windows are calibrated; native repair translations average
31.1586 units forward. Visual board alignment and absence of explosion FX
still require user confirmation. The rebuilt map links with zero missing
assets; 68,915 map / 41,061 mod material arguments and 2,283 hitboxes pass audits.
Do not equate a successful link or a server entity's unchanged origin with
correct client physics or rendering. Dogs, traps, the zipline and complete
multiplayer progression have not been comprehensively played through.

The maintained T4 exporter now includes the v5 vertex-layer stream and v6
shadow geometry/light-region tables consumed by the Python reader. The
previous maintained exporter wrote v4; this map had consequently lost
333,780 bytes of layer data and 43 shadow-light records. The new export
preserves the existing positions, indices, static models and brush ownership.
