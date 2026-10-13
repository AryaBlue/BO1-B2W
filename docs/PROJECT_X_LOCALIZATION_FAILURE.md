# Project X localization staging failure

The supplied `zm_projectx_waw-failure-1791908519317749700.zip` reports a
localization-stage failure in converter 0.2.14:
`ValueError: conflicting localization reference MUT_11_DESC`.
Staging stops before native script compilation and linking. The bundle contains
logs and weapon reports, but no map fastfiles or localization source files;
the offending source file and its actual text cannot be identified from it.

`localization.parse` previously raised when one StringEd file defined a key
twice with different text. It now retains the later definition within that
file. This matches the native asset pool's replacement of an existing name
(`AssetPoolDynamic::AddAsset`, `m_asset_lookup[normalizedName] = pAssetInfo`).
The explicit priority across files is unchanged: source zones/IWDs, then stock
WaW and raw sources, then eligible BO2 fallback text.

Conflicts are recorded in `content_source/localization.stage.json` with source,
line numbers, previous text and selected text, and produce
`LOCALIZATION_CONFLICT` warnings. Equal repeated values need no warning.
Repeated reads of the same file do not duplicate diagnostics. Generated output
contains one definition per resolved key.

Validation: 515 tests pass, including conflicting IWD text, zone priority,
unused fallback conflicts, language selection, placeholders and repeated
staging. A synthetic fixture using the reported key stages successfully,
links with the native T6 linker and round-trips its selected localized text
exactly. Evidence: `work/project_x_build_fix/verification.json`, `tests.log`,
`link.log`, `unlink.log` and `roundtrip/`.

Project X itself has **not** been rebuilt: the user confirmed its source is
unavailable on this computer. The reported blocker is fixed; later build
stages and gameplay remain unverified for this map.
