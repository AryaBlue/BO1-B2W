import tempfile
import unittest
from pathlib import Path
from collections import Counter
from waw2bo2 import entities, gsc, gscport, zombiebehavior
from waw2bo2.t6api import T6Api


class ZombieBehaviorTests(unittest.TestCase):
    def make_movement_callback(self, root):
        path = root / 'bo2/raw/maps/mp/animscripts/zm_run.gsc'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('setanimstatefromspeed(){ self [[ self.setanimstatefromspeed ]]("move", undefined); }')

    def test_round_speed_inputs_follow_source_helpers_before_each_round(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {
                'maps/_zombiemode.gsc': '#include maps\\rules;\n'
                    'round_spawning(){ players=get_players(); for(i=0;i<players.size;i++){ '
                    'players[i].timer=0; } count=prepare(level.round_number); '
                    'while(1){ spawn_zombie(); } }',
                'maps/rules.gsc': 'prepare(round){ switch(round){ case 1: level.low=80; '
                    'level.high=100; break; default: level.low=30; level.high=60; } return round*10; }\n'
                    'choose(){ return randomintrange(level.low,level.high); }',
                'maps/_zombiemode_spawner.gsc': '#include maps\\rules;\n'
                    'set_run_speed(){ value=choose(); if(value>70) self.zombie_move_speed="sprint"; '
                    'else self.zombie_move_speed="run"; }',
            }
            for name, text in files.items():
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
            sources = gscport.Sources([root], [], None)
            state = zombiebehavior.source_speed_state(sources, gscport.API['zombie_runtime'])
            self.assertIn('count=prepare(level.round_number)', state)
            self.assertNotIn('spawn_zombie', state)
            self.assertNotIn('players[i].timer', state)
            gsc.parse(state, 'state')
            runtime = zombiebehavior.runtime_source(gscport.API['zombie_runtime'], 'source::choose',
                                                    speed_state_function='source_state')
            self.assertLess(runtime.index('source_state::prepare_round'), runtime.index('self source::choose'))
            self.assertIn('level.waw_speed_round != level.round_number', runtime)

    def test_stock_round_speed_uses_source_initial_and_previous_round_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, text in {
                'maps/_zombiemode.gsc': 'round_think(){ while(1){ '
                    'level.zombie_move_speed=level.round_number*8; level.round_number++; } }',
                'maps/_zombiemode_spawner.gsc': 'init(){level.zombie_move_speed=1;} '
                    'set_run_speed(){self.zombie_move_speed=randomintrange(level.zombie_move_speed,35);}',
            }.items():
                p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
            state = zombiebehavior.source_speed_state(gscport.Sources([root], [], None), gscport.API['zombie_runtime'])
            tokens = gsc.tokenize(state)
            gscport.rename_level_fields(tokens)
            text = gsc.emit(tokens)
            self.assertIn('level.waw_zombie_move_speed=1', text)
            self.assertIn('level.waw_zombie_move_speed=source_round*8', text)
            self.assertIn('source_round = level.round_number - 1', text)
            self.assertIn('if (level.round_number > 1)', text)
            self.assertNotIn('level.round_number++', text)

    def test_conditional_round_speed_writer_is_not_applied_unconditionally(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, text in {
                'maps/_zombiemode.gsc': 'round_think(){while(1){ '
                    'if(level.round_number>4) level.zombie_move_speed=100; level.round_number++;}}',
                'maps/_zombiemode_spawner.gsc': 'set_run_speed(){self.zombie_move_speed=level.zombie_move_speed;}',
            }.items():
                p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
            with self.assertRaisesRegex(ValueError, 'conditional source speed state'):
                zombiebehavior.source_speed_state(gscport.Sources([root], [], None), gscport.API['zombie_runtime'])

    def test_source_actor_speed_writes_cannot_be_clobbered_by_native_field(self):
        tokens = gsc.tokenize('f(){self.zombie_move_speed="sprint"; '
                              'zombies[i].zombie_move_speed="run"; level.zombie_move_speed=100;}')
        gscport.rename_level_fields(tokens)
        self.assertIn('self.waw_zombie_move_speed="sprint"', gsc.emit(tokens))
        self.assertIn('zombies[i].waw_zombie_move_speed="run"', gsc.emit(tokens))
        runtime = zombiebehavior.runtime_source(gscport.API['zombie_runtime'], 'source::choose')
        self.assertIn('self.zombie_move_speed != self.waw_zombie_move_speed', runtime)
        self.assertIn('self.setanimstatefromspeed = ::source_animstate', runtime)
        self.assertIn('self.waw_previous_speed_callback', runtime)
        self.assertIn('native_request = self.waw_zombie_move_speed', runtime)

    def make_sources(self, root, text):
        path = root / 'maps/_zombiemode.gsc'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return gscport.Sources([root], [], None)

    def test_authored_movement_variants_keep_duplicate_weights(self):
        with tempfile.TemporaryDirectory() as temp:
            sources = self.make_sources(Path(temp), '#using_animtree("human");\n'
                'init_standard_zombie_anims(){ level.scr_anim["zombie"]["sprint1"]=%fast; '
                'level.scr_anim["zombie"]["sprint2"]=%fast; '
                'level.scr_anim["zombie"]["run1"]=%jog; }')
            tree, sets = zombiebehavior.movement_sets(sources, gscport.API['zombie_runtime'])
            self.assertEqual(tree, 'human')
            self.assertEqual(sets, {'sprint': ['fast', 'fast'], 'run': ['jog']})

    def test_movement_initializer_role_is_detected_from_table_assignments(self):
        with tempfile.TemporaryDirectory() as temp:
            sources = self.make_sources(Path(temp), '#using_animtree("human");\n'
                'custom_moves(){level.scr_anim["zombie"]["sprint1"]=%source_sprint; '
                'level.scr_anim["zombie"]["run1"]=%source_run;}')
            tree, sets = zombiebehavior.movement_sets(sources, gscport.API['zombie_runtime'])
            self.assertEqual(tree, 'human')
            self.assertEqual(sets, {'sprint': ['source_sprint'], 'run': ['source_run']})

    def test_conditional_movement_table_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as temp:
            sources = self.make_sources(Path(temp), 'init_standard_zombie_anims(){ '
                'if(level.fast) { level.scr_anim["zombie"]["sprint1"]=%fast; } }')
            with self.assertRaisesRegex(ValueError, 'conditional movement table'):
                zombiebehavior.movement_sets(sources, gscport.API['zombie_runtime'])

    def test_source_clips_bind_owned_server_and_client_states(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = self.make_sources(root, '#using_animtree("human");\n'
                'init_standard_zombie_anims(){ level.scr_anim["zombie"]["sprint1"]=%fast; }')
            raw = root / 'bo2/raw'
            for path, text in {
                'animtrees/zm_nuked_basic.atr': 'body\n{\nstock\n}\n',
                'animstatedefs/zm_nuked_basic.asd': 'zm_move_sprint : notify move_anim\n{\nstock\n}\n'
                    'zm_traverse : aliased\n{\njump stock\n}\n',
            }.items():
                p = raw / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
            out = root / 'out'
            (out / 'xanim').mkdir(parents=True)
            (out / 'xanim/waw_anim_fast').write_bytes(b'original source clip')
            for name in ('aitype/waw_actor.gsc', 'aitype/clientscripts/waw_actor.csc'):
                p = out / name; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('#using_animtree("zm_nuked_basic"); precache(){ use("zm_nuked_basic"); }')
            result = zombiebehavior.stage_actor_movement(sources, out, root / 'bo2', gscport.API['zombie_runtime'])
            self.assertEqual(result['clips'], ['waw_anim_fast'])
            asd = (out / ('animstatedefs/' + zombiebehavior.ACTOR_TREE + '.asd')).read_text()
            self.assertIn('waw_anim_fast', asd)
            self.assertIn('zm_traverse : aliased\n{\njump stock\n}', asd)
            self.assertIn('waw_anim_fast', (out / ('animtrees/' + zombiebehavior.ACTOR_TREE + '.atr')).read_text())
            for p in (out / 'aitype').rglob('*.?sc'):
                self.assertIn(zombiebehavior.ACTOR_TREE, p.read_text())
                self.assertIn('dummy_anim_ref = %waw_anim_fast;', p.read_text())
            self.assertNotIn('waw_anim_fast', (raw / 'animstatedefs/zm_nuked_basic.asd').read_text())

    def test_spawner_sampler_preserves_source_reroll_body(self):
        with tempfile.TemporaryDirectory() as temp:
            sources = self.make_sources(Path(temp), 'round_spawning(){ unrelated(); old_spawn=undefined; '
                'while(1){ spawn_point=level.enemy_spawns[randomint(level.enemy_spawns.size)]; '
                'if(isdefined(old_spawn) && spawn_point==old_spawn){ '
                'spawn_point=level.enemy_spawns[randomint(level.enemy_spawns.size)]; } '
                'old_spawn=spawn_point; spawn_zombie(spawn_point); } }')
            text = zombiebehavior.source_selection(sources, gscport.API['zombie_runtime'])
            gsc.parse(text, 'selection')
            self.assertEqual(text.count('randomint(candidates.size)'), 2)
            self.assertIn('spawn_point==old_spawn', text)
            self.assertNotIn('unrelated', text)
            self.assertNotIn('spawn_zombie', text)

    def test_native_spawner_picks_use_source_sampler(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_movement_callback(root)
            native = root / 'bo2/raw/maps/mp/zombies/_zm_spawner.gsc'
            native.parent.mkdir(parents=True)
            native.write_text('zombie_spawn_init(){ self init_zombie_run_cycle(); self thread zombie_think(); } '
                              'do_zombie_spawn(){spot=random(spots);} zombie_think(){}')
            out = root / 'out/maps/mp/waw'
            out.mkdir(parents=True)
            (out / '_waw2bo2_zombie_behavior.gsc').write_text('init(){}')
            (out / '_waw2bo2_zm.gsc').write_text('round_spawning(){ '
                'spawner=random(level.zombie_spawners); other=random(other_array); }\n'
                'init(){ maps\\mp\\zombies\\_zm_spawner::init(); }\n'
                'zombie_speed_up(){ self set_zombie_run_cycle("walk"); }')
            zombiebehavior.stage_native_support(root / 'out', root / 'bo2', gscport.API['zombie_runtime'])
            text = (out / '_waw2bo2_zm.gsc').read_text()
            self.assertIn('::choose_spawner(level.zombie_spawners)', text)
            self.assertIn('other=random(other_array)', text)
            self.assertIn('maps\\mp\\waw\\_waw2bo2_spawner::init()', text)
            self.assertIn('::refresh_speed("walk")', text)

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
            self.assertIn('native_request = self.waw_zombie_move_speed', runtime)
            self.assertIn('self.waw_zombie_move_speed = zombiemode_spawner__choose()', core)
            main = (root / 'out/maps/mp/waw/test.gsc').read_text()
            self.assertLess(main.index('_waw2bo2_zombie_behavior::init()'), main.index('initial_players_connected'))
            self.assertFalse(report.errors)

    def test_owned_callback_adapts_location_and_speed_before_think(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_movement_callback(root)
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
