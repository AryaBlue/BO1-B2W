"""Desktop build pipeline using shared Extract All caches."""
from __future__ import annotations

from pathlib import Path
from contextlib import ExitStack
import json
import shutil
import struct
import subprocess

from . import all2raw, modelhitboxes, progress, stagecache
from .launcher import BuildPaths, Settings, cli_command
from .resources import resource_root


def _dump_token(folder: Path):
    """A content identity for an extracted/dumped source folder.

    Prefers the extraction receipt's ``inputs`` (source stamp + tool digest +
    dependencies + asset selection -- a complete description of the dump's
    content); falls back to the content-addressed folder name when no receipt
    is present (e.g. a merged stock view)."""
    folder = Path(folder)
    try:
        data = json.loads((folder / 'extraction.json').read_text(encoding='utf-8'))
        if data.get('inputs') is not None:
            return {'inputs': data['inputs']}
    except (OSError, ValueError):
        pass
    return {'name': folder.name, 'exists': folder.exists()}


def staging_inputs(settings: Settings, sources: dict, wawraw: Path, stock: Path,
                   args: list[str]) -> dict:
    """Everything the ``stage-bridge`` step's output depends on.

    Conservative on purpose: extra inputs only cause harmless cache misses,
    whereas a missing input would restore a stale build. ``args`` already
    carries the map world, option flags and every source path the step reads."""
    return {
        'sources': {role: _dump_token(Path(p)) for role, p in sorted(sources.items())},
        'wawraw': _dump_token(wawraw),
        'stock': _dump_token(stock),
        'flags': {'bo2_stock_perks': settings.bo2_stock_perks, 'remaster': settings.remaster,
                  'source_fx': settings.source_fx, 'project': settings.project},
        'tools': {'t4': all2raw.digest(Path(settings.t4) / 'Unlinker.exe'),
                  't6': all2raw.digest(Path(settings.t6) / 'Unlinker.exe')},
        'args': list(args),
    }


def run(command: list[str], log: Path | None = None) -> None:
    if log is None:
        result = subprocess.run(command, check=False)
    else:
        log.parent.mkdir(parents=True, exist_ok=True)
        result = progress.native(command, log)
    if result.returncode:
        if log is not None:
            print(log.read_text(encoding='utf-8', errors='replace')[-8000:], flush=True)
        raise RuntimeError(f'{Path(command[0]).name} failed ({result.returncode})' +
                           (f'; see {log}' if log else ''))


def world_name(dump: Path, stem: str) -> str:
    """The map's world name in its dumped zone. Usually the fastfile's name;
    a map shipped only as mod.ff (or renamed) carries its world under the
    map's real name (maps/<name>.d3dbsp)."""
    maps = dump / 'waw2bo2/maps'
    if (maps / f'{stem}.d3dbsp.gfx.bin').is_file():
        return stem
    worlds = sorted(p.name.removesuffix('.d3dbsp.gfx.bin') for p in maps.glob('*.d3dbsp.gfx.bin'))
    if len(worlds) == 1:
        print(f'== map world "{worlds[0]}" found in {stem}.ff', flush=True)
        return worlds[0]
    if worlds:
        raise RuntimeError(f'{stem}.ff holds several map worlds ({", ".join(worlds)}); choose that map\'s own fastfile')
    return stem     # no world dumped: staging reports the missing world files


def ensure_laa(linker: Path) -> None:
    data = bytearray(linker.read_bytes())
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError(f'Not a PE executable: {linker}')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        raise ValueError(f'Invalid PE header: {linker}')
    flags = struct.unpack_from('<H', data, pe + 22)[0]
    if not flags & 0x20:
        struct.pack_into('<H', data, pe + 22, flags | 0x20)
        linker.write_bytes(data)


def build(settings: Settings, *, redump: bool = False, root: Path | None = None,
          cache_paths: all2raw.CachePaths | None = None) -> int:
    caches = cache_paths or all2raw.CachePaths.for_settings(settings)
    # Prepare only missing/stale caches before acquiring the read locks.
    # prepare() owns the extraction lock itself and resumes cached zones.
    for game, tool, cache, engine in (
            (Path(settings.waw), Path(settings.t4) / 'Unlinker.exe', caches.waw, all2raw.source_engine(settings.waw)),
            (Path(settings.bo2), Path(settings.t6) / 'Unlinker.exe', caches.bo2, 'T6')):
        try:
            all2raw.ready(game, tool, cache, engine=engine)
        except RuntimeError:
            print(f'== 1. preparing {engine} shared game assets automatically', flush=True)
            all2raw.prepare(game, tool, cache, engine=engine)
    # Extraction may prune old generations. Protect the stock view while a
    # build reads it; dependency extraction locks its own separate folders.
    with ExitStack() as locks:
        for cache in sorted({caches.waw, caches.bo2}, key=str):
            locks.enter_context(all2raw.cache_lock(cache))
        return _build(settings, redump=redump, root=root, cache_paths=caches)


