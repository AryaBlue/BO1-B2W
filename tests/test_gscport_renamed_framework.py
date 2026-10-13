import tempfile
import unittest
from pathlib import Path

from waw2bo2 import gscport
from waw2bo2.t6api import T6Api


FRAMEWORK = r'''
main() {
    maps\_load::main();
    maps\hooks::init();
    level thread maps\hooks::background();
    thread maps\hooks::unbound();
    flag_wait("all_players_connected");
    level thread round_start();
}
init_levelvars() {}
round_start() {}
round_think() {}
onPlayerConnect() {}
player_damage_override() {}
init_strings() { level.custom_hint = "source hint"; }
'''


class RenamedFrameworkTests(unittest.TestCase):
    def sources(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return gscport.Sources([root], [], None), root

    def test_renamed_framework_uses_existing_override_hooks_and_native_startup(self):
        sources, root = self.sources({
            'maps/test.gsc': r'main(){ before(); maps\wave_rules::main(); after(); } before(){} after(){}',
            'maps/wave_rules.gsc': FRAMEWORK,
            'maps/hooks.gsc': 'init(){} background(){ wait 1; } unbound(){}',
            'maps/_loadout.gsc': 'init_loadout(){} give_model(){}',
        })
        original = dict(sources.text)
        report = gscport.port_map(sources, T6Api({}, {}), 'test', root / 'out')
        main = (root / 'out/maps/mp/waw/test.gsc').read_text()
        pre, post = main.split('waw_main_post()', 1)
        self.assertIn('before()', pre)
        self.assertIn('after()', post)
        self.assertNotIn('wave_rules::main', main)
        self.assertIn('level thread maps\\mp\\waw\\hooks::background();', post)
        self.assertIn('thread maps\\mp\\waw\\hooks::unbound();', post)
        self.assertLess(post.index('hooks::init();'), post.index('initial_players_connected'))
        core = (root / 'out/maps/mp/waw/_waw2bo2_core.gsc').read_text()
        self.assertIn('source hint', core)
        self.assertEqual(report.errors, [])
        self.assertEqual(sources.text, original)
        self.assertEqual(report.rewrites[r'framework startup maps\wave_rules -> maps\_zombiemode'], 1)

    def test_alias_normalizes_includes_calls_and_pointers_with_original_provenance(self):
        sources, _ = self.sources({
            'maps/test.gsc': r'main(){ maps\wave_rules::main(); }',
            'maps/wave_rules.gsc': FRAMEWORK,
            'maps/helper.gsc': '#include maps\\wave_rules;\nf(){ maps\\wave_rules::init_strings(); '
                               'level.callback = maps\\wave_rules::init_strings; }',
        })
        provenance = sources.origin[r'maps\wave_rules.gsc']
        self.assertEqual(sources.bind_zombie_framework(r'maps\test'),
                         {r'maps\wave_rules': gscport.ZOMBIEMODE})
        text = sources.text[r'maps\helper.gsc']
        self.assertEqual(text.count(r'maps\_zombiemode'), 3)
        self.assertNotIn('wave_rules', text)
        self.assertEqual(sources.origin[gscport.ZOMBIEMODE + '.gsc'], provenance)

    def test_file_name_alone_does_not_establish_framework_role(self):
        sources, _ = self.sources({
            'maps/test.gsc': r'main(){ maps\custom_zombiemode::main(); }',
            'maps/custom_zombiemode.gsc': 'main(){ flag_wait("all_players_connected"); }',
        })
        self.assertEqual(sources.bind_zombie_framework(r'maps\test'), {})

    def test_multiple_startup_frameworks_fail_without_guessing(self):
        sources, _ = self.sources({
            'maps/test.gsc': r'main(){ maps\rules_a::main(); maps\rules_b::main(); }',
            'maps/rules_a.gsc': FRAMEWORK, 'maps/rules_b.gsc': FRAMEWORK,
        })
        with self.assertRaisesRegex(ValueError, 'multiple zombie startup frameworks'):
            sources.bind_zombie_framework(r'maps\test')


if __name__ == '__main__':
    unittest.main()
