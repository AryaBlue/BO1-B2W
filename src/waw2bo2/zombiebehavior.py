"""WaW speed selection and plain spawner locations on the BO2 AI runtime."""
from pathlib import Path
import re
import copy
from . import gsc

RUNTIME = r'maps\mp\waw\_waw2bo2_zombie_behavior'
ACTOR_TREE = 'waw2bo2_zombie_actor'
SELECTION = r'maps\_waw2bo2_source_spawns'


def source_selection(sources, definition: dict) -> str | None:
    """Extract the source loop's selection statements through its history update."""
    c = definition['source_selection']
    script = sources.get(c['script'])
    fn = script.functions.get(c['function']) if script else None
    if fn is None:
        return None
    tokens = script.tokens
    depth, start, base, end = 0, None, None, None
    for i in range(fn.body_open + 1, fn.body_close):
        depth += tokens[i].text == '{'
        depth -= tokens[i].text == '}'
        words = [t.low for t in tokens[i:i + 5]]
        if start is None and words == [c['candidate'], '=', 'level', '.', c['array_field']]:
            start, base = i, depth
        if start is not None and depth == base and [t.low for t in tokens[i:i + 4]] == [c['previous'], '=', c['candidate'], ';']:
            end = i + 4
            break
    if start is None or end is None:
        return None
    body = copy.deepcopy(tokens[start:end])
    for i in range(len(body) - 2):
        if [t.low for t in body[i:i + 3]] == ['level', '.', c['array_field']]:
            body[i].text = 'candidates'
            body[i + 1].text = body[i + 2].text = ''
    includes = '#include ' + c['script'] + ';'
    return (includes + f'\nchoose(candidates, {c["previous"]})\n{{\n' + gsc.emit(body) +
            f'\nreturn {c["candidate"]};\n}}\n')


def movement_sets(sources, definition: dict) -> tuple[str | None, dict[str, list[str]]]:
    """Read flat, authored movement table assignments, retaining variant weights."""
    contract = definition['source_movement']
    script = sources.get(contract['script'])
    fn = script.functions.get(contract['function']) if script else None
    if fn is None:
        return None, {}
    found = {}
    tokens = script.tokens
    depth = 0
    for i in range(fn.body_open + 1, fn.body_close):
        depth += tokens[i].text == '{'
        depth -= tokens[i].text == '}'
        words = [t.low for t in tokens[i:i + 13]]
        if len(words) < 13 or words[:5] != ['level', '.', contract['field'], '[', '"' + contract['row'] + '"']:
            continue
        if words[5:7] != [']', '['] or words[8:11] != [']', '=', '%'] or words[12] != ';':
            continue
        alias = words[7].strip('"')
        match = re.fullmatch(r'(walk|run|sprint)(\d+)', alias)
        if not match:
            continue
        if depth:
            raise ValueError(f'{contract["script"]}:{tokens[i].line}: conditional movement table requires runtime translation')
        found.setdefault(match[1], {})[int(match[2])] = words[11]
    return fn.animtree, {speed: [entries[i] for i in sorted(entries)] for speed, entries in found.items()}


