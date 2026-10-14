"""Bring source-owned weapon client libraries onto the T6 client runtime."""
from pathlib import Path
import warnings
from . import gsc


def translate_library(source: str, effects: dict[str, str], weapons: dict[str, str],
                      sound_names: set[str]) -> str:
    tokens = gsc.tokenize(source)
    for token in tokens:
        if token.kind == gsc.IDENT and token.low == 'realwait':
            token.text = 'waitrealtime'
        elif token.kind == gsc.STRING:
            name = token.text[1:-1]
            if name in effects:
                token.text = '"' + effects[name] + '"'
            elif name in weapons and weapons[name]:
                token.text = '"' + weapons[name] + '"'
            elif name in sound_names:
                token.text = '"waw/' + name + '"'
    text = gsc.emit(tokens)
    for name in ('_utility', '_fx', '_music'):
        text = text.replace('clientscripts\\' + name, 'clientscripts\\mp\\' + name)
    # A legacy clientNotify is a T6 client-system command, whereas source
    # libraries wait on a level notification. Forward only their single-arg
    # notification listeners; native notetracks retain their event payload.
    script = gsc.parse(text, '<source client library>')
    events = set()
    for i, token in enumerate(script.tokens[:-4]):
        if token.low == 'waittill' and i and script.tokens[i - 1].low == 'level' \
                and script.tokens[i + 1].text == '(' and script.tokens[i + 2].kind == gsc.STRING \
                and script.tokens[i + 3].text == ')':
            events.add(script.tokens[i + 2].text[1:-1])
    if events:
        init = script.functions['init']
        script.tokens[init.body_open].text += ''.join(
            f'\n    registersystem( "{name}", ::waw_notify_{i} );' for i, name in enumerate(sorted(events)))
        text = gsc.emit(script.tokens)
        text += ''.join(f'\nwaw_notify_{i}( localclientnum, state )\n{{\n    level notify( "{name}" );\n}}\n'
                        for i, name in enumerate(sorted(events)))
    return text


def stage_tesla(roots: list[Path], project: Path, effects: dict[str, str],
                weapon_table: dict[str, str], sound_names: set[str]) -> str:
    core = project / 'maps/mp/waw/_waw2bo2_core.gsc'
    if not core.is_file() or 'waw_tesla_init()' not in core.read_text(encoding='utf-8'):
        return ''
    source = next((root / 'clientscripts/_zombiemode_tesla.csc' for root in roots
                   if (root / 'clientscripts/_zombiemode_tesla.csc').is_file()), None)
    if source is None:
        warnings.warn('source Tesla gameplay library has no matching client library; client effects were not staged',
                      RuntimeWarning)
        return ''
    target = project / 'clientscripts/mp/waw/_zombiemode_tesla.csc'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(translate_library(source.read_text(encoding='utf-8'), effects, weapon_table, sound_names),
                      encoding='utf-8')
    return '    clientscripts\\mp\\waw\\_zombiemode_tesla::init();\n'
