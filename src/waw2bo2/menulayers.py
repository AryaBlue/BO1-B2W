"""Full-canvas menu layers, scoped by a per-project frontend stringtable."""
from pathlib import Path
import csv
import io
import hashlib
import json

RUNTIME = 'ui_mp/t6/zombie/gamemapzombie.lua'
BASE = 'ui_mp/t6/zombie/waw_gamemap_base.lua'
TABLE = 'zm/waw_menu_layers.csv'


def clear_runtime(root: Path, metadata: dict) -> None:
    if metadata.get('layer_layout') == 'aligned':
        for name in (RUNTIME, BASE, TABLE):
            (root / name).unlink(missing_ok=True)


def stage_runtime(bo2: Path, root: Path, project: str) -> dict:
    original = bo2 / 'raw' / RUNTIME
    bytecode = original.read_bytes()
    if not bytecode.startswith(b'\x1bLua'):
        raise ValueError(f'Expected stock compiled T6 menu: {original}')
    compiled = Path(__file__).parent / 'compat/menu_layers.luac'
    manifest = json.loads(compiled.with_suffix('.json').read_text())
    for file, key in ((compiled, 'bytecode_sha256'), (compiled.with_suffix('.lua'), 'source_sha256')):
        if hashlib.sha256(file.read_bytes()).hexdigest() != manifest[key]:
            raise ValueError('Menu layer source/bytecode mismatch; rebuild with tools/compile_menu_layers.py.')
    wrapper = compiled.read_bytes()
    if wrapper[:16] != bytecode[:16]:
        raise ValueError('Stock menu bytecode uses an unsupported T6 VM format.')
    target = root / RUNTIME
    target.parent.mkdir(parents=True, exist_ok=True)
    (root / BASE).write_bytes(bytecode)
    target.write_bytes(wrapper)
    rows = io.StringIO(newline='')
    csv.writer(rows, lineterminator='\n').writerow([project, f'menu_{project}_blit'])
    (root / TABLE).parent.mkdir(parents=True, exist_ok=True)
    (root / TABLE).write_text(rows.getvalue(), encoding='utf-8')
    return {'layer_layout': 'aligned', 'layer_rawfiles': [BASE, RUNTIME],
            'layer_materials': [f'menu_{project}_blit'], 'blit': f'menu_{project}_loc'}
