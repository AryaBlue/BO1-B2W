import tempfile
import unittest
from pathlib import Path
from collections import Counter
from waw2bo2 import entities, gsc, gscport, zombiebehavior
from waw2bo2.t6api import T6Api


class ZombieBehaviorTests(unittest.TestCase):
    def test_source_speed_body_and_dependencies_are_translated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {
                'maps/test.gsc': 'main(){ maps\\_zombiemode::main(); }',
                'maps/_zombiemode.gsc': 'main(){}',
                'maps/_zombiemode_spawner.gsc':
                    'set_run_speed(){ if(level.round_number >= 1) self.zombie_move_speed = choose(); } '
                    'choose(){ return "sprint"; }',
                'maps/_loadout.gsc': 'init_loadout(){} give_model(){}',
            }
            for name, text in files.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(text)
            report = gscport.port_map(gscport.Sources([root], [], None), T6Api({}, {}), 'test', root / 'out')
            core = (root / 'out/maps/mp/waw/_waw2bo2_core.gsc').read_text()
            self.assertIn('if(level.round_number >= 1)', core)
            self.assertIn('return "sprint";', core)
            self.assertIn('maps\\_zombiemode_spawner::choose', report.extracted)
            runtime = (root / 'out/maps/mp/waw/_waw2bo2_zombie_behavior.gsc').read_text()
            self.assertIn('::zombiemode_spawner__set_run_speed()', runtime)
            self.assertIn('set_zombie_run_cycle( self.zombie_move_speed )', runtime)
            main = (root / 'out/maps/mp/waw/test.gsc').read_text()
            self.assertLess(main.index('_waw2bo2_zombie_behavior::init()'), main.index('initial_players_connected'))
            self.assertFalse(report.errors)

    def test_owned_callback_adapts_location_and_speed_before_think(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            native = root / 'bo2/raw/maps/mp/zombies/_zm_spawner.gsc'
            native.parent.mkdir(parents=True)
            native.write_text('#include maps\\mp\\zombies\\_zm_spawner;\n'
                'zombie_spawn_init(animname_set){ self init_zombie_run_cycle(); self thread zombie_think(); }\n'
                'do_zombie_spawn(){ spot=random(spots); self.spawn_point = spot; }\n'
                'zombie_think(){ wait 1; }')
            runtime = root / 'out/maps/mp/waw/_waw2bo2_zombie_behavior.gsc'
            runtime.parent.mkdir(parents=True)
            runtime.write_text(zombiebehavior.runtime_source(gscport.API['zombie_runtime'], None))
            original = native.read_text()
            zombiebehavior.stage_native_support(root / 'out', root / 'bo2', gscport.API['zombie_runtime'])
            text = (runtime.parent / '_waw2bo2_spawner.gsc').read_text()
            gsc.parse(text, 'owned')
            self.assertLess(text.index('::bind_spawn_location()'), text.index('::select_speed()'))
            self.assertLess(text.index('::select_speed()'), text.index('self thread zombie_think()'))
            self.assertLess(text.index('spot = self.spawn_point_override'), text.index('self.spawn_point = spot'))
            self.assertIn('#include maps\\mp\\waw\\_waw2bo2_spawner;', text)
            self.assertEqual(native.read_text(), original)
            self.assertIn('level.zombie_spawn_locations', runtime.read_text())
            self.assertIn('self.script_string == "riser"', runtime.read_text())

    def test_native_contract_change_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / 'out/maps/mp/waw/_waw2bo2_zombie_behavior.gsc'
            runtime.parent.mkdir(parents=True)
            runtime.write_text('init(){}')
            native = root / 'bo2/raw/maps/mp/zombies/_zm_spawner.gsc'
            native.parent.mkdir(parents=True)
            native.write_text('zombie_spawn_init(){ changed_speed_init(); } do_zombie_spawn(){}')
            with self.assertRaisesRegex(ValueError, 'expected one speed initialization'):
                zombiebehavior.stage_native_support(root / 'out', root / 'bo2', gscport.API['zombie_runtime'])

    def test_spawner_target_survives_on_its_spawn_location(self):
        struct = entities.spawn_struct({'target': 'window_route', 'origin': '1 2 3'}, 'spawn_group', Counter())
        self.assertEqual(struct['target'], 'window_route')


if __name__ == '__main__':
    unittest.main()
