import tempfile
import unittest
from pathlib import Path
from waw2bo2 import gsc, gscport, zombiebehavior


class SourceChaseTests(unittest.TestCase):
    def test_native_spawn_event_reaches_both_chase_decisions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            definition = gscport.API['zombie_runtime']
            native = root / 'bo2/raw/maps/mp/zombies/_zm_spawner.gsc'
            native.parent.mkdir(parents=True)
            native.write_text(
                'zombie_spawn_init(){ self init_zombie_run_cycle(); self thread zombie_think(); }'
                'do_zombie_spawn(){spot=random(spots);}'
                'should_skip_teardown(native_result){return false;}'
                'zombie_think(){native_result=undefined; self waittill("risen",native_result);'
                'if(!isdefined(native_result)&&isdefined(self.target)&&self.target!=""){go_window();}}')
            movement = root / 'bo2/raw/maps/mp/animscripts/zm_run.gsc'
            movement.parent.mkdir(parents=True)
            movement.write_text('setanimstatefromspeed(){self [[self.setanimstatefromspeed]]();}')
            out = root / 'out/maps/mp/waw'
            out.mkdir(parents=True)
            (out / '_waw2bo2_zombie_behavior.gsc').write_text('init(){}')
            (out / '_waw2bo2_source_chase_policy.gsc').write_text('should_chase(result){return false;}')
            zombiebehavior.stage_native_support(root / 'out', root / 'bo2', definition)
            owned = (out / '_waw2bo2_spawner.gsc').read_text()
            self.assertEqual(owned.count('::source_chases( native_result )'), 2)
            self.assertNotIn('::source_chases()', owned)
            self.assertIn('self waittill("risen",native_result)', owned)

    def test_riser_event_local_is_a_policy_argument_not_an_unbound_local(self):
        for variable in ('rise_struct_string', 'authored_spawn_result'):
            with self.subTest(variable=variable), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / 'maps').mkdir()
                (root / 'maps/_zombiemode_spawner.gsc').write_text(
                    f'zombie_think(){{ {variable}=undefined; '
                    f'if(self.riser){{self waittill("risen", {variable});}} '
                    'if(isdefined(self.script_forcegoal)&&self.script_forcegoal){go_window();}'
                    f'else if(isdefined({variable}) && {variable}=="riser_door"){{go_window();}}'
                    f'else if(isdefined({variable}) && {variable}=="find_flesh"){{'
                    'self zombie_setup_attack_properties();self thread find_flesh();}}')
                definition = gscport.API['zombie_runtime']
                policy = zombiebehavior.source_chase_policy(gscport.Sources([root], [], None), definition)
                self.assertEqual(gsc.parse(policy, 'policy').functions['should_chase'].params, [variable])
                self.assertNotIn('waittill', policy)
                self.assertNotIn(f'{variable}=undefined', policy)
                self.assertLess(policy.index('script_forcegoal'), policy.index('riser_door'))
                self.assertIn(f'{variable}=="find_flesh")' + '{ return true; }', policy)
                runtime = zombiebehavior.runtime_source(definition, None, chase_function='policy::should_chase')
                self.assertIn('source_chases( rise_result )', runtime)
                self.assertIn('self policy::should_chase( rise_result )', runtime)

    def test_source_map_and_actor_guards_keep_forced_goal_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'maps').mkdir()
            (root / 'maps/_zombiemode_spawner.gsc').write_text(
                'zombie_think(){'
                'if(isdefined(self.script_forcegoal)&&self.script_forcegoal){self go_window();}'
                'else if(level.script=="custom_swamp" && isdefined(self.script_string) && '
                '(self.script_string=="riser" || self.script_string=="custom_chaser")) {'
                'self zombie_setup_attack_properties();'
                'if(isdefined(self.target)){self setgoalnode(getnode(self.target,"targetname"));}'
                'self thread find_flesh(); return;}'
                'else {self go_window();}}')
            source = zombiebehavior.source_chase_policy(gscport.Sources([root], [], None), gscport.API['zombie_runtime'])
            self.assertIn('if(isdefined(self.script_forcegoal)&&self.script_forcegoal){ return false; }', source)
            self.assertIn('level.script=="custom_swamp"', source)
            self.assertIn('self.script_string=="custom_chaser"', source)
            self.assertIn('{ return true; }', source)
            self.assertIn('else{ return false; }', source)
            self.assertNotIn('setgoalnode', source)
            self.assertLess(source.index('script_forcegoal'), source.index('custom_swamp'))

    def test_unrelated_find_flesh_reference_is_not_a_spawn_routing_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'maps').mkdir()
            (root / 'maps/_zombiemode_spawner.gsc').write_text('zombie_think(){if(self.dead){find_flesh();}}')
            self.assertIsNone(zombiebehavior.source_chase_policy(gscport.Sources([root], [], None), gscport.API['zombie_runtime']))
