"""Carry the WaW zombie zone graph into the BO2 map script.

WaW (_zombiemode_zone_manager) and BO2 (_zm_zonemgr) share the model: zones
are ``info_volume`` brush entities named by targetname, linked with
``add_adjacent_zone( a, b, flag )`` where the flag is set by the door that
opens the connection, plus a list of zones active at start. The WaW map
script is plain GSC in the map zone; both are read from its tokens, so
commented-out and developer-only (``/# #/``) calls are not part of the graph.

A flag argument may be a local array built just before the call (Der Riese:
``flag_array[0] = ...; add_adjacent_zone( a, b, flag_array, true )``). Both
frameworks require every flag of such an array (and any one of several
single-flag calls for the same pair). The array is resolved from the local
assignments in source order and written as ``[ "f0", "f1" ]``; BO2's
add_adjacent_zone indexes level.flag with its flag argument, so those links
are made through _zm_zonemgr's zone_init/make_zone_adjacent, as WaW's own
add_adjacent_zone does.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import gsc

ADJACENT_RE = re.compile(r"^\s*(?:[\w\\/]+::)?add_adjacent_zone\s*\(([^;]*)\)\s*;", re.MULTILINE)
INIT_ZONE_RE = re.compile(
    r'^\s*(?:zones|init_zones|level\s*\.\s*dlc3\s*\.\s*initialzones)'
    r'\s*\[[^\]]*\]\s*=\s*"([^"]+)"\s*;', re.MULTILINE | re.IGNORECASE)


class ZoneError(ValueError):
    pass


ARRAY_ARG_RE = re.compile(r'^\[(.*)\]$')


def live_tokens(waw_gsc: str) -> list[gsc.Token]:
    """Tokens of retail code: comments dropped, ``/# ... #/`` developer blocks skipped."""
    out, dev = [], False
    for token in gsc.tokenize(waw_gsc):
        if token.text == '/#':
            dev = True
        elif token.text == '#/':
            dev = False
        elif not dev and token.kind != gsc.EOF:
            out.append(token)
    return out


def _arguments(tokens: list[gsc.Token], open_: int) -> tuple[list[list[gsc.Token]], int]:
    args, current, depth, i = [], [], 0, open_ + 1
    while i < len(tokens):
        text = tokens[i].text
        if text in ('(', '[', '[['):
            depth += 1
        elif text in (')', ']', ']]'):
            if depth == 0:
                break
            depth -= 1
        if text == ',' and depth == 0:
            args.append(current)
            current = []
        else:
            current.append(tokens[i])
        i += 1
    if current:
        args.append(current)
    return args, i


def _render(arg: list[gsc.Token], arrays: dict[str, dict[int, str]], scalars: dict[str, str]) -> str:
    if len(arg) == 1 and arg[0].kind == gsc.IDENT:
        name = arg[0].low
        if name in arrays:
            return '[ ' + ', '.join(value for _, value in sorted(arrays[name].items())) + ' ]'
        if name in scalars:
            return scalars[name]
    return ' '.join(t.text for t in arg).replace(' ( ', '( ').replace(' ,', ',')


def read_waw_zones(waw_gsc: str) -> tuple[list[str], list[str]]:
    """(initial zones, add_adjacent_zone argument lists) from a WaW map script.

    Both are empty for a map without a zone graph (prototype/asylum/sumpf
    scripts); entities.synthesize_zones builds one from its spawners."""
    tokens = live_tokens(waw_gsc)
    lines: dict[int, list[str]] = {}
    for t in tokens:
        lines.setdefault(t.line, []).append(t.text)
    live = '\n'.join(' '.join(words) for words in lines.values())
    adjacency: list[str] = []
    arrays: dict[str, dict[int, str]] = {}
    scalars: dict[str, str] = {}
    depth = 0
    for i, token in enumerate(tokens):
        if token.text == '{':
            depth += 1
        elif token.text == '}':
            depth -= 1
            if depth == 0:
                arrays, scalars = {}, {}   # locals belong to one function
        nxt = tokens[i + 1:i + 7]
        texts = [t.text for t in nxt]
        if token.kind == gsc.IDENT and (i == 0 or tokens[i - 1].text in (';', '{', '}')):
            # local array element / local string: name[ n ] = "x";  name = "x";
            # (the script's last statements leave fewer than six tokens ahead)
            if len(nxt) > 5 and texts[0] == '[' and texts[2:4] == [']', '='] and texts[5] == ';' \
                    and nxt[1].kind == gsc.NUMBER and nxt[4].kind == gsc.STRING:
                arrays.setdefault(token.low, {})[int(float(nxt[1].text))] = nxt[4].text
            elif len(nxt) > 2 and texts[0] == '=' and texts[2] == ';' and nxt[1].kind == gsc.STRING:
                scalars[token.low] = nxt[1].text
                arrays.pop(token.low, None)
            elif texts[:4] == ['=', '[', ']', ';']:
                arrays[token.low] = {}
        if token.low == 'add_adjacent_zone' and texts[:1] == ['('] and                 (i == 0 or tokens[i - 1].text != '.'):
            args, _ = _arguments(tokens, i + 1)
            adjacency.append(', '.join(_render(arg, arrays, scalars) for arg in args))
    initial = list(dict.fromkeys(INIT_ZONE_RE.findall(live)))
    if not adjacency:
        return [], []
    if not initial:
        initial = [re.findall(r'"([^"]+)"', adjacency[0])[0]]
    return initial, adjacency


