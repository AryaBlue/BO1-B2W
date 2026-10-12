"""Validate authored bone-space hitboxes after native T6 linking."""
from __future__ import annotations

import json
import math
from pathlib import Path


def has_authored_hitboxes(source: Path) -> bool:
    return any(model.get('boneInfo') and model.get('type') in ('animated', 'viewhands')
               for path in (source / 'xmodel').rglob('*.json')
               for model in [json.loads(path.read_text())])


def audit(source: Path, built: Path) -> dict:
    models = bones = 0
    errors = []
    for path in sorted((source / 'xmodel').rglob('*.json')):
        original = json.loads(path.read_text())
        if not original.get('boneInfo') or original.get('type') not in ('animated', 'viewhands'):
            continue
        target = built / path.relative_to(source)
        if not target.is_file():
            continue
        models += 1
        actual = {bone['bone']: bone for bone in json.loads(target.read_text()).get('boneInfo', [])}
        for expected in original['boneInfo']:
            name = expected['bone']
            if name not in actual:
                errors.append(f'{path.stem}: missing hitbox bone {name}')
                continue
            bones += 1
            if expected.get('hitloc') is not None and actual[name].get('hitloc') != expected['hitloc']:
                errors.append(f'{path.stem}: {name} hit location changed: {expected["hitloc"]} -> {actual[name].get("hitloc")}')
            for key in ('mins', 'maxs', 'offset', 'radiusSquared'):
                left, right = expected[key], actual[name][key]
                left = left if isinstance(left, list) else [left]
                right = right if isinstance(right, list) else [right]
                if len(left) != len(right) or any(not math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)
                                                  for a, b in zip(left, right)):
                    errors.append(f'{path.stem}: {name} {key} changed: {left} -> {right}')
    return {'models': models, 'bones': bones, 'errors': errors}
