import json
from pathlib import Path
import tempfile
import unittest

from waw2bo2 import gsc, gscport, stockperks
from waw2bo2.launcher import Settings, BuildPaths
from waw2bo2.t6api import T6Api


class StockPerkTests(unittest.TestCase):
    def test_option_defaults_off_and_survives_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            self.assertFalse(Settings().bo2_stock_perks)
            Settings(bo2_stock_perks=True).save(path)
            self.assertTrue(Settings.load(path).bo2_stock_perks)
            path.write_text('{"bo2_stock_perks":"true"}')
            self.assertFalse(Settings.load(path).bo2_stock_perks)

    def test_changing_perk_mode_requires_a_matching_build_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(work=tmp, project='zm_sample', fastfile=str(Path(tmp) / 'sample.ff'))
            paths = BuildPaths.for_settings(settings)
            paths.output.mkdir(parents=True)
            for name in ('zm_sample.ff', 'zm_sample.ipak', 'mod.ff', 'mod_load.ff', 'mod.json'):
                (paths.output / name).touch()
            receipt = paths.root / 'build.json'
            receipt.write_text(json.dumps({'project': settings.project}))
            self.assertTrue(paths.complete(settings.project, bo2_stock_perks=False))
            self.assertFalse(paths.complete(settings.project, bo2_stock_perks=True))
            receipt.write_text(json.dumps({'project': settings.project, 'bo2_stock_perks': True}))
            self.assertTrue(paths.complete(settings.project, bo2_stock_perks=True))
            self.assertFalse(paths.complete(settings.project, bo2_stock_perks=False))

    def test_native_purchase_loss_and_client_hud_code_remain_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for prefix, ext in (('maps', 'gsc'), ('clientscripts', 'csc')):
                for module in stockperks.MODULES:
                    path = root / f'bo2/raw/{prefix}/mp/zombies/_zm_perk_{module}.{ext}'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f'enable_{module}_perk_for_level() {{}}')
                original = 'init() { start_native_purchases();\n' + ''.join(stockperks.NATIVE_PACK_A_PUNCH) + '}\n'
                original += 'perk_think(perk) { wait_for_down(); lose_native_perk(perk); }\n'
                original += 'perk_init_code_callbacks() { bind_native_hud(); }\n'
                output = stockperks.native_source(original, f'{prefix}/mp/zombies/_zm_perks.{ext}',
                                                  root / 'out', root / 'bo2')
                script = gsc.parse(output, 'native')
                self.assertIn('start_native_purchases();', output)
                for name in ('perk_think', 'perk_init_code_callbacks'):
                    before = gsc.parse(original, 'original')
                    fn = before.functions[name]
                    actual = script.functions[name]
                    self.assertEqual(gsc.emit(before.tokens[fn.body_open:fn.body_close + 1]),
                                     gsc.emit(script.tokens[actual.body_open:actual.body_close + 1]))
                self.assertIn('enable_electric_cherry_perk_for_level();', output)
                if prefix == 'maps':
                    self.assertNotIn('vending_weapon_upgrade', output)
                    self.assertNotIn('turn_packapunch_on', output)

    def test_entities_and_script_comparisons_use_same_native_perk_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'entities.json'
            path.write_text(json.dumps({'entities': [{'targetname': 'zombie_vending_bo1',
                'script_noteworthy': 'specialty_extraammo', 'target': 'vending_mule_kick'}]}))
            stockperks.translate_entities(path)
            entity = json.loads(path.read_text())['entities'][0]
            self.assertEqual(entity, {'targetname': 'zombie_vending',
                'script_noteworthy': 'specialty_additionalprimaryweapon',
                'target': 'vending_additionalprimaryweapon'})
            source = stockperks.translate_literals('if (perk == "specialty_extraammo") {} '
                'level notify("specialty_extraammo_power_on"); // specialty_extraammo\n'
                'hint = &"ZOMBIE_PERK_QUICKREVIVE";')
            self.assertIn('"specialty_additionalprimaryweapon"', source)
            self.assertIn('"specialty_additionalprimaryweapon_power_on"', source)
            self.assertIn('// specialty_extraammo', source)
            self.assertIn('&"ZOMBIE_PERK_QUICKREVIVE"', source)

    def test_custom_perk_machine_rejects_stock_mode_without_rewriting_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'entities.json'
            original = json.dumps({'entities': [{'targetname': 'zombie_vending_bo1',
                                                  'script_noteworthy': 'specialty_custom'}]})
            path.write_text(original)
            with self.assertRaisesRegex(ValueError, 'unsupported perk'):
                stockperks.translate_entities(path)
            self.assertEqual(path.read_text(), original)

    def test_stock_mode_never_starts_source_perk_controllers_or_duplicate_hud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {'maps/sample.gsc': '#include maps\\_zombiemode_perks;\n'
                'main() {\n maps\\_zombiemode::main();\n self setperk("specialty_quickrevive");\n'
                'self thread perk_hud_create("specialty_quickrevive");\n'
                'self thread perk_think("specialty_quickrevive");\n }',
                'maps/_zombiemode.gsc': 'main() { maps\\_zombiemode_perks::init(); '
                'maps\\_zombiemode_perks_extra::init(); }',
                'maps/_zombiemode_perks.gsc': 'init() {} perk_hud_create(perk) {} perk_think(perk) {}',
                'maps/_zombiemode_perks_extra.gsc': 'init() { start_custom_purchase(); }'}
            for name, source in files.items():
                path = root / 'source' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            report = gscport.port_map(gscport.Sources([root / 'source'], [], root / 'source'),
                T6Api({}, {r'maps\mp\zombies\_zm_perks': {'perk_think': 1}}),
                'sample', root / 'out', bo2_stock_perks=True)
            self.assertFalse(any(stockperks.is_perk_framework(p) for p in report.ported))
            self.assertFalse(any('stock BO2 perks' in error for error in report.errors))
            source = (root / 'out/maps/mp/waw/sample.gsc').read_text()
            self.assertEqual(source.count('stock_perks_owned_by_bo2('), 2)
            self.assertNotIn('::perk_think(', source)
            self.assertIn('::waw_setperk(', source)

    def test_waw_pack_a_punch_and_power_relays_stay_while_bo2_owns_perks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {'maps/sample.gsc': 'main() { maps\\_zombiemode_perks::init(); '
                                        'maps\\_zombiemode_perks_extra::init(); }',
                     'maps/_zombiemode_perks.gsc':
                         'init() {\n vending_triggers = getentarray("zombie_vending", "targetname");\n'
                         ' if (vending_triggers.size < 1) return;\n'
                         ' upgrades = getentarray("zombie_vending_upgrade", "targetname");\n'
                         ' array_thread(upgrades, ::vending_upgrade);\n'
                         ' array_thread(vending_triggers, ::vending_trigger_think);\n'
                         ' level thread turn_PackAPunch_on();\n}\n'
                         'vending_upgrade() { self thread do_knuckle_crack(); }\n'
                         'do_knuckle_crack() {}\n'
                         'turn_PackAPunch_on() { level waittill("Pack_A_Punch_on"); }\n'
                         'vending_trigger_think() { self perk_think("x"); }\n'
                         'perk_think(perk) {}\n',
                     'maps/_zombiemode_perks_extra.gsc':
                         'init() { level thread turn_staminup_on(); thread wait_for_power(); }\n'
                         'turn_staminup_on() { level waittill("staminup_on"); }\n'
                         'wait_for_power() { flag_wait("electricity_on"); level notify("staminup_on"); }\n'}
            for name, source in files.items():
                path = root / 'source' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            report = gscport.port_map(gscport.Sources([root / 'source'], [], root / 'stock'),
                T6Api({}, {r'maps\mp\zombies\_zm_perks': {'perk_think': 1}}),
                'sample', root / 'out', bo2_stock_perks=True)
            self.assertFalse(any('stock BO2 perks' in error for error in report.errors), report.errors)
            pap = (root / 'out/maps/mp/waw/_zombiemode_perks.gsc').read_text()
            self.assertIn('vending_upgrade', pap)
            self.assertIn('do_knuckle_crack', pap)
            self.assertIn('turn_PackAPunch_on', pap)
            self.assertNotIn('vending_trigger_think', pap)
            self.assertNotIn('perk_think', pap)
            extra = (root / 'out/maps/mp/waw/_zombiemode_perks_extra.gsc').read_text()
            self.assertIn('level notify("marathon_on")', extra)
            self.assertNotIn('turn_staminup_on', extra)
            main = (root / 'out/maps/mp/waw/sample.gsc').read_text()
            self.assertIn(r'maps\mp\waw\_zombiemode_perks::init()', main)
            self.assertIn(r'maps\mp\waw\_zombiemode_perks_extra::init()', main)

    def test_perk_machines_get_bo2_models_and_stay_out_of_the_map_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / 'bo2/raw'
            (raw / 'xmodel').mkdir(parents=True)
            (raw / 'xmodel/zombie_vending_jugg.json').write_text('{}')
            (raw / 'maps/mp/zombies').mkdir(parents=True)
            (raw / 'maps/mp/zombies/_zm_perks.gsc').write_text(
                'f() { precachemodel( "zombie_vending_jugg" ); precachemodel( "zombie_vending_ads" ); '
                'precachemodel( "p6_anim_zm_buildable_pap" ); }')
            for module in stockperks.MODULES:
                (raw / f'maps/mp/zombies/_zm_perk_{module}.gsc').write_text('f() {}')
            self.assertEqual(stockperks.machine_models(root / 'bo2'),
                             {'zombie_vending_jugg', 'p6_zm_al_vending_ads_on'})
            path = root / 'entities.json'
            path.write_text(json.dumps({'entities': [
                {'classname': 'trigger_use', 'targetname': 'zombie_vending',
                 'script_noteworthy': 'specialty_armorvest', 'target': 'vending_jugg'},
                {'classname': 'script_model', 'targetname': 'vending_jugg', 'model': 'zombie_vending_jugg'},
                {'classname': 'trigger_use', 'targetname': 'zombie_vending_bo1',
                 'script_noteworthy': 'specialty_bulletaccuracy', 'target': 'vending_deadshot'},
                {'classname': 'script_model', 'targetname': 'vending_deadshot', 'model': 'zombie_vending_deadshot'},
                {'classname': 'trigger_radius', 'targetname': 'vending_deadshot'},
                {'classname': 'script_model', 'targetname': 'vending_pack_a_punch',
                 'model': 'zombie_vending_packapunch'}]}))
            stockperks.translate_entities(path, root / 'bo2')
            models = [e.get('model') for e in json.loads(path.read_text())['entities']]
            self.assertEqual(models, [None, 'zombie_vending_jugg', None, 'p6_zm_al_vending_ads_on', None,
                                      'zombie_vending_packapunch'])

    def test_waw_mule_kick_inventory_size_raises_bo2_weapon_limit(self):
        # BO2 wall buys and its too-many-weapons monitor read get_player_weapon_limit,
        # which only counts BO2's Mule Kick; a WaW pack raises self.InventorySize
        source = (gscport.COMPAT_DIR / '_waw2bo2_compat.gsc').read_text()
        script = gsc.parse(source, 'compat')
        init = script.functions['init']
        self.assertIn('level.get_player_weapon_limit = ::waw_player_weapon_limit;',
                      gsc.emit(script.tokens[init.body_open:init.body_close + 1]))
        fn = script.functions['waw_player_weapon_limit']
        body = gsc.emit(script.tokens[fn.body_open:fn.body_close + 1])
        self.assertIn('player.inventorysize > limit', body)

    def test_hidden_box_trigger_is_restored_without_clearing_buyer_visibility(self):
        source = (gscport.COMPAT_DIR / '_waw2bo2_compat.gsc').read_text()
        script = gsc.parse(source, 'compat')
        fn = script.functions['waw_enable_trigger']
        body = gsc.emit(script.tokens[fn.body_open:fn.body_close + 1])
        self.assertLess(body.index('::enable_trigger()'), body.index('self show()'))
        self.assertIn('self.classname == "trigger_use"', body)
        self.assertNotIn('setvisibletoall', body)
        self.assertEqual(gscport.API['function_renames']['enable_trigger'],
                         gscport.COMPAT + '::waw_enable_trigger')

    def test_source_box_move_flags_are_isolated_for_initialization_and_waits(self):
        tokens = gsc.tokenize('flag_init("moving_chest_now"); flag_set("moving_chest_now"); '
            'if (flag("moving_chest_now")) {} flag_clear("moving_chest_now"); '
            'flag_wait("power_on"); level.chests = [];')
        gscport.rename_level_fields(tokens)
        text = gsc.emit(tokens)
        self.assertEqual(text.count('"waw_moving_chest_now"'), 4)
        self.assertIn('flag_wait("power_on")', text)
        self.assertIn('level.waw_chests', text)


if __name__ == '__main__':
    unittest.main()
