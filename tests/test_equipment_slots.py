import tempfile
import unittest
from pathlib import Path

from waw2bo2 import gscport
from waw2bo2.t6api import T6Api


class EquipmentSlotTranslationTests(unittest.TestCase):
    def test_owner_visibility_uses_waw_mask_replacement_even_with_native_builtin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'maps').mkdir()
            (root / 'maps/test.gsc').write_text(
                'main(){ trigger SetVisibleToPlayer(owner); trigger setvisibletoall(); }')
            api = T6Api({}, {}, methods={'setvisibletoplayer': (1, 1), 'setvisibletoall': (0, 0)})
            translator = gscport.Translator(gscport.Sources([root], [], None), api, gscport.PortReport())
            source = translator.translate(r'maps\test')
            self.assertIn('trigger ' + gscport.COMPAT + '::waw_setvisibletoplayer(owner)', source)
            self.assertIn('trigger setvisibletoall()', source)
            self.assertEqual(translator.report.unsupported, {})

    def test_repeated_native_hud_cleanup_is_safe_without_changing_local_helpers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'maps').mkdir()
            (root / 'maps/test.gsc').write_text(
                '#include maps\\_hud_util;\nmain(){ hud destroyElem(); hud destroyElem(); '
                'player EnableWeaponCycling(); }')
            (root / 'maps/_hud_util.gsc').write_text('destroyElem(){}')
            api = T6Api({}, {r'maps\mp\gametypes_zm\_hud_util': {'destroyelem': 0}},
                        methods={'enableweaponcycling': (0, 0)})
            translator = gscport.Translator(gscport.Sources([root], [], None), api, gscport.PortReport())
            text = translator.translate(r'maps\test')
            self.assertEqual(text.count('waw_destroy_hud_elem( hud )'), 2)
            self.assertIn('EnableWeaponCycling()', text)
            (root / 'maps/local.gsc').write_text('main(){ hud destroyElem(); } destroyElem(){}')
            translator = gscport.Translator(gscport.Sources([root], [], None), api, gscport.PortReport())
            self.assertNotIn('waw_destroy_hud_elem', translator.translate(r'maps\local'))

    def test_zombies_hud_cleanup_guards_missing_and_repeated_hud_receivers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'maps').mkdir()
            (root / 'maps/test.gsc').write_text(
                '#include maps\\_zombiemode_utility;\n'
                'main(){ self.hint_hud destroy_hud(); self.hint_hud destroy_hud(); '
                'self.used_suit = undefined; self notify("lost"); }')
            (root / 'maps/_zombiemode_utility.gsc').write_text('destroy_hud() { self destroy(); }')
            api = T6Api({}, {r'maps\mp\zombies\_zm_utility': {'destroy_hud': 0}})
            translator = gscport.Translator(gscport.Sources([root], [], None), api, gscport.PortReport())
            text = translator.translate(r'maps\test')
            self.assertEqual(text.count('waw_destroy_hud( self.hint_hud )'), 2)
            self.assertIn('self.used_suit = undefined;', text)
            self.assertIn('self notify("lost");', text)
            self.assertEqual(translator.report.unsupported, {})

    def test_map_owned_hud_destructors_retain_their_source_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'maps').mkdir()
            (root / 'maps/test.gsc').write_text(
                '#include maps\\_zombiemode_utility;\nmain(){ hud destroy_hud(); } '
                'destroy_hud(){ custom_cleanup(); } custom_cleanup(){}')
            api = T6Api({}, {r'maps\mp\zombies\_zm_utility': {'destroy_hud': 0}})
            translator = gscport.Translator(gscport.Sources([root], [], None), api, gscport.PortReport())
            self.assertNotIn('waw_destroy_hud(', translator.translate(r'maps\test'))

    def test_weapon_slot_calls_translate_even_when_bo2_accepts_the_builtin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'maps').mkdir()
            (root / 'maps/test.gsc').write_text(
                'main(){ player setActionSlot(3,"weapon",item); '
                'self setactionslot(3,"weapon"," "); self setactionslot(3,"altMode"); }')
            api = T6Api({}, {}, methods={'setactionslot': (2, 3)})
            translator = gscport.Translator(gscport.Sources([root], [], None), api, gscport.PortReport())
            text = translator.translate(r'maps\test')
            self.assertIn('waw_setactionslot(3,"weapon",item)', text)
            self.assertIn('waw_setactionslot(3,"weapon"," ")', text)
            self.assertIn('waw_setactionslot(3,"altMode")', text)


if __name__ == '__main__':
    unittest.main()