def zone_names(initial: list[str], adjacency: list[str]) -> set[str]:
    """Every zone a WaW zone graph names (start zones and both ends of each link)."""
    names = set(initial)
    for args in adjacency:
        names.update(re.findall(r'"([^"]+)"', args)[:2])
    return names


def patch_bo2_script(bo2_gsc: str, project: str, initial: list[str], adjacency: list[str]) -> str:
    """Replace the template's single ``start_zone`` setup with the WaW zones."""
    init_block = "".join(f'    init_zones[{i}] = "{z}";\n' for i, z in enumerate(initial))
    out, n = re.subn(r'^\s*init_zones\[0\] = "start_zone";\n', init_block, bo2_gsc, flags=re.MULTILINE)
    if n != 1 and init_block not in bo2_gsc:
        raise ZoneError("template init_zones block not found in the map script")
    body = "".join(adjacent_zone_call(args) for args in adjacency)
    func = re.compile(rf"^{re.escape(project)}_zone_init\(\)\s*\{{.*?^\}}", re.MULTILINE | re.DOTALL)
    if not func.search(out):
        raise ZoneError(f"{project}_zone_init() not found in the map script")
    return func.sub(lambda _: f"{project}_zone_init()\n{{\n    // zone graph from the WaW map script\n{body}}}", out, count=1)


def _split_args(args: str) -> list[str]:
    parts, depth, current = [], 0, ''
    for ch in args:
        depth += ch in '[('
        depth -= ch in '])'
        if ch == ',' and depth == 0:
            parts.append(current.strip())
            current = ''
        else:
            current += ch
    return parts + [current.strip()] if current.strip() else parts


def adjacent_zone_call(args: str) -> str:
    """One WaW add_adjacent_zone in BO2 form (see the module docstring)."""
    parts = _split_args(args)
    array = ARRAY_ARG_RE.match(parts[2]) if len(parts) > 2 else None
    if array is None:
        return f"    add_adjacent_zone( {args} );\n"
    a, b = parts[0], parts[1]
    flags = _split_args(array[1])
    one_way = parts[3] if len(parts) > 3 else 'false'
    lines = ['    waw2bo2_flags = [];']
    lines += [f'    waw2bo2_flags[{i}] = {flag};' for i, flag in enumerate(flags)]
    lines += [f'    if ( !isdefined( level.flag[{flag}] ) )\n        flag_init( {flag} );' for flag in flags]
    lines += [f'    zone_init( {a} );', f'    zone_init( {b} );',
              f'    make_zone_adjacent( {a}, {b}, waw2bo2_flags );',
              f'    if ( !( {one_way} ) )\n        make_zone_adjacent( {b}, {a}, waw2bo2_flags );']
    return '\n'.join(lines) + '\n'


def apply(waw_gsc_path: Path, bo2_gsc_path: Path, project: str,
          synthesized: dict | None = None) -> tuple[list[str], int]:
    initial, adjacency = read_waw_zones(waw_gsc_path.read_text(encoding="utf-8", errors="replace"))
    if not adjacency and synthesized:
        initial, adjacency = synthesized["initial"], synthesized["adjacency"]
    if not initial:
        raise ZoneError("no add_adjacent_zone calls in the WaW map script and no zombie spawners to build zones from")
    text = bo2_gsc_path.read_text(encoding="utf-8", errors="replace")
    bo2_gsc_path.write_text(patch_bo2_script(text, project, initial, adjacency), encoding="utf-8")
    return initial, len(adjacency)
