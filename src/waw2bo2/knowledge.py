"""Cross-map conversion knowledge: what each converted map needed and what the
converter could not translate yet.

Every build records one observation per map (stage report gaps, reported
fallbacks and the step that failed). Observations accumulate in a ledger, one
file per map, so the converter's gaps are ranked by how many maps share them
instead of being rediscovered map by map. The ledger is evidence, never a
switch: no conversion decision reads it. Failure bundles (diagnostics.py)
carry the same stage report, so maps converted on other machines can be
ingested too.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import time
import zipfile

SCHEMA = 1
REPORT_NAME = 'bridge_stage.report.json'

_ARITY = re.compile(r'^(?P<name>\w+)/(?P<argc>\d+)args\((?P<why>.*)\)$')
_XANIM = re.compile(r'^(?P<name>\S+) \(animtree (?P<tree>[^:]+): (?P<why>.*)\)$')
_CSC = re.compile(r'^(?P<name>\S+) in client listener (?P<listener>\S+)')
_TAG = re.compile(r'^([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b')
_STEP = re.compile(r'^== (\d+[a-z]?)\. (.*)$', re.M)


def classify(entry: str) -> tuple[str, str]:
    """(kind, symbol) of a stage report ``unsupported`` key."""
    head, _, rest = entry.partition(' ')
    if head == 'GSC':
        arity = _ARITY.match(rest)
        if arity:
            return 'gsc_arity', f"{arity['name']}/{arity['argc']}"
        return ('gsc_framework' if '::' in rest else 'gsc_builtin'), rest.lower()
    if head == 'XANIM':
        xanim = _XANIM.match(rest)
        return ('xanim_missing', f"{xanim['tree']}::{xanim['name']}") if xanim else ('xanim', rest)
    if head == 'CSC':
        csc = _CSC.match(rest)
        return 'csc_builtin', (csc['name'].lower() if csc else rest)
    return head.lower() or 'other', rest


def error_kind(text: str) -> str:
    """Stable category of a stage error: its leading words, without asset names."""
    tag = _TAG.match(text)
    if tag:
        return tag[1]
    words = []
    for word in re.split(r'\s+', text.split(':', 1)[0].strip()):
        if re.search(r'[\\/.]|\d', word) or (words and word.islower() and '_' in word):
            break
        words.append(word.lower())
        if len(words) == 3:
            break
    return ' '.join(words) or 'other'


def map_key(source: str) -> str:
    """Ledger key of a source map: the fastfile stem plus a short path digest,
    so two maps named alike in different folders keep separate records."""
    path = Path(source)
    digest = hashlib.sha1(str(path).lower().encode('utf-8')).hexdigest()[:8]
    return f'{path.stem.lower()}_{digest}'


def failed_step(log: str) -> str | None:
    """The last ``== N. step`` banner of a build console before its failure."""
    steps = _STEP.findall(log or '')
    return f'{steps[-1][0]}. {steps[-1][1]}' if steps else None


def observation(report: dict | None, *, source: str, project: str = '', version: str = '',
                outcome: str = 'unknown', step: str | None = None, error: str = '') -> dict:
    """One map's observation from its stage report (None when staging never wrote one)."""
    report = report or {}
    scripts = report.get('scripts') or {}
    gaps: dict[str, dict[str, int]] = defaultdict(dict)
    for entry, where in (scripts.get('unsupported') or {}).items():
        kind, symbol = classify(entry)
        gaps[kind][symbol] = gaps[kind].get(symbol, 0) + max(1, len(where or []))
    errors = Counter(error_kind(e) for e in [*report.get('errors', []), *scripts.get('errors', [])])
    tags = Counter(tag[1] for w in report.get('warnings', []) if (tag := _TAG.match(w)))
    return {
        'schema': SCHEMA,
        'map': map_key(source),
        'source': Path(source).name,
        'project': project or report.get('project', ''),
        'converter_version': version,
        'recorded': time.strftime('%Y-%m-%d'),
        'outcome': outcome,
        'failed_step': step,
        'error': error[-2000:],
        'gaps': {kind: dict(sorted(symbols.items())) for kind, symbols in sorted(gaps.items())},
        'stage_errors': dict(errors.most_common()),
        'reported': dict(tags.most_common()),
        'scripts_ported': len(scripts.get('ported', [])),
        'functions_extracted': len(scripts.get('extracted', [])),
    }


