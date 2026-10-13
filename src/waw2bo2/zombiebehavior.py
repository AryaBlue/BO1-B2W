"""WaW speed selection and plain spawner locations on the BO2 AI runtime."""
from pathlib import Path
import re
import copy
from . import gsc

RUNTIME = r'maps\mp\waw\_waw2bo2_zombie_behavior'
ACTOR_TREE = 'waw2bo2_zombie_actor'
SELECTION = r'maps\_waw2bo2_source_spawns'
SPEED_STATE = r'maps\_waw2bo2_source_speed_state'


def source_speed_state(sources, definition: dict) -> str | None:
    """Keep initialization and round inputs read by the actual source selector.

    Round-spawn helpers may initialize speed bounds as a side effect of choosing
    the round population. Preserve those calls before choosing a zombie's speed,
    without starting a second WaW spawning loop on the native AI runtime.
    """
    from .gscport import top_level_statements
    contract = definition['source_speed']
    round_contract = definition['source_round_state']
    def owner(script, ref):
        if ref.qualifier:
            return sources.get(ref.qualifier)
        if ref.name.lower() in script.functions:
            return script
        return next((dep for path in script.includes if (dep := sources.get(path)) and
                     ref.name.lower() in dep.functions), None)
    def fields(script, name, seen=None):
        seen = set() if seen is None else seen
        key = (script.path, name)
        if key in seen or name not in script.functions:
            return set(), set()
        seen.add(key)
        fn = script.functions[name]
        tokens = script.tokens
        reads, writes = set(), set()
        for i in range(fn.body_open + 1, fn.body_close - 3):
            if [t.low for t in tokens[i:i + 2]] == ['level', '.']:
                field = tokens[i + 2].low
                if tokens[i + 3].text in ('=', '+=', '-=', '++', '--'):
                    writes.add(field)
                if tokens[i + 3].text != '=':
                    reads.add(field)
        for ref in gsc.references(tokens, fn.body_open + 1, fn.body_close):
            dep = owner(script, ref)
            if dep:
                r, w = fields(dep, ref.name.lower(), seen)
                reads |= r
                writes |= w
        return reads, writes
    speed = sources.get(contract['script'])
    if not speed or contract['function'] not in speed.functions:
        return None
    reads, _ = fields(speed, contract['function'])
    reads -= {'round_number', 'zombie_vars'}
    initial, start, end = [], [], []
    initializer = speed.functions.get('init')
    if initializer:
        for a, b in top_level_statements(speed.tokens, initializer.body_open, initializer.body_close):
            stmt = speed.tokens[a:b]
            if len(stmt) > 3 and [t.low for t in stmt[:2]] == ['level', '.'] and stmt[2].low in reads:
                initial.append(gsc.emit(stmt))
    framework = sources.get(round_contract['script'])
    begin = framework.functions.get(round_contract['start_function']) if framework else None
    if begin:
        for a, b in top_level_statements(framework.tokens, begin.body_open, begin.body_close):
            stmt = framework.tokens[a:b]
            if stmt[0].low == 'while':
                break
            if stmt[0].low in ('for', 'foreach'):
                continue
            direct = len(stmt) > 3 and [t.low for t in stmt[:2]] == ['level', '.'] and stmt[2].low in reads
            writers = [ref for ref in gsc.references(stmt) if (dep := owner(framework, ref)) and
                       fields(dep, ref.name.lower())[1] & reads]
            if direct or writers:
                start.append(gsc.emit(stmt))
    finish = framework.functions.get(round_contract['end_function']) if framework else None
    if finish:
        tokens = framework.tokens
        # End-of-round scalar updates belong to the previous source round.
        # A conditional update requires a control-flow slice, not a guessed rate.
        depth = 0
        for i in range(finish.body_open + 1, finish.body_close - 3):
            depth += tokens[i].text == '{'
            depth -= tokens[i].text == '}'
            if [t.low for t in tokens[i:i + 2]] != ['level', '.'] or tokens[i + 2].low not in reads:
                continue
            if tokens[i + 3].text not in ('=', '+=', '-=', '++', '--'):
                continue
            boundary = max((j for j in range(finish.body_open, i) if tokens[j].text in (';', '{', '}')),
                           default=finish.body_open)
            prefix = [t.low for t in tokens[boundary + 1:i]]
            if depth > 1 or any(word in ('if', 'else', 'for', 'switch', 'case') for word in prefix):
                raise ValueError(f'{framework.path}::{finish.name}: conditional source speed state needs a control-flow slice')
            j = next(j for j in range(i, finish.body_close) if tokens[j].text == ';')
            stmt = copy.deepcopy(tokens[i:j + 1])
            if depth == 0:
                initial.append(gsc.emit(stmt))
                continue
            for k in range(len(stmt) - 2):
                if [t.low for t in stmt[k:k + 3]] == ['level', '.', 'round_number']:
                    stmt[k].text, stmt[k + 1].text, stmt[k + 2].text = 'source_round', '', ''
            end.append(gsc.emit(stmt))
    if not initial and not start and not end:
        return None
    includes = {contract['script'], round_contract['script']}
    if framework:
        includes.update(framework.includes)
    return ('\n'.join('#include ' + path + ';' for path in sorted(includes)) +
            '\ninit()\n{\n' + '\n'.join(initial) + '\n}\n' +
            '\nprepare_round()\n{\n' + ('if (level.round_number > 1) {\nsource_round = level.round_number - 1;\n' +
             '\n'.join(end) + '\n}\n' if end else '') + '\n'.join(start) + '\n}\n')


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
    if script and fn is None:
        # Older/renamed frameworks declare the same movement table in another
        # initializer. Identify the role from its authored table assignments.
        candidates = []
        for candidate in script.functions.values():
            if candidate.params:
                continue
            tokens = script.tokens
            for i in range(candidate.body_open + 1, candidate.body_close - 12):
                words = [t.low for t in tokens[i:i + 13]]
                if words[:5] == ['level', '.', contract['field'], '[', '"' + contract['row'] + '"'] and \
                        words[5:7] == [']', '['] and words[8:11] == [']', '=', '%'] and \
                        re.fullmatch(r'"(?:walk|run|sprint)\d+"', words[7]):
                    candidates.append(candidate)
                    break
        if len(candidates) > 1:
            raise ValueError(f'{script.path}: ambiguous movement table initializers')
        fn = candidates[0] if candidates else None
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
        text = actor.read_text(encoding='utf-8').replace('zm_nuked_basic', ACTOR_TREE)
        text = re.sub(r'\n// BEGIN SOURCE MOVEMENT REFS.*?// END SOURCE MOVEMENT REFS\n', '', text, flags=re.S)
        # T6 keeps only animation-tree nodes referenced by compiled scripts.
        # ASD substate names are strings and do not pin those nodes themselves.
        text += ('\n// BEGIN SOURCE MOVEMENT REFS\nwaw_reference_movement_anims()\n{\n' +
                 ''.join(f'    dummy_anim_ref = %{clip};\n' for clip in sorted(set(clips))) +
                 '}\n// END SOURCE MOVEMENT REFS\n')
        actor.write_text(text, encoding='utf-8')
    return {'states': sets, 'tree': ACTOR_TREE, 'clips': sorted(set(clips))}


