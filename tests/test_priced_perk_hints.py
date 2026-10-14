import unittest

from waw2bo2 import gsc, gscport


class PricedPerkHintTests(unittest.TestCase):
    def test_generic_prompt_uses_authored_selector(self):
        text = '''vending_set_hintstring(perk){self SetHintString(&"ZOMBIE_PERK_JUGGERNAUT");}
        vending_trigger_think(){self SetHintString(&"ZOMBIE_PERK_GENERIC");}'''
        script = gsc.parse(text, 'perks')
        self.assertEqual(gscport.bridge_generic_perk_hints(script.tokens, script), 1)
        result = gsc.emit(script.tokens)
        self.assertIn('self vending_set_hintstring(self.script_noteworthy)', result)
        self.assertIn('&"ZOMBIE_PERK_JUGGERNAUT"', result)
        gsc.parse(result, 'translated')

    def test_no_selector_or_custom_hint_is_unchanged(self):
        for text in ('f(){self SetHintString(&"ZOMBIE_PERK_GENERIC");}',
                     'vending_set_hintstring(p){} f(){self SetHintString(&"CUSTOM_PERK");}',
                     'vending_set_hintstring(p){} f(){other SetHintString(&"ZOMBIE_PERK_GENERIC");}'):
            script = gsc.parse(text, 'perks')
            self.assertEqual(gscport.bridge_generic_perk_hints(script.tokens, script), 0)
            self.assertEqual(gsc.emit(script.tokens), text)
