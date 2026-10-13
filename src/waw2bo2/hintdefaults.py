"""Translate the WaW engine's default use prompt before authored scripts run."""
import json
from pathlib import Path


def source(project: Path):
    path = project / 'BSP/entities.json'
    entities = json.loads(path.read_text(encoding='utf-8'))['entities'] if path.exists() else []
    groups = {}
    for entity in entities:
        if entity.get('classname') == 'trigger_use' and entity.get('targetname'):
            groups.setdefault(entity['targetname'], []).append(entity)
    names = sorted(name for name, group in groups.items()
                   if all(not any(entity.get(field) for field in ('hintstring', 'script_hint')) for entity in group))
    lines = ['// WaW default use prompts; source scripts may replace or clear them.', 'init()', '{']
    if names:
        lines += ['    precachestring(&"PLATFORM_HOLD_TO_USE");']
    for name in names:
        lines += [f'    triggers = getentarray({json.dumps(name)}, "targetname");',
                  '    for (i = 0; i < triggers.size; i++)',
                  '        if (triggers[i].classname == "trigger_use")',
                  '            triggers[i] sethintstring(&"PLATFORM_HOLD_TO_USE");']
    return '\n'.join(lines + ['}', ''])
