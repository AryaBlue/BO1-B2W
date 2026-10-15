# Sound gain, attenuation, and voice limits

## Rooms, ambient packages and reverb level

A WaW map's `clientscripts/<map>_amb.csc` declares its ambient rooms and
packages; map `ambient_package` triggers name them. BO2's `_ambientpackage`
has the same API, so the converter ports `main()`'s declarative calls into the
generated `<project>_amb.csc` (`sounds.port_ambient`): packages and their
elements, rooms, room tones and room reverb. The room and package a WaW
script activates at startup become BO2's default room and package (code
triggers fall back to them). Rooms a trigger names but no script declares get
the default room's settings; otherwise BO2 deactivates reverb there and its
audible stock preset plays. Element and tone aliases are added to the sound
dependencies; any that do not convert are dropped and reported.

BO2 reverb is RAD (`radverb`), not I3DL2, and a map cannot add its own driver.
Each WaW patch therefore selects the stock radverb of the same room class
(`EAX_RADVERB`, e.g. MOUNTAINS -> `gen_hills`, HALLWAY -> `gen_hallway`); the
`gen_*` presets are loaded by `zmb_code_post_gfx` on every zombies map.
Custom-named patches use the nearest standard patch by decay time, reflection
delay, HF level and late level. Silent patches and rooms without reverb stay
dry. Every mapping is a `SOUND_ROOM_REVERB` warning and in the bridge report's
`ambient` entry. Room dry/wet values are the source values.

Alias sends are calibrated to BO2's convention, measured on every build
(`t6bridge.measure_reverb_send`). WaW sends feed I3DL2 patches that are
already 5-30 dB down, while radverbs return near unity, so BO2 designers send
far less. The converter compares nonzero sends of the stock BO2 zombies banks
(mod tools `raw/soundbank/zmb_*.all.aliases.csv`) with those of the stock WaW
`nazi_zombie*` zones (extracted once into the shared asset cache), per BO2
volume group the converter assigns from an identified WaW bus role (weapon,
voice, ambience, music, UI; at least `REVERB_MIN_SAMPLES` on each side). Each
alias gets its group's offset; other groups get the median of those offsets
weighted by sample count. On the stock games (2026-10-15): weapon -24.0 dB,
voice -26.1 dB, ambience -34.0 dB, overall -26.1 dB. Without either side's
data the last measurement `REVERB_SEND_DB` (-24 dB) is used and reported as
`SOUND_REVERB_SEND unmeasured`. The result is in the bridge report
(`reverb_send`) and `sounds.bank.json`. Uncalibrated WaW sends, with the map's
rooms undeclared, made weapons and voices echo in every room. Aliases with
WaW's `noWetLevel` flag send nothing. Dry gains are unchanged.

Falloff curves: BO2 build output names an approximated curve only when its
loudness error exceeds `AUDIBLE_CURVE_DB` (3 dB RMS); the rest are summarized
in one `SOUND_CURVES` warning. `sounds.curves.json` lists every binding.
Rescaling alias distances does not improve any stock fit (measured on Shi No
Numa), so curves keep their source distances.

## Default reverb

WaW's stock `DEFAULT` I3DL2 reverb patch is silent (-10000 millibels for
room, reflections, and reverb). BO2's `default` RAD preset has audible
reflections. Without a declared room, a converted map inherited that BO2
effect on all aliases with nonzero sends, particularly gunfire after the
linear gain correction. The converter now reads the staged WaW driver and,
when its default is silent, declares a default ambient room with dry gain 1
and wet gain 0. It also selects that mix at client startup. The normal ambient
room controller owns subsequent room changes; alias sends, source PCM, and
loaded weapon allocation are unchanged. Missing or audible custom source
defaults are reported and are never assumed silent. Explicit WaW room presets
still require I3DL2-to-RAD DSP translation; this fixes the baseline rather
than claiming complete room acoustics conversion. This baseline applies only to maps without a
source `_amb.csc`; maps with one use its startup room (see above).

WaW sound aliases retain their original audio, distance ranges, and four
dry/wet falloff curves in the converter's sound IR. BO2 rejects a second
`snddriverglobals` asset, so the converter binds against curves in the stock
BO2 driver's `.w2bsdg` sidecar.

