import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from waw2bo2 import t6bridge, techsets


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


class ShadowOnlySurfaceTests(unittest.TestCase):
    def test_game_flag_one_is_only_cast_shadow(self):
        # measured: mc/mtl_mangrove1_gobo (Shi No Numa) and stock T6 shadowcaster
        self.assertTrue(techsets.only_casts_shadow({'gameFlags': ['1', '4', '10', 'CASTS_SHADOW']}))
        self.assertFalse(techsets.only_casts_shadow({'gameFlags': ['10', 'CASTS_SHADOW']}))
        self.assertFalse(techsets.only_casts_shadow({}))

    def _stage(self, root: Path, primitives_materials):
        source, output = root / 'source', root / 'output'
        materials = ['mc/bark', 'mc/leaf', 'mc/gobo']
        _write(source / 'materials/mc/bark.json', {'techniqueSet': 'mc_l_sm_r0c0', 'gameFlags': ['10']})
        _write(source / 'materials/mc/leaf.json', {'techniqueSet': 'mc_treecanopy', 'gameFlags': ['4']})
        _write(source / 'materials/mc/gobo.json', {'techniqueSet': 'mc_l_sm_t0c0', 'gameFlags': ['1', '4']})
        meshes = [{'primitives': [{'attributes': {'POSITION': 0}, 'material': m}]} for m in primitives_materials]
        _write(source / 'tree.gltf', {
            'materials': [{'name': n} for n in materials], 'meshes': meshes,
            'nodes': [{'name': f'surf{i}', 'mesh': i} for i in range(len(meshes))],
            'accessors': [{'min': [0, 0, 0], 'max': [1, 1, 1]}]})
        _write(source / 'xmodel/tree.json', {'lods': [{'file': 'tree.gltf', 'distance': 100}]})
        (root / 'partclassification.csv').write_text('')
        report = t6bridge.StageReport('example')
        with patch.object(t6bridge, 'OAT_T6_RAW', root):
            t6bridge.stage_models(report, SimpleNamespace(static_models=[]), 'example', source, output,
                                  {'tree'}, [source])
        return report, json.loads((output / 'tree.gltf').read_text())

    def test_model_lod_drops_gobo_cards(self):
        with tempfile.TemporaryDirectory() as folder:
            report, gltf = self._stage(Path(folder), [0, 1, 2])
        self.assertEqual([[p['material'] for p in m['primitives']] for m in gltf['meshes']], [[0], [1], []])
        self.assertEqual(['mesh' in n for n in gltf['nodes']], [True, True, False])
        self.assertEqual(report.content['shadow_only_model_surfaces'][0]['materials'], ['mc/gobo'])

    def test_model_made_only_of_shadow_surfaces_is_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            report, gltf = self._stage(Path(folder), [2])
        self.assertEqual(gltf['meshes'][0]['primitives'][0]['material'], 2)
        self.assertNotIn('shadow_only_model_surfaces', report.content)


if __name__ == '__main__':
    unittest.main()