def _build(settings: Settings, *, redump: bool = False, root: Path | None = None,
           cache_paths: all2raw.CachePaths | None = None) -> int:
    import os
    os.environ['WAW2BO2_VERBOSE'] = '1' if settings.verbose else '0'
    paths = BuildPaths.for_settings(settings)
    if root is not None:
        root = root.resolve()
        paths = BuildPaths(root, root / 'stage', paths.stock, root / 'waw_dumps',
                           root / 'mod_build', root / 'package')
    caches = cache_paths or all2raw.CachePaths.for_settings(settings)
    waw, bo2 = Path(settings.waw), Path(settings.bo2)
    t4 = Path(settings.t4) / 'Unlinker.exe'
    t6 = Path(settings.t6) / 'Unlinker.exe'
    # Builds never extract or list a stock FF. Extract All owns every static
    # asset, index, sound driver and API cache.
    wawraw = all2raw.ready(waw, t4, caches.waw, engine=all2raw.source_engine(waw))
    stock = all2raw.ready(bo2, t6, caches.bo2, engine='T6')
    stage, mod = paths.stage, paths.mod
    # Stage in the worker as well: standalone CLI and Wine builds do not
    # necessarily share the launcher's filesystem or its pre-staged metadata.
    from .menuart import stage_art
    stage_art(settings, stage / 'zone_raw' / settings.project)
    for folder in (stage, mod):
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stock / 't6api_cache.json', stage / 't6api_cache.json')
    print('== 0. reusing shared game assets and preparing cached map sources', flush=True)
    sources = progress.timed('step 0 extract map sources', all2raw.source_dumps, settings, caches, refresh=redump)
    source = Path(settings.fastfile).resolve()
    project = settings.project
    mapraw = sources['map']
    mapzone = world_name(mapraw, source.stem)
    roots = [str(p) for p in sources.values()] + [str(wawraw)]
    extra = [arg for path in roots for arg in ('--extra-root', path)]
    linker = Path(settings.t6) / 'Linker.exe'
    print('== 1. using pre-extracted stock assets (no stock dumping)', flush=True)
    print(f'== 2. staging {project}', flush=True)
    args = ['stage-bridge', str(stage), project,
            '--gfx', str(mapraw / 'waw2bo2/maps' / (mapzone + '.d3dbsp.gfx.bin')),
            '--clip', str(mapraw / 'waw2bo2/maps' / (mapzone + '.d3dbsp.clip.bin')), *extra,
            '--iwd-dir', str(source.parent), '--iwd-dir', str(waw / 'main'),
            '--waw-map-script', str(mapraw / 'maps' / (mapzone + '.gsc')),
            '--waw-script-root', str(sources.get('mod', mapraw)), '--waw-stock-scripts', str(wawraw),
            '--t6-unlinker', str(t6), '--waw-root', str(waw), '--t4-unlinker', str(t4),
            '--waw-stock-dumps', str(caches.waw), '--xwma-decoder', settings.decoder,
            '--approximate-sound-curves', '--stock-materials', str(stock / 'materials'),
            '--techset-dump', str(stock), '--bo2', str(bo2),
            '--script-template', str(stage / 'zone_raw/bridge'), '--script-template-name', 'bridge']
    if settings.bo2_stock_perks:
        args += ['--bo2-stock-perks']
    if settings.remaster:
        args += ['--remaster-bo2-materials']
    if 'patch' in sources:
        # WaW loads <map>_patch.ff after the map zone: its scripts win
        args += ['--waw-patch-script-root', str(sources['patch'])]
    if source.parent.is_relative_to((waw / 'zone').resolve()):
        # a retail WaW level: stock_map_policies apply (never to custom maps)
        args += ['--waw-stock-map']
    if settings.source_fx:
        args += ['--waw-mod-tools', settings.waw_tools, '--waw-source-fx',
                 '--waw-source-dumps', str(caches.waw / 'source')]
    # WAW2BO2_FROM_STEP resumes a build whose earlier steps' output is unchanged (BO1 bring-up)
    steps = ['stage', 'build-mod', 'compile-scripts', 'bridge-link', 'audit']
    first = steps.index(os.environ.get('WAW2BO2_FROM_STEP') or 'stage')
    if first <= 0:
        # Opt-in per-map cache (WAW2BO2_STAGE_CACHE): an identical rebuild of the
        # same map restores staging's output instead of recomputing it. Off by
        # default; see stagecache.py for the correctness contract.
        cache = stagecache.StageCache(caches.waw.parent / 'stage_cache') if stagecache.enabled() else None
        token = cache.token(staging_inputs(settings, sources, wawraw, stock, args)) if cache else None
        if cache is not None and cache.lookup(token) is not None:
            print('== 2. restoring staged content from cache (identical inputs)', flush=True)
            cache.restore(token, stage)
        else:
            before = stagecache.snapshot(stage) if cache is not None else None
            run(cli_command(*args))
            if cache is not None:
                files = stagecache.changed(before, stagecache.snapshot(stage))
                if cache.store(token, stage, files, meta={'project': project}):
                    print(f'== cached staged content ({len(files)} files) for identical rebuilds', flush=True)
    else:
        print(f'== resuming at {steps[first]} (earlier steps reused)', flush=True)
    ensure_laa(linker)
    print('== 3a. linking gameplay mod.ff with the BO2 mod tools linker', flush=True)
    if first <= 1:
        progress.timed('step 3a build mod.ff (BO2 linker)', run,
                       cli_command('build-mod', str(stage), project, '--bo2', str(bo2), '--work', str(mod),
                                   '--unlinker', str(t6), '--linker', str(linker), '--techset-dump', str(stock)))
    print('== 3b. compiling map scripts with the BO2 mod tools linker', flush=True)
    if first <= 2:
        progress.timed('step 3b compile scripts (BO2 linker)', run,
                       cli_command('compile-scripts', str(stage), project, '--bo2', str(bo2), '--unlinker', str(t6)))
    print(f'== 4. linking {project} with the T6 bridge', flush=True)
    if first <= 3:
        progress.timed('step 4 bridge-link (T6 linker)', run,
                       cli_command('bridge-link', str(stage), project, '--linker', str(linker),
                                   '--techset-dump', str(stock), '--log', str(stage / (project + '_bridge.log'))))
    print('== 5. auditing server/client clientfields', flush=True)
    from . import clientfields
    report = clientfields.audit(stage / 'zone_raw' / project, project, bo2)
    findings = clientfields.write_report(report, stage)
    for finding in findings:
        print('WARNING clientfield', finding, flush=True)
    print(f'{len(report["fields"]["server"])} server / {len(report["fields"]["client"])} client clientfields, '
          f'{len(findings)} likely mismatches; see {stage / "clientfield_audit.txt"}', flush=True)
    print('== 6. auditing built material arguments', flush=True)
    for ff in (stage / 'zone_out' / project / (project + '.ff'), mod / 'out/mod.ff'):
        if not ff.is_file():
            raise FileNotFoundError(f'Linker did not create {ff}')
        audit = stage / ('audit_' + ff.stem)
        if not audit.resolve().is_relative_to(stage.resolve()):
            raise ValueError(f'Audit cleanup target is outside staging: {audit}')
        if audit.exists():
            shutil.rmtree(audit)
        model_source = stage / 'zone_raw' / project
        audit_hitboxes = ff.stem == project and modelhitboxes.has_authored_hitboxes(model_source)
        run([str(t6), '--no-color', '--search-path', str(bo2 / 'zone/all'), '--include-assets',
             'material,techniqueset' + (',xmodel' if audit_hitboxes else ''),
             '--output-folder', str(audit), str(ff)], stage / (audit.name + '.log'))
        from .launcher import python_command
        run(python_command() + [str(resource_root() / 'tools/audit_material_args.py'), str(audit), str(stock)])
        if audit_hitboxes:
            result = modelhitboxes.audit(model_source, audit)
            (stage / 'bone_hitbox_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            if result['errors'] or not result['models']:
                raise RuntimeError('Authored bone hitboxes changed during linking; see bone_hitbox_audit.json')
            print(f'{result["bones"]} authored bone hitboxes checked across {result["models"]} models, 0 violations', flush=True)
    return 0
