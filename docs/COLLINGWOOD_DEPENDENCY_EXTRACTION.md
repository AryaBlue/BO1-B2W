# Collingwood dependency extraction (2026-10-13)

The supplied `zm_cph_waw` failure bundle records a v0.2.14 build stopping during
script/animation staging. A stock dependency export of `pby_fly.ff` exits with
`0xC0000409` after two retries. Its native log is empty. The bundle contains
logs and asset lists, not the map source; the user confirmed the source is not
available on this computer.

## Resolver defect and change

A typed lookup against a compact stock cache previously expanded the zone to
all conversion asset types. An animation lookup therefore exported unrelated
campaign images, models, effects and audio. The resolver also treated any cache
containing materials as complete for every asset kind, regardless of the receipt.

The prepared-cache resolver now requests the lookup's asset types together with
the types already extracted. Further lookups expand that set as needed. It
records the actual native extraction receipt, reuses satisfied lookups, and
retains the previously published generation if an expansion fails. Untyped
callers still request the full legacy dependency set. There is no map-name
exception, dropped required asset, substituted animation, or suppressed error.

This removes the unnecessary bulk-export path reached by dependency discovery.
It is a targeted mitigation of the reported build failure, not proof of the
native crash's internal cause. Both the current extractor and the v0.2.14
packaged extractor completed a bulk export of this computer's `pby_fly.ff`;
the supplied crash was not reproduced locally. Bulk image export also logs an
unsupported IWI format 9; this is not established as the cause of that crash.

## Validation

- 520 tests pass. New cases cover incremental typed extraction, material caches
  not masking missing images, repeated lookup reuse, and failure preserving the
  published cache.
- The actual v0.2.14 packaged T4 extractor successfully exports `rawfile,xanim`
  through the changed resolver: 301 animation files and 357 files total.
- The recovered set includes `viewmodel_panzerschreck_idle`,
  `viewmodel_panzerschreck_fire` and `viewmodel_panzerschreck_reload`, named in the
  bundle's Collingwood asset list. No image/model/material/audio files are
  exported for this animation request, and a second request reuses the cache.
- Local evidence is under `work/collingwood_regression`, including
  `validation.json`, native logs and test output.

A full Collingwood build remains unverified because its source is unavailable.
The next check is a rebuild on the source machine with this converter change;
if it still fails, retain the new log's requested asset-type list and native log.
