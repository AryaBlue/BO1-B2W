"""Full-frame lobby map preview, scoped by a per-project frontend stringtable.

Stock ZM draws the lobby preview (CoD.MapInfoImage.mapImage) 294 x 136 and
leaves the 46-unit strip below it to the frame's dark gradient behind the map
name. Converted maps register in zm/waw_menu_preview.csv; a compiled wrapper
around the installed game's ui/t6/mapinfoimage.lua extends their picture
under that strip, so the whole 294 x 182 frame shows it."""
from pathlib import Path
import csv
import hashlib
import io
import json

RUNTIME = 'ui/t6/mapinfoimage.lua'
BASE = 'ui/t6/waw_mapinfoimage_base.lua'
TABLE = 'zm/waw_menu_preview.csv'
# Width / height of the full stock ZM frame (MapImageWidth x MapImageHeight + 46).
ASPECT = 294 / 182


def clear_runtime(root: Path, metadata: dict) -> None:
    if metadata.get('preview_layout') == 'full':
        for name in (RUNTIME, BASE, TABLE):
            (root / name).unlink(missing_ok=True)


def compiled_wrapper(name: str, stock: bytes) -> bytes:
    """Checked-in hksc bytecode for compat/<name>.lua, verified against its
    manifest and against the installed game's Lua VM header."""
    compiled = Path(__file__).parent / f'compat/{name}.luac'
    manifest = json.loads(compiled.with_suffix('.json').read_text())
    for file, key in ((compiled, 'bytecode_sha256'), (compiled.with_suffix('.lua'), 'source_sha256')):
        if hashlib.sha256(file.read_bytes()).hexdigest() != manifest[key]:
            raise ValueError(f'{name} source/bytecode mismatch; rebuild with tools/compile_menu_layers.py.')
    wrapper = compiled.read_bytes()
    if wrapper[:16] != stock[:16]:
        raise ValueError('Stock menu bytecode uses an unsupported T6 VM format.')
    return wrapper


def stage_runtime(bo2: Path, root: Path, project: str) -> dict:
    original = bo2 / 'raw' / RUNTIME
    bytecode = original.read_bytes()
    if not bytecode.startswith(b'\x1bLua'):
        raise ValueError(f'Expected stock compiled T6 menu: {original}')
    wrapper = compiled_wrapper('menu_preview', bytecode)
    target = root / RUNTIME
    target.parent.mkdir(parents=True, exist_ok=True)
    (root / BASE).write_bytes(bytecode)
    target.write_bytes(wrapper)
    rows = io.StringIO(newline='')
    csv.writer(rows, lineterminator='\n').writerow([project])
    (root / TABLE).parent.mkdir(parents=True, exist_ok=True)
    (root / TABLE).write_text(rows.getvalue(), encoding='utf-8')
    return {'preview_layout': 'full', 'preview_rawfiles': [BASE, RUNTIME]}
