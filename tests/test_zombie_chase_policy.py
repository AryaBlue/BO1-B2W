import tempfile
import unittest
from pathlib import Path
from waw2bo2 import gscport, zombiebehavior


class SourceChaseTests(unittest.TestCase):
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
