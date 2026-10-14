"""Repair the stock T6 overheat HUD without changing weapon heat semantics."""
from pathlib import Path
import json
from .progress import captured
from . import weapons

HUD = 'ui_mp/t6/zombie/otherammocounters.lua'


def repair_bytecode(data: bytes) -> bytes:
    # Both misspelled constants have the same length as their replacements.
    # Preserve the stock Lua bytecode, offsets, instructions and debug data.
    if not data.startswith(b'\x1bLua'):
        raise ValueError('overheat HUD is not compiled Lua')
    for old, new in ((b'beingAnimation\0', b'beginAnimation\0'),
                     (b'pluse_low\0', b'pulse_low\0')):
        if data.count(old) != 1:
            raise ValueError(f'unrecognized stock overheat HUD constant: {old!r}')
        data = data.replace(old, new)
    return data


def stage(bo2: Path, project: Path, work: Path, unlinker: Path) -> list[str]:
    runtime = project / 'content_source/weapons.runtime.json'
    if not runtime.is_file():
        return []
    names = json.loads(runtime.read_text()).get('weapons', [])
    if not any(weapons.read_info_file(project / 'content_source/weapons' / name).get('overheatWeapon') == '1'
               for name in names if (project / 'content_source/weapons' / name).is_file()):
        return []
    dump = work.resolve() / 'overheat_hud_stock'
    dump.mkdir(parents=True, exist_ok=True)
    proc = captured([str(unlinker.resolve()), '--no-color', '--include-assets', 'rawfile',
                     '--output-folder', str(dump), str(bo2 / 'zone/all/patch_zm.ff')],
                    capture_output=True, text=True, errors='replace')
    (dump / 'extract.log').write_text(proc.stdout + proc.stderr)
    source = dump / HUD
    if proc.returncode or not source.is_file():
        raise RuntimeError(f'cannot extract stock overheat HUD; see {dump / "extract.log"}')
    target = project / HUD
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(repair_bytecode(source.read_bytes()))
    return [f'rawfile,{HUD}']