def record(ledger: Path, obs: dict) -> Path:
    ledger.mkdir(parents=True, exist_ok=True)
    path = ledger / f"{obs['map']}.json"
    path.write_text(json.dumps(obs, indent=1, sort_keys=False) + '\n', encoding='utf-8')
    return path


def load(*ledgers: Path) -> list[dict]:
    """Observations of every map, the newest record of a map winning."""
    found: dict[str, dict] = {}
    for ledger in ledgers:
        for path in sorted(Path(ledger).glob('*.json')) if Path(ledger).is_dir() else ():
            try:
                obs = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if obs.get('schema') != SCHEMA:
                continue
            old = found.get(obs['map'])
            if old is None or obs.get('recorded', '') >= old.get('recorded', ''):
                found[obs['map']] = obs
    return list(found.values())


def aggregate(observations: list[dict]) -> dict:
    """Gaps ranked by the number of maps sharing them: the converter's backlog."""
    gaps: dict[tuple[str, str], dict] = {}
    errors: dict[str, set[str]] = defaultdict(set)
    steps: dict[str, set[str]] = defaultdict(set)
    outcomes = Counter()
    for obs in observations:
        name = obs.get('source') or obs['map']
        outcomes[obs.get('outcome', 'unknown')] += 1
        for kind, symbols in obs.get('gaps', {}).items():
            for symbol, uses in symbols.items():
                gap = gaps.setdefault((kind, symbol), {'kind': kind, 'symbol': symbol, 'maps': [], 'uses': 0})
                gap['maps'].append(name)
                gap['uses'] += uses
        for kind in obs.get('stage_errors', {}):
            errors[kind].add(name)
        if obs.get('failed_step'):
            steps[obs['failed_step']].add(name)
    ranked = sorted(gaps.values(), key=lambda g: (-len(g['maps']), -g['uses'], g['kind'], g['symbol']))
    for gap in ranked:
        gap['maps'] = sorted(gap['maps'])
    return {
        'schema': SCHEMA,
        'maps': len(observations),
        'outcomes': dict(outcomes),
        'gaps': ranked,
        'stage_errors': {k: sorted(v) for k, v in sorted(errors.items(), key=lambda i: (-len(i[1]), i[0]))},
        'failed_steps': {k: sorted(v) for k, v in sorted(steps.items(), key=lambda i: (-len(i[1]), i[0]))},
    }


def known(summary: dict, kind: str, symbol: str) -> list[str]:
    """Maps that already exposed a gap (for "seen in N maps" report lines)."""
    for gap in summary.get('gaps', []):
        if gap['kind'] == kind and gap['symbol'] == symbol:
            return gap['maps']
    return []


def from_bundle(bundle: Path) -> dict | None:
    """Observation from a failure bundle (diagnostics.create_bundle); it carries
    the stage report when staging got far enough to write one."""
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        summary = json.loads(archive.read('summary.json')) if 'summary.json' in names else {}
        console = archive.read('console.log').decode('utf-8', 'replace') if 'console.log' in names else ''
        reports = [n for n in names if n.endswith('/' + REPORT_NAME)]
        report = json.load(io.TextIOWrapper(archive.open(reports[0]), encoding='utf-8')) if reports else None
    settings = summary.get('settings') or {}
    source = settings.get('fastfile') or settings.get('project') or bundle.stem
    return observation(report, source=source, project=settings.get('project', ''),
                       version=summary.get('version', ''), outcome='failed',
                       step=failed_step(console), error=summary.get('error', ''))
