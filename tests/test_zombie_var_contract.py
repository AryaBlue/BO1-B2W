import tempfile
import unittest
from pathlib import Path
from waw2bo2 import gscport, t6bridge
from waw2bo2.t6api import T6Api


class ZombieVarContractTests(unittest.TestCase):
    def test_waw_float_flag_does_not_resolve_to_bo2_table_column(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'maps').mkdir()
            (root / 'maps/test.gsc').write_text(
                '#include maps\\_zombiemode_utility;\n'
                'main(){set_zombie_var("travel",0.5,undefined,true);}')
            api = T6Api(builtins={}, scripts={r'maps\mp\zombies\_zm_utility': {'set_zombie_var': 5}})
            tr = gscport.Translator(gscport.Sources([root], [], None), api, gscport.PortReport())
            text = tr.translate(r'maps\test')
            self.assertIn('waw_set_zombie_var("travel",0.5,undefined,true)', text)

    def test_only_source_table_overrides_are_staged_with_root_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            roots = [Path(folder) / 'custom', Path(folder) / 'stock']
            for root, value in zip(roots, ('0.5', '0.11')):
                (root / 'mp').mkdir(parents=True)
                (root / 'mp/zombiemode.csv').write_text('travel,' + value + '\nempty,\n')
            values = t6bridge.source_zombie_var_overrides(roots)
            self.assertEqual(values, {'travel': '0.5'})
            generated = gscport.assets_source({}, zombie_var_overrides=values)
            self.assertIn('level.waw_zombie_var_overrides["travel"] = "0.5";', generated)
            self.assertEqual(t6bridge.source_zombie_var_overrides([]), {})
