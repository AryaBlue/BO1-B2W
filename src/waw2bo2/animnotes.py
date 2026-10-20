"""Adapt raw v17 weapon sound notifications without changing motion or timing."""
import hashlib
import json
import re
import struct
from pathlib import Path
from . import weapons


def add_sound_events(raw: bytes, sound_map: dict[str, str]) -> tuple[bytes, list[dict]]:
    keys = {key: alias for key, alias in sound_map.items() if not key.startswith('sndnt#')}
    if not any(key.encode() + b'\0' in raw for key in keys):
        return raw, []
    if len(raw) >= 4 and struct.unpack_from('<H', raw)[0] == 19:
        # BO1 (v19) animations: notetrack sound adaptation is not ported yet; keep the motion as-is
        return raw, []
    if len(raw) < 4 or struct.unpack_from('<H', raw)[0] != 17:
        raise weapons.WeaponError('weapon sound notifications require a raw v17 animation')
    frames = struct.unpack_from('<H', raw, 2)[0]
    # Raw v17 ends with count:u8 followed by (name:cstring, frame:u16).
    # Find a fully validated suffix; all preceding motion data stays opaque.
    candidates = []
    for start in range(len(raw)):
        count = raw[start]
        if not count:
            continue
        pos, notes = start + 1, []
        for _ in range(count):
            end = raw.find(b'\0', pos, pos + 256)
            if end < 0 or end + 3 > len(raw) or not re.fullmatch(rb'[A-Za-z0-9_#/ .:+-]{1,255}', raw[pos:end]):
                break
            name = raw[pos:end].decode('ascii')
            frame = struct.unpack_from('<H', raw, end + 1)[0]
            if frame > frames:
                break
            notes.append((name, frame))
            pos = end + 3
        if len(notes) == count and pos == len(raw) and any(name in keys for name, _ in notes):
            candidates.append((start, notes))
    # Every candidate ends at the end of the file, so a shorter one is a tail of
    # the longest: a frame's high byte that equals the remaining note count
    # (frame 331 = 4B 01, then one note) parses as a second, nested suffix.
    # The longest one is the real section; the nested ones never hold all notes.
    if not candidates:
        raise weapons.WeaponError('raw animation has no valid notification suffix')
    start, notes = min(candidates)
    existing = set(notes)
    result, added = [], []
    for name, frame in notes:
        result.append((name, frame))
        if name in keys:
            native = 'sndnt#' + keys[name]
            if (native, frame) not in existing:
                result.append((native, frame))
                added.append({'source': name, 'sound': keys[name], 'frame': frame})
    if not added:
        return raw, []
    # The linker appends an end event; T6's final notifyCount is also u8.
    if len(result) > 254:
        raise weapons.WeaponError('converted animation exceeds notification count limit including end event')
    return raw[:start] + bytes([len(result)]) + b''.join(
        name.encode('ascii') + b'\0' + struct.pack('<H', frame) for name, frame in result), added


def stage_weapon_events(content: Path) -> dict:
    path = content / 'weapons.stage.json'
    stage = json.loads(path.read_text())
    report = {}
    for entry in stage['weapons']:
        weapon = content / 'weapons' / entry['name']
        if not weapon.is_file():
            continue
        fields = weapons.read_info_file(weapon)
        sound_map = dict(line.split() for line in fields.get('notetrackSoundMap', '').splitlines() if line.strip())
        if not sound_map:
            continue
        for key, name in list(fields.items()):
            if not name.startswith(weapons.PREFIXES['xanim']):
                continue
            source = content / 'xanim' / name
            if not source.is_file():
                continue
            raw, added = add_sound_events(source.read_bytes(), sound_map)
            if not added:
                continue
            # Shared animations may map the same note to different weapon sounds.
            digest = hashlib.sha256(raw).hexdigest()[:16]
            target_name = weapons.output_name('xanim', 'sound_events/' + digest + '/' + name.removeprefix(weapons.PREFIXES['xanim']))
            target = content / 'xanim' / target_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            fields[key] = target_name
            report[target_name] = {'source': name, 'added': added}
        weapon.write_text(weapons.write_info(fields), encoding='utf-8')
    stage['animation_sound_events'] = report
    path.write_text(json.dumps(stage, indent=2) + '\n')
    return report
