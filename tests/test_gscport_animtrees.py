import tempfile
import unittest
from pathlib import Path

from waw2bo2 import gscport, t6bridge
from waw2bo2.t6api import T6Api


class SourceAnimationDependenciesTests(unittest.TestCase):
    def test_portable_script_keeps_each_animation_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'maps').mkdir()
            (root / 'maps/trees.gsc').write_text(
                '#using_animtree("factory");\n'
                'gate() { self useanimtree(#animtree); x = %gate_open; }\n'
                '#using_animtree("native");\n'
                'stock() { self useanimtree(#animtree); x = %native_idle; }\n'
                '#using_animtree("missing");\n'
                'unsupported() { self useanimtree(#animtree); x = %lost; }')
            tr = gscport.Translator(gscport.Sources([root], [], None),
                                   T6Api({}, {}, methods={'useanimtree': (1, 1)}), gscport.PortReport())
            tr.animtrees = {'native'}
            tr.core_animtrees = {'factory': {'gate_open'}}
            result = tr.translate(r'maps\trees')
            self.assertIn('%waw_anim_gate_open', result)
            self.assertIn('%native_idle', result)
            self.assertIn('x = "lost"', result)
            self.assertIn('gate() { self useanimtree(#animtree)', result)
            self.assertIn('stock() { self useanimtree(#animtree)', result)
            self.assertIn('unsupported() { self maps\\mp\\waw\\_waw2bo2_compat::waw_anim_useanimtree', result)

    def test_reachable_functions_keep_their_own_trees_and_source_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source/maps').mkdir(parents=True)
            (root / 'source/xanim').mkdir()
            (root / 'source/maps/test.gsc').write_text(
                'main() { maps\\dlc3_code::script_anims_init(); '
                'level.zombie_anim_override = maps\\dlc3_code::anim_override_func; }')
            text = ('#using_animtree("factory");\n'
                    'script_anims_init() { level.gate_anim = %gate_open; level.play_gate = ::play_gate; }\n'
                    'play_gate() { self useanimtree(#animtree); }\n'
                    '#using_animtree("generic_human");\n'
                    'anim_override_func() { level.attack_anim = %attack; }\n'
                    'unused() { level.unused = %unused_animation; }')
            (root / 'source/maps/dlc3_code.gsc').write_text(text)
            for name in ['gate_open', 'attack', 'unused_animation']:
                (root / 'source/xanim' / name).write_bytes(b'original-' + name.encode())
            sources = gscport.Sources([root / 'source'], [], None)
            api = T6Api({}, {}, methods={'useanimtree': (1, 1)})
            original = sources.get(r'maps\dlc3_code')
            self.assertEqual(original.functions['script_anims_init'].animtree, 'factory')
            self.assertEqual(original.functions['anim_override_func'].animtree, 'generic_human')
            wanted = gscport.discover_animation_dependencies(sources, api, 'test')
            self.assertEqual(wanted, {'factory': {'gate_open'}, 'generic_human': {'attack'}})
            self.assertEqual(gscport.gsc.emit(original.tokens), text)
            trees, assets = t6bridge.stage_core_animtrees(t6bridge.StageReport('test'), sources,
                [root / 'source'], root / 'out', {'generic_human'}, api=api, map_name='test')
            self.assertEqual(trees, wanted)
            self.assertEqual(set(assets), {'waw_anim_gate_open', 'waw_anim_attack'})
            self.assertEqual((root / 'out/xanim/waw_anim_gate_open').read_bytes(), b'original-gate_open')
            self.assertIn('waw_anim_attack', (root / 'out/animtrees/waw2bo2_generic_human.atr').read_text())
            self.assertFalse((root / 'out/xanim/waw_anim_unused_animation').exists())
            port = gscport.port_map(sources, api, 'test', root / 'out', core_animtrees=trees)
            core = (root / 'out/maps/mp/waw/_waw2bo2_core.gsc').read_text()
            self.assertIn('#using_animtree( "waw2bo2_factory" );', core)
            self.assertIn('%waw_anim_gate_open', core)
            self.assertIn('#using_animtree( "waw2bo2_generic_human" );', core)
            self.assertIn('%waw_anim_attack', core)
            self.assertFalse(any('dlc3_code' in k for k in port.unsupported))


