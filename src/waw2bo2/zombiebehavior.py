"""WaW speed selection and plain spawner locations on the BO2 AI runtime."""
from pathlib import Path
from . import gsc

RUNTIME = r'maps\mp\waw\_waw2bo2_zombie_behavior'


def runtime_source(definition: dict, speed_function: str | None) -> str:
    native = definition['native_spawner']
    owned = definition['owned_spawner']
    entry = definition['native_spawn_init']
    result_field = definition['source_speed']['result_field']
    speed = (f'self {speed_function}();\n'
             f'    self maps\\mp\\zombies\\_zm_utility::set_zombie_run_cycle( self.{result_field} );'
             if speed_function else 'self maps\\mp\\zombies\\_zm_utility::init_zombie_run_cycle();')
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
