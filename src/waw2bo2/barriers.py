"""Align native animated barricades with authored WaW plank planes."""
import json
import math
import struct
from pathlib import Path


def repaired_translation(path: Path) -> tuple[float, float, float]:
    """Final root translation of the measured T6 basic-board repair format.

    Raw v19: header, empty delta quaternion, indexed compressed delta
    translation. Reject other contracts instead of guessing a fixed offset.
    See OAT's CompiledXAnimLoader::LoadDeltaTransTrack.
    """
    data = path.read_bytes()
    version, frames, bones, flags, kind, fps = struct.unpack_from('<3H2BH', data)
    if version != 19 or flags != 2 or not bones or not fps:
        raise ValueError(f'{path}: unsupported barricade repair animation header')
    if struct.unpack_from('<H', data, 10)[0] != 0:
        raise ValueError(f'{path}: barricade repair has an unsupported delta rotation')
    count = struct.unpack_from('<H', data, 12)[0]
    offset = 14
    if count == 1:
        return struct.unpack_from('<3f', data, offset)
    if count < 2:
        raise ValueError(f'{path}: barricade repair has no root translation')
    # Non-looping animation has frames keys, numbered 0 through frames-1.
    if count < frames:
        size = 1 if frames <= 256 else 2
        indices = struct.unpack_from('<' + ('B' if size == 1 else 'H') * count, data, offset)
        offset += count * size
        if indices[-1] != frames - 1:
            raise ValueError(f'{path}: barricade repair omits its final frame')
    small = data[offset]
    if small not in (0, 1):
        raise ValueError(f'{path}: invalid compressed translation flag')
    mins = struct.unpack_from('<3f', data, offset + 1)
    ranges = struct.unpack_from('<3f', data, offset + 13)
    width, maximum = (1, 255) if small else (2, 65535)
    values = struct.unpack_from('<3' + ('B' if small else 'H'), data,
                                offset + 25 + (count - 1) * 3 * width)
    result = tuple(mins[k] + ranges[k] * values[k] / maximum for k in range(3))
    if not all(math.isfinite(x) for x in result):
        raise ValueError(f'{path}: non-finite repaired translation')
    return result


def align_native_boards(bsp: Path, bo2: Path) -> dict:
    """Keep attack slots outside while matching the source boards' depth.

    T6 places its attack slots at the zbarrier origin, but its repair animation
    advances the boards about thirty units. The source entry struct is the
    repair trigger, not the animated barrier's root.
    """
    path = bsp / 'entities.json'
    data = json.loads(path.read_text())
    es = data['entities']
    poses, aligned, warnings = {}, [], []
    for goal in es:
        if goal.get('targetname') != 'exterior_goal' or not goal.get('target'):
            continue
        group = [e for e in es if e.get('targetname') == goal['target']]
        native = [e for e in group if e.get('classname') == 'zbarrier_zmcore_BasicWoodBarrier']
        boards = [e for e in group if e.get('classname') == 'script_brushmodel'
                  and e.get('script_noteworthy', '').isdigit()]
        if len(native) != 1 or not boards:
            continue
        origin = tuple(float(x) for x in goal.get('origin', '0 0 0').split())
        pitch, yaw, _ = [math.radians(float(x)) for x in goal.get('angles', '0 0 0').split()]
        forward = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), -math.sin(pitch))
        depths = [sum((float(x) - origin[k]) * forward[k]
                      for k, x in enumerate(board['origin'].split())) for board in boards]
        names = [native[0][f'zbarrierboardanim{i}'] for i in range(1, int(native[0]['zbarriernumboards']) + 1)]
        for name in names:
            if name not in poses:
                poses[name] = repaired_translation(bo2 / 'raw/xanim' / name)
        source_depth = sum(depths) / len(depths)
        native_depth = sum(poses[name][0] for name in names) / len(names)
        shift = source_depth - native_depth
        native[0]['origin'] = ' '.join(f'{origin[k] + forward[k] * shift:.9g}' for k in range(3))
        native[0]['angles'] = goal.get('angles', '0 0 0')
        aligned.append({'target': goal['target'], 'source_depth': source_depth,
                        'native_repaired_depth': native_depth, 'root_advance': shift})
    path.write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8')
    return {'aligned': aligned, 'repair_poses': poses, 'warnings': warnings}
