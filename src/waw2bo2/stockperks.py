"""Explicit BO2 perk ownership, independent of the source map's name."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import gsc

# Community WaW perk packs use these engine perks as storage for BO1/BO2
# effects. This table is applied only when the user selects BO2 stock perks.
PERK_NAMES = {
    'specialty_detectexplosive': 'specialty_flakjacket',
    'specialty_extraammo': 'specialty_additionalprimaryweapon',
    'specialty_bulletaccuracy': 'specialty_deadshot',
    'specialty_boost': 'specialty_grenadepulldeath',
    'specialty_quieter': 'specialty_scavenger',
    'specialty_shades': 'specialty_finalstand',
}
GROUPS = {'zombie_vending_bo1': 'zombie_vending', 'zombie_vending_bo2': 'zombie_vending'}
MACHINE_NAMES = {
    'vending_mule_kick': 'vending_additionalprimaryweapon',
    'vending_staminup': 'vending_marathon',
    'vending_phd_flopper': 'vending_divetonuke',
    'vending_whos_who': 'vending_chugabud',
    'mule_kick_on': 'additionalprimaryweapon_on',
    'staminup_on': 'marathon_on',
    'phd_on': 'divetonuke_on',
    'cherry_on': 'electric_cherry_on',
}
FLAGS = ('doubletap', 'juggernaut', 'revive', 'sleightofhand', 'marathon',
         'deadshot', 'additionalprimaryweapon', 'tombstone', 'chugabud')
MODULES = ('electric_cherry', 'divetonuke')
SUPPORTED_PERKS = {'specialty_armorvest', 'specialty_quickrevive', 'specialty_rof',
                   'specialty_fastreload', 'specialty_longersprint', 'specialty_weapupgrade',
                   *PERK_NAMES.values()}
# BO2's prison precacher uses this shipped model for both Deadshot states;
# the older default precacher references BO1 names absent from BO2 Mod Tools.
STOCK_MODELS = {'zombie_vending_ads': 'p6_zm_al_vending_ads_on',
                'zombie_vending_ads_on': 'p6_zm_al_vending_ads_on',
                'zombie_vending_nuke': 'p6_zm_al_vending_nuke_on',
                'zombie_vending_nuke_on': 'p6_zm_al_vending_nuke_on'}
# The model each native machine controller sets while its power is off.
OFF_MODELS = {'specialty_armorvest': 'zombie_vending_jugg',
              'specialty_quickrevive': 'zombie_vending_revive',
              'specialty_fastreload': 'zombie_vending_sleight',
              'specialty_rof': 'zombie_vending_doubletap2',
              'specialty_longersprint': 'zombie_vending_marathon',
              'specialty_deadshot': 'zombie_vending_ads',
              'specialty_additionalprimaryweapon': 'zombie_vending_three_gun',
              'specialty_flakjacket': 'zombie_vending_nuke',
              'specialty_grenadepulldeath': 'p6_zm_vending_electric_cherry_off'}
# The source map keeps its own Pack-a-Punch: BO2's controller must not also
# claim the same trigger and machine.
NATIVE_PACK_A_PUNCH = (
    '''    if ( vending_weapon_upgrade_trigger.size >= 1 )
        array_thread( vending_weapon_upgrade_trigger, ::vending_weapon_upgrade );
''',
    '''    if ( isdefined( level._custom_turn_packapunch_on ) )
        level thread [[ level._custom_turn_packapunch_on ]]();
    else
        level thread turn_packapunch_on();
''')


def is_perk_framework(path: str | None) -> bool:
    return bool(path and path.startswith('maps\\_zombiemode_perks'))


def translate_value(value: str) -> str:
    if value in GROUPS:
        return GROUPS[value]
    if value in MACHINE_NAMES:
        return MACHINE_NAMES[value]
    for old, new in PERK_NAMES.items():
        if value == old or value.startswith(old + '_'):
            return new + value[len(old):]
    return value


def translate_literals(source: str) -> str:
    tokens = gsc.tokenize(source)
    for token in tokens:
        if token.kind == gsc.STRING and token.text.startswith('"'):
            token.text = '"' + translate_value(token.text[1:-1]) + '"'
    return gsc.emit(tokens)


def stock_model(name: str, bo2_root: Path) -> str:
    """The shipped BO2 model for a machine model name BO2 raw lacks."""
    if name in STOCK_MODELS and not (bo2_root / f'raw/xmodel/{name}.json').is_file():
        return STOCK_MODELS[name]
    return name


def machine_models(bo2_root: Path) -> set[str]:
    """Every perk machine model the native controllers set. The map must not
    carry a converted WaW model of the same name (it would shadow BO2's)."""
    names = set()
    for module in ('perks', *(f'perk_{m}' for m in MODULES)):
        text = (bo2_root / f'raw/maps/mp/zombies/_zm_{module}.gsc').read_text(encoding='utf-8')
        names |= {stock_model(name, bo2_root) for name in re.findall(r'precachemodel\(\s*"([^"\n]+)"', text, re.I)
                  if 'vending' in name}
    return names


def translate_entities(path: Path, bo2_root: Path | None = None) -> None:
    """Native perk names on the entities; with ``bo2_root`` each perk
    machine also gets the BO2 machine model in place of the WaW one."""
    data = json.loads(path.read_text(encoding='utf-8'))
    machines = {}
    for entity in data['entities']:
        for key, value in entity.items():
            if isinstance(value, str):
                entity[key] = translate_value(value)
        if entity.get('targetname') in ('zombie_vending', 'zombie_vending_upgrade'):
            perk = entity.get('script_noteworthy')
            if perk and perk.removesuffix('_upgrade') not in SUPPORTED_PERKS:
                raise ValueError(f'BO2 stock perks: vending machine uses perk {perk!r}, which BO2 does not have '
                                 f'(unsupported perk; turn "Use BO2 stock perks" off for this map)')
            if entity['targetname'] == 'zombie_vending' and perk in OFF_MODELS and entity.get('target'):
                machines[entity['target']] = OFF_MODELS[perk]
    if bo2_root is not None:
        for entity in data['entities']:
            model = machines.get(entity.get('targetname'))
            if model and entity.get('classname') == 'script_model':
                entity['model'] = stock_model(model, bo2_root)
    path.write_text(json.dumps(data, indent=1), encoding='utf-8')


def native_source(source: str, name: str, out_root: Path, bo2_root: Path) -> str:
    """Keep native controllers intact and register BO2's optional perks.

    Use owned script names for optional modules too, so their registrations
    share the same perk tables as the owned bootstrap rather than cached stock
    script entry points.
    """
    client = name.startswith('clientscripts/')
    for old, new in STOCK_MODELS.items():
        if not (bo2_root / f'raw/xmodel/{old}.json').is_file():
            source = source.replace(f'"{old}"', f'"{new}"')
    if not client:
        for block in NATIVE_PACK_A_PUNCH:
            if block not in source:
                raise ValueError(f'{name}: BO2 Pack-a-Punch start not found')
            source = source.replace(block, "    // waw2bo2: the source map's WaW Pack-a-Punch stays in charge.\n")
    prefix = 'clientscripts' if client else 'maps'
    native = prefix + r'\mp\zombies\_zm_perks'
    owned = prefix + r'\mp\waw\_waw2bo2_perks'
    calls = [f'    level.zombiemode_using_{flag}_perk = 1;' for flag in FLAGS]
    if not client:
        calls.append('    level.waw2bo2_stock_perks = 1;')
    for module in MODULES:
        relative = f'{prefix}/mp/zombies/_zm_perk_{module}.' + ('csc' if client else 'gsc')
        raw = bo2_root / 'raw' / relative
        if not raw.is_file():
            raise ValueError(f'BO2 stock perk runtime missing: {raw}')
        target = out_root / (f'{prefix}/mp/waw/_waw2bo2_perk_{module}' + ('.csc' if client else '.gsc'))
        target.parent.mkdir(parents=True, exist_ok=True)
        module_source = raw.read_text(encoding='utf-8').replace(native, owned)
        for old, new in STOCK_MODELS.items():
            if not (bo2_root / f'raw/xmodel/{old}.json').is_file():
                module_source = module_source.replace(f'"{old}"', f'"{new}"')
        if module == 'electric_cherry':
            # Stock setup uses different target/targetname spellings. WaW
            # scripts follow these links, so retain one matching name.
            module_source = module_source.replace('"vendingelectric_cherry"', '"vending_electric_cherry"')
            module_source = module_source.replace('"vending_electriccherry"', '"vending_electric_cherry"')
        target.write_text(module_source, encoding='utf-8')
        module_path = prefix + rf'\mp\waw\_waw2bo2_perk_{module}'
        calls.append(f'    {module_path}::enable_{module}_perk_for_level();')
    script = gsc.parse(source, name)
    init = script.functions.get('init')
    if init is None:
        raise ValueError(f'{name}: BO2 perk initializer missing')
    script.tokens[init.body_open].text += '\n' + '\n'.join(calls) + '\n'
    return gsc.emit(script.tokens)


def asset_lines(out_root: Path) -> list[str]:
    """Explicit native perk dependencies, so missing DLC assets fail linking."""
    entries = set()
    kinds = {'precacheitem': 'weapon', 'precachemodel': 'xmodel',
             'precacheshader': 'material', 'loadfx': 'fx'}
    paths = [out_root / 'maps/mp/waw/_waw2bo2_perks.gsc',
             *(out_root / 'maps/mp/waw').glob('_waw2bo2_perk_*.gsc'),
             *(out_root / 'clientscripts/mp/waw').glob('_waw2bo2_perk_*.csc')]
    for path in paths:
        source = path.read_text(encoding='utf-8')
        for call, asset in re.findall(r'\b(precacheitem|precachemodel|precacheshader|loadfx)\s*\(\s*"([^"\n]+)"',
                                      source, re.I):
            entries.add(kinds[call.lower()] + ',' + asset)
    return sorted(entries)