def stage_actor_movement(sources, out_root: Path, bo2_root: Path, definition: dict) -> dict:
    _, sets = movement_sets(sources, definition)
    if not sets:
        return {}
    asd = (bo2_root / 'raw/animstatedefs/zm_nuked_basic.asd').read_text(encoding='utf-8')
    clips = []
    for speed, names in sets.items():
        assets = ['waw_anim_' + name for name in names]
        for asset in assets:
            if not (out_root / 'xanim' / asset).is_file():
                raise ValueError(f'Source movement xanim missing: {asset}')
        state = definition['source_movement']['states'][speed]
        pattern = re.compile(r'(^' + re.escape(state) + r'\s*:[^\n]*\n\{).*?^\}', re.M | re.S)
        asd, count = pattern.subn(lambda m: m[1] + '\n' + ''.join('\t' + a + '\n' for a in assets) + '}', asd)
        if count != 1:
            raise ValueError(f'Native movement state {state}: expected one definition')
        clips.extend(assets)
    atr = (bo2_root / 'raw/animtrees/zm_nuked_basic.atr').read_text(encoding='utf-8')
    atr, count = re.subn(r'(^body\s*\n\{)', lambda m: m[1] + '\n' +
                        ''.join('\t' + c + '\n' for c in sorted(set(clips))), atr, count=1, flags=re.M)
    if count != 1:
        raise ValueError('Native zombie animation tree has no body group')
    for directory, suffix, text in [('animtrees', '.atr', atr), ('animstatedefs', '.asd', asd)]:
        target = out_root / directory / (ACTOR_TREE + suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    for actor in (out_root / 'aitype').rglob('waw_*.?sc'):
        actor.write_text(actor.read_text(encoding='utf-8').replace('zm_nuked_basic', ACTOR_TREE), encoding='utf-8')
    return {'states': sets, 'tree': ACTOR_TREE, 'clips': sorted(set(clips))}


def runtime_source(definition: dict, speed_function: str | None, selection_function: str | None = None) -> str:
    native = definition['native_spawner']
    owned = definition['owned_spawner']
    entry = definition['native_spawn_init']
    result_field = definition['source_speed']['result_field']
    speed = (f'self {speed_function}();\n'
             f'    self maps\\mp\\zombies\\_zm_utility::set_zombie_run_cycle( self.{result_field} );'
             if speed_function else 'self maps\\mp\\zombies\\_zm_utility::init_zombie_run_cycle();')
    selection = (f'{selection_function}( candidates, level.waw_previous_spawner )'
                 if selection_function else 'common_scripts\\utility::random( candidates )')
    return f'''// waw2bo2: source WaW speed rules and plain spawner origin ownership.
init()
{{
    bound = 0;
    spawners = getentarray( "zombie_spawner", "script_noteworthy" );
    foreach ( spawner in spawners )
    {{
        if ( !isdefined( spawner.spawn_funcs ) )
            continue;
        for ( i = 0; i < spawner.spawn_funcs.size; i++ )
        {{
            if ( spawner.spawn_funcs[i]["function"] == {native}::{entry} )
            {{
                spawner.spawn_funcs[i]["function"] = {owned}::{entry};
                bound++;
            }}
        }}
    }}
    println( "WAW2BO2 zombie spawn callbacks adapted: " + bound );
}}

bind_spawn_location()
{{
    // Plain WaW spawners use their own origin. Risers keep BO2's zone selection.
    if ( isdefined( self.script_string ) && self.script_string == "riser" )
        return;
    if ( !isdefined( level.zombie_spawn_locations ) )
        return;
    spots = level.zombie_spawn_locations;
    foreach ( spot in spots )
    {{
        if ( spot.script_noteworthy == "{definition['plain_spawn_location']}" &&
             distancesquared( self.origin, spot.origin ) < 0.01 )
        {{
            self.spawn_point_override = spot;
            return;
        }}
    }}
}}

select_speed()
{{
    {speed}
}}

choose_spawner( candidates )
{{
    if ( !isdefined( level.waw_selection_round ) || level.waw_selection_round != level.round_number )
    {{
        level.waw_previous_spawner = undefined;
        level.waw_selection_round = level.round_number;
    }}
    chosen = {selection};
    level.waw_previous_spawner = chosen;
    return chosen;
}}
'''


def stage_native_support(out_root: Path, bo2_root: Path, definition: dict) -> None:
    """Own the registered spawn callback so cached stock scripts cannot mask it."""
    if not (out_root / (RUNTIME.replace('\\', '/') + '.gsc')).is_file():
        return
    native, owned = definition['native_spawner'], definition['owned_spawner']
    source = (bo2_root / 'raw' / (native.replace('\\', '/') + '.gsc')).read_text(encoding='utf-8')
    script = gsc.parse(source, native)
    fn = script.functions.get(definition['native_spawn_init'])
    location = script.functions.get(definition['native_location_function'])
    if fn is None or location is None:
        raise ValueError(f'{native}: required spawn callback/location function missing')
    refs = [r for r in gsc.references(script.tokens, fn.body_open, fn.body_close)
            if r.name.lower() == definition['native_speed_init'] and not r.pointer]
    if len(refs) != 1:
        raise ValueError(f'{native}: expected one speed initialization before zombie_think')
    ref = refs[0]
    if any(r.name.lower() == 'zombie_think' and r.index < ref.index
           for r in gsc.references(script.tokens, fn.body_open, fn.body_close)):
        raise ValueError(f'{native}: speed initialization must precede zombie_think')
    if ref.qualifier is not None or script.tokens[ref.index - 1].low != 'self':
        raise ValueError(f'{native}: expected synchronous zombie method speed initialization')
    script.tokens[ref.index].text = RUNTIME + '::select_speed'
    script.tokens[fn.body_open].text += '\n    self ' + RUNTIME + '::bind_spawn_location();'
    selections = [r for r in gsc.references(script.tokens, location.body_open, location.body_close)
                  if r.name.lower() == 'random' and not r.pointer and
                  [t.low for t in script.tokens[r.index - 2:r.index + 5]] ==
                  ['spot', '=', 'random', '(', 'spots', ')', ';']]
    if len(selections) != 1:
        raise ValueError(f'{native}: expected one ordinary spawn location selection')
    # Select before target/zone metadata is copied, not only in the animation loop.
    script.tokens[selections[0].index - 2].text = (
        'if ( isdefined( self.spawn_point_override ) )\n'
        '        spot = self.spawn_point_override;\n    else\n        spot')
    # Local calls/pointers still resolve to the copied callback implementation.
    for ref in gsc.references(script.tokens):
        if ref.qualifier == native:
            script.tokens[ref.qual_index].text = owned
    for token in script.tokens:
        match = gsc.INCLUDE_RE.match(token.text) if token.kind == gsc.DIRECTIVE else None
        if match and match[1] == native:
            token.text = f'#include {owned};'
    text = gsc.emit(script.tokens)
    dest = out_root / (owned.replace('\\', '/') + '.gsc')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('// waw2bo2: native AI with source spawn/speed adapters.\n' + text, encoding='utf-8')
    bootstrap = out_root / 'maps/mp/waw/_waw2bo2_zm.gsc'
    if bootstrap.is_file():
        zm = gsc.parse(bootstrap.read_text(encoding='utf-8'), 'owned zombie bootstrap')
        fn = zm.functions.get('round_spawning')
        if fn:
            for ref in gsc.references(zm.tokens, fn.body_open, fn.body_close):
                if ref.name.lower() == 'random' and not ref.pointer and [t.low for t in zm.tokens[ref.index + 2:ref.index + 5]] in (
                    ['level', '.', 'zombie_spawners'], ['level', '.', 'zombie_spawn']):
                    zm.tokens[ref.index].text = RUNTIME + '::choose_spawner'
            bootstrap.write_text(gsc.emit(zm.tokens), encoding='utf-8')
