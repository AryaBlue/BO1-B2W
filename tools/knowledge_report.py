"""Rank the converter's untranslated features across every map it has seen.

Reads knowledge ledgers (one observation per map, written by each build),
failure bundles and stage reports, and prints the gaps shared by the most maps.

    python tools/knowledge_report.py                      # the user's build ledger
    python tools/knowledge_report.py --bundle x.zip       # add a failure bundle
    python tools/knowledge_report.py --report path/bridge_stage.report.json
    python tools/knowledge_report.py --write catalog/knowledge.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waw2bo2 import knowledge  # noqa: E402
from waw2bo2.launcher import Settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ledger', type=Path, action='append', default=[],
                        help='knowledge ledger folder (default: <build folder>/knowledge)')
    parser.add_argument('--bundle', type=Path, action='append', default=[], help='failure bundle zip')
    parser.add_argument('--report', type=Path, action='append', default=[],
                        help='a bridge_stage.report.json of a staged map (its project names the map)')
    parser.add_argument('--record', action='store_true',
                        help='also store bundle/report observations in the first ledger')
    parser.add_argument('--write', type=Path, help='write the aggregate summary as JSON')
    parser.add_argument('--top', type=int, default=40)
    args = parser.parse_args()
    ledgers = args.ledger or [Path(Settings().work) / 'knowledge']
    extra = [knowledge.from_bundle(b) for b in args.bundle]
    for path in args.report:
        report = json.loads(path.read_text(encoding='utf-8'))
        extra.append(knowledge.observation(report, source=report.get('project') or path.parent.name,
                                           project=report.get('project', ''), outcome='staged'))
    if args.record:
        for obs in extra:
            knowledge.record(ledgers[0], obs)
    seen = {obs['map']: obs for obs in knowledge.load(*ledgers)}
    seen.update({obs['map']: obs for obs in extra})
    summary = knowledge.aggregate(list(seen.values()))
    print(f"{summary['maps']} maps: {summary['outcomes']}")
    for step, maps in summary['failed_steps'].items():
        print(f'failed at {step}: {", ".join(maps)}')
    print(f"\n{'maps':>4} {'uses':>5}  gap")
    for gap in summary['gaps'][:args.top]:
        print(f"{len(gap['maps']):>4} {gap['uses']:>5}  {gap['kind']:<14} {gap['symbol']}")
    if summary['stage_errors']:
        print('\nstage errors:')
        for kind, maps in list(summary['stage_errors'].items())[:args.top]:
            print(f'{len(maps):>4}  {kind}')
    if args.write:
        args.write.write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