Exact shape matches take precedence. With `--approximate-sound-curves` (enabled
by `tools/run_bridge.ps1`), unmatched curves use the stock shape with the lowest
RMS loudness error over normalized distance. The comparison uses 256 midpoint
samples and a -60 dB floor. If the source fades smoothly to silence, the
approximation prefers curves that also fade smoothly rather than hold a
nonzero gain until a terminal step. Source minimum and maximum distances are
preserved. Normalizing distance between those endpoints remains an engine
compatibility assumption, rather than a measured guarantee of identical
attenuation. `sounds.curves.json` reports both maximum linear gain error and
RMS dB error; strict mode still rejects unmatched curves.

BO2 alias CSV volume fields use dB SPL, not percentages. The converter writes
`100 + 20 * log10(source_gain)` for volume, reverb, center, and envelope gain,
with zero encoded as CSV zero. Fractional dB values are preserved. For example,
WaW gain 0.5 becomes approximately 93.9794 dB SPL; writing 50 would produce
gain 0.00316. The native loader quantizes gains to 16 bits.

The original WaW bus `volumeMod` multiplies the alias volume before dB
conversion. First-person weapon buses use the first-person BO2 duck group.
Aliases referenced by converted weapons share BO2's weapon volume group,
including custom aliases authored on WaW's `full_vol` bus and reload/notetrack
sounds. This avoids category-dependent gain differences within weapon audio;
BO2's broader driver routing and ducking remain approximations.

Loaded-bank budgeting prioritizes the actual weapon dependency graph before
other loaded sounds. Weapon clips converted to streams can compete for
streaming playback resources during rapid firing. The current map now keeps
all 429 available weapon variants (317 unique files) loaded, compared with
175 loaded / 253 streamed variants before this change. The allocation retains
the existing 392-file budget and uses about 35 MB of its 58 MB byte allowance.

The native XWMA bridge parses only bytes inside the RIFF container. WaW dumps
can carry additional trailing data; treating that trailer as RIFF chunks
incorrectly rejected valid files. The fix recovers 36 decoded files and 104
alias variants. Decoding a real fixture with and without its trailer produces
identical native PCM and matches the source decoded packet counts.

Alias and entity voice limits preserve WaW's counts, including zero, and its
`none`, `oldest`, `reject`, and `priority` policies. WaW's additional `softest`
policy uses BO2's `priority` policy and is recorded per variant in
`sounds.bank.json`. Unknown policies are reported as conversion errors.

Verification for this change:

- 23 sound tests, 5 audio tests, and 3 XWMA tests pass.
- 32 weapon variants compile and extract with their selected curves, loaded
  storage, categories, and voice limits intact; linear gain error is below
  2/65535.
- Evidence is in `work/sound_curve_fix/conversion_summary.json` and
  `work/sound_curve_fix/native_roundtrip.json`.
- Updated playback allocation and native gain verification are recorded in
  `work/sound_playback_fix/conversion_summary.json` and
  `work/sound_playback_fix/native_mix_roundtrip.json`.

The current conversion still reports missing PCM and secondary aliases. Its
full native bank build also warns about two non-48 kHz loaded death-music
clips. This change does not establish that every missing sound or playback
interruption is resolved. The latest 4,014-variant bank was rebuilt and
installed after the game closed, retaining the revive-waypoint and
teleporter boundary fixes. All nine packaged files match the build by
SHA-256; the rebuilt gameplay fastfile passed its 67,090-argument material
audit with zero violations. Installation evidence is in
`work/sound_playback_fix/installed_build.json`. In-game playback remains
unverified.

## Which aliases are converted

A WaW zone file pulls whole alias CSVs, so a map's fastfile typically defines
thousands of aliases it never plays: other maps' content, weapons the map does
not carry, and sounds only WaW's engine requests by name (`step_*`,
`bullet_*`, `land_*`, `bodyfall_*`), which BO2's engine never asks for. The
zone's aliases are therefore candidates, not dependencies. An alias is
converted when something in the port can play it:

- the map's weapons (fields, notetrack maps, grenade bounce surfaces) and FX;
- a string literal in any ported server or client script (`.gsc`/`.csc`),
  or a cell of a string table whose path a script names;
- a map entity key/value (e.g. a perk machine's `script_sound` jingle);
- a name scripts build at runtime (`"plr_" + index + "_vox_" + category`):
  a literal joined with `+` occurs in the alias, and every non-numeric word of
  the alias occurs in some script literal;
- the secondary and chain aliases of any of the above.

Converted scripts reach WaW aliases only through `waw_sound`, which reports a
missing alias once (`SOUND <alias>`) instead of playing a substitute. The
aliases left out are listed in `content_source/sounds.unreferenced.json`, and
the bridge report gives their count under `unreferenced_sound_aliases`.
