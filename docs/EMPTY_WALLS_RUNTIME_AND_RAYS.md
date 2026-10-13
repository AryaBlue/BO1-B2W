# Empty Walls runtime and light rays (2026-10-13)

These fixes apply to the shared converter and compatibility runtime. Empty
Walls is the local validation fixture; no map or material names select the fixes.

## Spawn location

The native round controller selects an active zone location separately from its
actor prototype. T6's `spawn_zombie` accepts that location but spawns at the
prototype origin instead. Its spawn callbacks run after a frame boundary. The
shared wrapper now binds `spawn_point_override` and teleports the returned actor
to the selected location before those callbacks run. Matching authored actors
are used when their origins match the selected location within one unit; the
source selection rule still chooses among eligible candidates.

Native initialization also caches the stock round-spawn function. The runtime
redirects that known default to the owned round controller while preserving
custom providers. An already-bound location is retained by later callbacks.

In the baseline live probe, births could occur far outside the starting area.
The corrected probe observed six births exactly at their selected `start_zone`
locations. They remained 2.1 seconds apart, consistent with the authored two-second
delay plus frame scheduling. The first spawn still follows the map's intro;
this change does not shorten authored timers.

## Image streaming

Converted streaming-mode-1 images lacked the header retained by stock T6
character/world images. Both streaming modes now carry the texture format,
flags and mip metadata with zero inline resource bytes. Pixels remain in the
IPAK. Native extraction confirms the corrected header. All 107 inspected
character DDS mip chains match the source exactly, and the IPAK is unchanged.

The same zombie changing outfit is a reported visual defect. Server model
tracking stayed stable during the probe; that does not prove client rendering
is fixed. The user will visually retest later.

## One-sided black light rays

WaW's `wc_unlit_falloff_add` was missing from the recognized world unlit
techniques. Its T6 emissive pass retained the alpha-blended donor program/state.
It now receives the original WaW program and additive state in both UNLIT and
EMISSIVE slots. The original vertex program also needs a normal stream absent
from the native unlit donor. That stream is explicitly routed using T6's
`STREAM_SRC_NORMAL=3` and `STREAM_DST_NORMAL=1`, with the existing packed-vector
adapter. This retains the authored view-angle falloff, vertex color and fog.
Source back-face culling is retained, explaining the one-sided visibility.

The Empty Walls ray material now compiles both original vertex/pixel pairs with
zero unsupported bindings. This validates the conversion and compiled linkage;
the final in-game visual remains to be checked.

## Early effect registration and evidence

Generated asset initialization now precaches each distinct valid mapped FX in
the initial level frame. This removes the live radio initialization error from
a valid electrical effect requested after the source script's first wait.
An earlier longer probe exposed separate undefined arithmetic in the map's
`monitor_ground_bomb`; this is not claimed fixed by these changes.

Local evidence is under `work/zombie_runtime_20261013`: `observations.log`,
`candidate_verification.json`, `ray_material_report.json`, native link/extraction
logs, and the original ray shader assembly. Temporary probes are removed after
the owned test process exits. No diagnostic script is shipped in the map.

Native package validation compares 106 compiled scripts byte for byte, audits
material arguments, checks all character mip chains, and verifies 82,831 terrain
triangles with source geometry, flags and model ownership. The earlier rebuild
also retains all 18 moving terrain roots below the uint16 model-root limit.