class AnimtreeRegistrationTests(unittest.TestCase):
    def test_registration_remains_idempotent_after_perk_client_bootstrap_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gsc, csc = root / 'main.gsc', root / 'main.csc'
            gsc.write_text('main()\n{\n    maps\\mp\\zombies\\_zm::init();\n}\n')
            csc.write_text('main()\n{\n    clientscripts\\mp\\zombies\\_zm::init();\n}\n')
            gscport.hook_bo2_animtrees(gsc, csc, root, ['shared_tree'])
            gscport.hook_bo2_perk_client(csc)
            gscport.hook_bo2_perk_server(gsc)
            server_before = gsc.read_text()
            before = csc.read_text()
            self.assertFalse(gscport.hook_bo2_animtrees(gsc, csc, root, ['shared_tree']))
            self.assertEqual(csc.read_text(), before)
            self.assertEqual(gsc.read_text(), server_before)
            self.assertIn("maps\\mp\\waw\\_waw2bo2_zm::init();\n    maps\\mp\\waw\\_waw2bo2_animtrees::init();", server_before)
            self.assertIn('_waw2bo2_zm::init();\n    clientscripts\\mp\\waw\\_waw2bo2_animtrees::init();', before)

    def test_staged_animtrees_follow_zm_init_on_server_and_client(self):
        # BO2: "Unrecognized animtree '%s'. You may need to call ScriptModelsUseAnimTree()";
        # server and client must register in the same order (both register zm_ally in _zm::init)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gsc, csc = root / "main.gsc", root / "main.csc"
            gsc.write_text("main()\n{\n    maps\\mp\\zombies\\_zm::init();\n    other();\n}\n", encoding="utf-8")
            csc.write_text("main()\n{\n    clientscripts\\mp\\zombies\\_zm::init();\n    other();\n}\n", encoding="utf-8")
            self.assertTrue(gscport.hook_bo2_animtrees(gsc, csc, root, ["nuketown"]))
            self.assertIn("_zm::init();\n    maps\\mp\\waw\\_waw2bo2_animtrees::init();\n    other();",
                          gsc.read_text(encoding="utf-8"))
            self.assertIn("_zm::init();\n    clientscripts\\mp\\waw\\_waw2bo2_animtrees::init();\n    other();",
                          csc.read_text(encoding="utf-8"))
            for script in ("maps/mp/waw/_waw2bo2_animtrees.gsc", "clientscripts/mp/waw/_waw2bo2_animtrees.csc"):
                text = (root / script).read_text(encoding="utf-8")
                self.assertIn('#using_animtree( "nuketown" );', text)
                self.assertIn("scriptmodelsuseanimtree( #animtree );", text)
            self.assertFalse(gscport.hook_bo2_animtrees(gsc, csc, root, ["nuketown"]))
            self.assertFalse(gscport.hook_bo2_animtrees(gsc, csc, root, []))
            # a call left after _load::main by an earlier run moves after _zm::init
            gsc.write_text("main()\n{\n    maps\\mp\\zombies\\_load::main();\n    maps\\mp\\waw\\_waw2bo2_animtrees::init();\n"
                           "    maps\\mp\\zombies\\_zm::init();\n}\n", encoding="utf-8")
            self.assertTrue(gscport.hook_bo2_animtrees(gsc, csc, root, ["nuketown"]))
            text = gsc.read_text(encoding="utf-8")
            self.assertEqual(text.count("_waw2bo2_animtrees::init();"), 1)
            self.assertIn("_zm::init();\n    maps\\mp\\waw\\_waw2bo2_animtrees::init();", text)


if __name__ == "__main__":
    unittest.main()