def runtime_source(definition: dict, speed_function: str | None, selection_function: str | None = None,
                   speed_state_function: str | None = None) -> str:
    native = definition['native_spawner']
    owned = definition['owned_spawner']
    entry = definition['native_spawn_init']
    result_field = definition['source_speed']['owned_result_field']
    callback_field = definition['native_movement']['callback']
    speed = (f'self {speed_function}();\n'
             f'    self refresh_speed();\n'
             '    if ( !isdefined( self.waw_speed_callback_bound ) )\n'
             '    {\n'
             '        self.waw_speed_callback_bound = 1;\n'
             f'        self.waw_previous_speed_callback = self.{callback_field};\n'
             f'        self.{callback_field} = ::source_animstate;\n'
             '    }'
             if speed_function else 'self maps\\mp\\zombies\\_zm_utility::init_zombie_run_cycle();')
    state_init = f'{speed_state_function}::init();' if speed_state_function else ''
    state_round = f'{speed_state_function}::prepare_round();' if speed_state_function else ''
    selection = (f'{selection_function}( candidates, level.waw_previous_spawner )'
                 if selection_function else 'common_scripts\\utility::random( candidates )')
    return f'''// waw2bo2: source WaW speed rules and plain spawner origin ownership.
init()
{{
    {state_init}
    bound = 0;
    spawners = getentarray( "zombie_spawner", "script_noteworthy" );
    foreach ( spawner in spawners )
    {{
        if ( !isdefined( spawner.spawn_funcs ) )
            continue;
        for ( i = 0; i < spawner.spawn_funcs.size; i++ )
        {{
            if ( spawner.spawn_funcs[i]["function"] == {native}::{entry} ||
                 spawner.spawn_funcs[i]["function"] == {owned}::{entry} )
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
    if ( !isdefined( level.waw_speed_round ) || level.waw_speed_round != level.round_number )
    {{
        {state_round}
        level.waw_speed_round = level.round_number;
    }}
    {speed}
}}

refresh_speed( native_request )
{{
    if ( isdefined( self.{result_field} ) )
        native_request = self.{result_field};
    self maps\\mp\\zombies\\_zm_utility::set_zombie_run_cycle( native_request );
}}

source_animstate( animstate, substate )
{{
    // Cached native scripts can still request another speed. Restore the source
    // field and its animation state when native movement consumes that request.
    if ( isdefined( self.{result_field} ) && self.zombie_move_speed != self.{result_field} )
    {{
        self refresh_speed();
        animstate = self maps\\mp\\animscripts\\zm_utility::append_missing_legs_suffix( "zm_move_" + self.{result_field} );
        if ( isdefined( self.a.gib_ref ) && self.a.gib_ref == "no_legs" )
            animstate = "zm_move_stumpy";
        substate = undefined;
        self setanimstatefromasd( animstate );
    }}
    if ( isdefined( self.waw_previous_speed_callback ) )
        self [[ self.waw_previous_speed_callback ]]( animstate, substate );
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
    movement = definition['native_movement']
    movement_source = bo2_root / 'raw' / (movement['script'].replace('\\', '/') + '.gsc')
    moving = gsc.parse(movement_source.read_text(encoding='utf-8'), movement['script'])
    move_fn = moving.functions.get(movement['function'])
    callback = ['self', '[[', 'self', '.', movement['callback'], ']]', '(']
    words = [t.low for t in moving.tokens[move_fn.body_open:move_fn.body_close]] if move_fn else []
    if not any(words[i:i + len(callback)] == callback for i in range(len(words))):
        raise ValueError(f'{movement["script"]}: native movement does not invoke the source speed callback')
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
        for ref in gsc.references(zm.tokens):
            if ref.qualifier == native:
                zm.tokens[ref.qual_index].text = owned
            if ref.name.lower() == 'set_zombie_run_cycle':
                if ref.qualifier is None or ref.qualifier == r'maps\mp\zombies\_zm_utility':
                    zm.tokens[ref.index].text = RUNTIME + '::refresh_speed'
                    if ref.qual_index is not None:
                        zm.tokens[ref.qual_index].text = ''
                        zm.tokens[ref.index - 1].text = ''
        fn = zm.functions.get('round_spawning')
        if fn:
            for ref in gsc.references(zm.tokens, fn.body_open, fn.body_close):
                if ref.name.lower() == 'random' and not ref.pointer and [t.low for t in zm.tokens[ref.index + 2:ref.index + 5]] in (
                    ['level', '.', 'zombie_spawners'], ['level', '.', 'zombie_spawn']):
                    zm.tokens[ref.index].text = RUNTIME + '::choose_spawner'
            bootstrap.write_text(gsc.emit(zm.tokens), encoding='utf-8')
