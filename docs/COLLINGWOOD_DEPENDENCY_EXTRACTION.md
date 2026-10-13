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

## Project X corroborating report

The later `zm_projectx_waw-failure-1791927340921385100.zip` also reports v0.2.14
stopping during script/animation staging at the same `pby_fly.ff` dependency,
with the same `0xC0000409` exit after two retries. This is separate from the
earlier Project X localization conflict: this build never reaches that stage.

Its native log contains failed opens for numerous unrelated merchant-ship and
character model exports, then `images/glass_c.dds`, before the abort. The output
folder is already the shallow cache staging folder, so the evidence does not
justify asserting that deep cache paths caused these particular failures. The
OS reason for the failed opens is not included in the native log.

Both reports exercise the old bulk dependency export, not the new typed
resolver in commit `0ee164c`. They should be retested with a build containing
that change. The additional report supports sharing the mitigation across maps;
it does not establish successful full builds or the native abort's internal cause.
