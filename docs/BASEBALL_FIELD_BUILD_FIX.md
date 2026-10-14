# Baseball Field stock framework detection (2026-10-13)

The failure bundle `zm_bbf_waw-failure-1791938234155427700.zip` stops during
script staging with `player_damage_override prelude applies damage itself;
not ported`. This is a framework classification error, not a native compiler
failure.

The merged WaW stock cache selects one script definition per path. Its selected
`maps/_zombiemode.gsc` is an older stock release whose damage override starts
with the nonlethal-health branch. Baseball Field uses the later stock body from
Der Riese, including attacker handling and the terminal 75-point explosive
damage branch. Comparing only the merged definition incorrectly labels that
stock prefix as custom damage logic.

`Sources` now includes original stock-zone folders recorded in the verified
cache's `catalog.json` when comparing framework versions. Asset and map script
lookup priority stays unchanged; these folders supply comparison variants.
The newer stock damage body is recognized, so BO2 retains ownership of standard
damage handling. No duplicate source attacker handling or damage callback is
registered. Unsupported authored damage applications remain rejected.

Regression coverage reproduces the old failure, recognizes a newer catalogued
stock body despite map-local formatting, and verifies that a genuine authored
rule before that stock body still becomes a callback. A separate check with
the actual Baseball Field IWD reproduces the exact submitted error against the
old merged-only comparison and reports no error with the corrected discovery.

## Validation

- 522 tests pass.
- The locally available Baseball Field source completes full map and gameplay
  linking with zero distinct missing assets.
- All 112 compiled server/client scripts match byte for byte after extracting
  the final map fastfile. The generated core has no duplicate stock damage prelude.
- Native material audits check 30,294 map and 43,373 gameplay arguments with zero
  violations or missing technique sets.
- All 5,000 authored bone hitboxes across 125 models match after native linking.

Evidence and the verified standalone package are under
`work/baseball_field_build_fix`. No map was installed, and gameplay has not
been tested. The branch is `codex/baseball-field-build-fix`.
