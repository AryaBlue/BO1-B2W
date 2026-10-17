import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from waw2bo2 import t6bridge


def _surface(index, material, brush_model, world_vert_format):
    return SimpleNamespace(index=index, material=material, brush_model=brush_model,
                           world_vert_format=world_vert_format)


class BrushModelBlendTests(unittest.TestCase):
    """Shi No Numa's Flogger (brush model *3) carries *6n_83: berlin_trim_metal
    plus a blood splat. In T6 it drew black (lit and fullbright), while blends
    with that splat layer on static world surfaces draw correctly."""

    def _run(self, surfaces, defined):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in defined:
                path = root / 'materials' / (name + '.json')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({'techniqueSet': 'wc_l_sm_r0c0n0s0'}))
            names = ['clip_%d' % i for i in range(84)]
            names[6], names[83] = 'berlin_trim_metal_noscorch', 'decal_bloodsplat8'
            clip = SimpleNamespace(materials=[SimpleNamespace(name=n) for n in names])
            report = t6bridge.StageReport('example')
            white = t6bridge.brush_blends_to_base_layer(report, SimpleNamespace(surfaces=surfaces), clip, [root])
        return report, white

    def test_brush_model_blend_draws_its_base_layer(self):
        flogger = _surface(5, '*6n_83', 3, 1)
        world = _surface(6, '*6n_83', 0, 1)
        plain = _surface(7, 'wc/berlin_trim_metal_noscorch', 3, 0)
        report, white = self._run([flogger, world, plain], ['wc/berlin_trim_metal_noscorch'])
        self.assertEqual((flogger.material, flogger.world_vert_format), ('wc/berlin_trim_metal_noscorch', 0))
        # static world blends keep their layers (T6 binds vd1 for them)
        self.assertEqual((world.material, world.world_vert_format), ('*6n_83', 1))
        self.assertEqual(white, frozenset({5}))
        self.assertTrue(any('BRUSH_MODEL_BLEND_BASE_LAYER 1' in w for w in report.warnings))

    def test_blend_is_kept_when_its_base_material_is_not_defined(self):
        flogger = _surface(5, '*6n_83', 3, 1)
        report, white = self._run([flogger], [])
        self.assertEqual(flogger.material, '*6n_83')
        self.assertEqual(white, frozenset())
        self.assertTrue(any('BRUSH_MODEL_BLEND_KEPT' in w for w in report.warnings))


if __name__ == '__main__':
    unittest.main()
