import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from waw2bo2 import knowledge


REPORT = {
    'project': 'zm_test_waw',
    'errors': ['material mc/foo_bar: no WaW source materials/mc/foo_bar.json in any zone dump'],
    'warnings': ['BO2_FALLBACK xmodel arms -> bo2_arms: absent from WaW', 'path nodes: 10 nodes'],
    'scripts': {
        'ported': ['maps/a', 'maps/b'],
        'extracted': ['x'],
        'errors': [],
        'unsupported': {
            'GSC dospawn': ['a.gsc:1', 'a.gsc:9'],
            'GSC maps\\_collectibles::has_collectible': ['b.gsc:3'],
            'GSC moveto/1args(T6 takes 2-4)': ['c.gsc:4'],
            'XANIM scripted_talking (animtree generic_human: no WaW xanim)': ['d.gsc:2'],
            'CSC println in client listener effects_init_thread (client-only)': ['e.csc:1'],
        },
    },
}


class KnowledgeTests(unittest.TestCase):
    def test_classify_report_entries(self):
        assert knowledge.classify('GSC SetAnimKnob') == ('gsc_builtin', 'setanimknob')
        assert knowledge.classify('GSC maps\\_x::y') == ('gsc_framework', 'maps\\_x::y')
        assert knowledge.classify('GSC moveto/1args(T6 takes 2-4)') == ('gsc_arity', 'moveto/1')
        assert knowledge.classify('XANIM body (animtree generic_human: no WaW xanim)') == \
            ('xanim_missing', 'generic_human::body')
        assert knowledge.classify('CSC SetVolFog in client listener dog_start (client-only)') == \
            ('csc_builtin', 'setvolfog')

    def test_error_kinds_drop_asset_names(self):
        assert knowledge.error_kind('material mc/foo: no source') == 'material'
        assert knowledge.error_kind('xmodel foo_bar: xmodel/foo_bar.json missing') == 'xmodel'
        assert knowledge.error_kind('MODEL_GEOMETRY_MISSING x: y') == 'MODEL_GEOMETRY_MISSING'
        assert knowledge.error_kind('path nodes: bad') == 'path nodes'

    def test_observation_and_aggregate_rank_shared_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a = knowledge.observation(REPORT, source='C:/maps/a/nazi_zombie_a.ff', outcome='built')
            other = dict(REPORT, scripts={'unsupported': {'GSC dospawn': ['z.gsc:1']}})
            b = knowledge.observation(other, source='C:/maps/b/nazi_zombie_b.ff', outcome='failed',
                                      step='compile-scripts')
            assert a['gaps']['gsc_builtin'] == {'dospawn': 2}
            assert a['stage_errors'] == {'material': 1}
            assert a['reported'] == {'BO2_FALLBACK': 1}
            for obs in (a, b):
                knowledge.record(tmp_path, obs)
            summary = knowledge.aggregate(knowledge.load(tmp_path))
            top = summary['gaps'][0]
            assert (top['kind'], top['symbol'], top['uses']) == ('gsc_builtin', 'dospawn', 3)
            assert top['maps'] == ['nazi_zombie_a.ff', 'nazi_zombie_b.ff']
            assert summary['failed_steps'] == {'compile-scripts': ['nazi_zombie_b.ff']}
            assert knowledge.known(summary, 'gsc_builtin', 'dospawn') == top['maps']

    def test_same_named_maps_in_different_folders_stay_apart(self):
        assert knowledge.map_key('C:/a/nazi_zombie_x.ff') != knowledge.map_key('C:/b/nazi_zombie_x.ff')

    def test_failure_bundle_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle = tmp_path / 'b.zip'
            with zipfile.ZipFile(bundle, 'w') as archive:
                archive.writestr('summary.json', json.dumps({'version': '0.2.15', 'error': 'boom',
                                                             'settings': {'fastfile': 'C:/m/nazi_zombie_q.ff',
                                                                          'project': 'zm_q_waw'}}))
                archive.writestr('console.log', '== 0. reusing\n== 2. staging zm_q_waw\nTraceback')
                archive.writestr('build/stage/zone_raw/zm_q_waw/bridge_stage.report.json', json.dumps(REPORT))
            obs = knowledge.from_bundle(bundle)
            assert obs['outcome'] == 'failed' and obs['failed_step'] == '2. staging zm_q_waw'
            assert obs['source'] == 'nazi_zombie_q.ff' and obs['gaps']['gsc_framework']


if __name__ == '__main__':
    unittest.main()
