"""Preserve authored perk-conditioned point modifiers on native T6 scoring."""
from pathlib import Path
import copy

from . import gsc

RULES = r'maps\mp\waw\_waw2bo2_score_rules'
NATIVE = r'maps\mp\zombies\_zm_score'
OWNED = r'maps\mp\waw\_waw2bo2_score'


def source_rules(script):
    """Extract pure point arithmetic guarded by a source perk test.

    Preserve each source event case and condition; do not infer a perk's
    effect from its name. Other scoring actions stay on the native runtime.
    """
    fn = script.functions.get('player_add_points') if script else None
    if fn is None:
        return None
    tokens = script.tokens
    # Only direct cases of switch(event) are eligible. Copying a nested rule
    # without its enclosing condition would change when its modifier applies.
    switches = {}
    for i in range(fn.body_open + 1, fn.body_close - 4):
        if [t.low for t in tokens[i:i + 4]] == ['switch', '(', 'event', ')'] and tokens[i + 4].text == '{':
            switches[i + 4] = gsc._match(tokens, i + 4, '{', '}')
    scopes = []
    event = None
    rules = []
    for i in range(fn.body_open + 1, fn.body_close):
        if tokens[i].text == '{':
            scopes.append(i)
        elif tokens[i].text == '}' and scopes:
            scopes.pop()
        if len(scopes) != 1 or scopes[0] not in switches:
            continue
        if tokens[i].low == 'case':
            event = tokens[i + 1].text if tokens[i + 1].kind == gsc.STRING else None
        elif tokens[i].low == 'default':
            event = None
        if tokens[i].low != 'if' or tokens[i + 1].text != '(' or event is None:
            continue
        close = gsc._match(tokens, i + 1, '(', ')')
        if tokens[close + 1].text != '{':
            continue
        end = gsc._match(tokens, close + 1, '{', '}')
        condition = tokens[i:close + 1]
        body = tokens[close + 2:end]
        # This contract is deliberately pure arithmetic, not a copied score
        # framework with T6 stats, client fields or team bookkeeping removed.
        if not any(t.low == 'hasperk' for t in condition):
            continue
        if any(t.kind == gsc.IDENT and t.low not in
               {'if', 'self', 'hasperk', 'points', *fn.params} for t in condition):
            continue
        if not body or body[0].low != 'points' or body[-1].text != ';':
            continue
        if any(t.kind == gsc.IDENT and t.low != 'points' for t in body):
            continue
        if any(t.kind == gsc.STRING or t.text in ('{', '}', '[', ']') for t in body):
            continue
        statements = gsc.emit(body).split(';')[:-1]
        if not statements or any(not _point_assignment(statement) for statement in statements):
            continue
        if tokens[end + 1].low == 'else':
            continue
        rules.append((event, gsc.emit(copy.deepcopy(tokens[i:end + 1]))))
    if not rules:
        return None
    text = '#include maps\\_zombiemode_utility;\nadjust(points, event, mod, hit_location, is_dog)\n{\n'
    for event, rule in rules:
        text += f'    if (event == {event}) {{\n{rule}\n    }}\n'
    return text + '    return points;\n}\n'


def _point_assignment(text):
    tokens = gsc.tokenize(text)[:-1]
    return (len(tokens) >= 3 and tokens[0].low == 'points'
            and tokens[1].text in ('=', '+=', '-=', '*=', '/=', '%=')
            and all(t.kind == gsc.NUMBER or t.low == 'points'
                    or t.text in ('+', '-', '*', '/', '%', '(', ')') for t in tokens[2:])
            and not any(a.low == 'points' and b.text == '(' for a, b in zip(tokens, tokens[1:])))


def stage_native(out_root: Path, bo2_root: Path):
    if not (out_root / (RULES.replace('\\', '/') + '.gsc')).exists():
        return
    source = (bo2_root / 'raw' / (NATIVE.replace('\\', '/') + '.gsc')).read_text(encoding='utf-8')
    script = gsc.parse(source, NATIVE)
    fn = script.functions['player_add_points']
    matches = [i for i in range(fn.body_open, fn.body_close - 4)
               if [t.low for t in script.tokens[i:i + 4]] == ['player_points', '=', 'multiplier', '*']]
    if len(matches) != 1:
        raise ValueError('Native score contract requires one final player point multiplier')
    token = script.tokens[matches[0]]
    token.pre += f'\n    player_points = self {RULES}::adjust(player_points, event, mod, hit_location, is_dog);\n    '
    dest = out_root / (OWNED.replace('\\', '/') + '.gsc')
    dest.write_text(gsc.emit(script.tokens).replace(NATIVE, OWNED), encoding='utf-8')
    # Spawn/death callbacks must use an owned script, rather than an override
    # of a stock script that T6 may already have cached.
    native_spawner = r'maps\mp\zombies\_zm_spawner'
    owned_spawner = r'maps\mp\waw\_waw2bo2_spawner'
    caller = out_root / (owned_spawner.replace('\\', '/') + '.gsc')
    text = caller.read_text(encoding='utf-8') if caller.exists() else (
        bo2_root / 'raw' / (native_spawner.replace('\\', '/') + '.gsc')).read_text(encoding='utf-8')
    caller.write_text(text.replace(native_spawner, owned_spawner).replace(NATIVE, OWNED), encoding='utf-8')
    for path in (out_root / 'maps/mp/waw').rglob('*.gsc'):
        if path == caller:
            continue
        text = path.read_text(encoding='utf-8')
        changed = text.replace(NATIVE, OWNED).replace(native_spawner, owned_spawner)
        if changed != text:
            path.write_text(changed, encoding='utf-8')
