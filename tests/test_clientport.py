import unittest
from waw2bo2 import clientport


class ClientPortTests(unittest.TestCase):
    def test_source_effects_sounds_and_single_argument_level_events_are_translated(self):
        source = '#include clientscripts\\_utility;\ninit(){loadfx("source/tube");}\n' \
                 'watch(){level waittill("TGH"); level waittill("notetrack", n, note); ' \
                 'realwait(0.1); playsound(0,"source_hum",(0,0,0)); ' \
                 'if(getcurrentweapon(0)=="source_weapon") return;}\n'
        translated = clientport.translate_library(source, {'source/tube':'waw/source/tube'},
                                                  {'source_weapon':'converted_weapon'}, {'source_hum'})
        self.assertIn('#include clientscripts\\mp\\_utility;', translated)
        self.assertIn('loadfx("waw/source/tube")', translated)
        self.assertIn('waitrealtime(0.1)', translated)
        self.assertIn('"waw/source_hum"', translated)
        self.assertIn('"converted_weapon"', translated)
        self.assertIn('registersystem( "TGH", ::waw_notify_0 )', translated)
        self.assertNotIn('registersystem( "notetrack"', translated)
        self.assertIn('level notify( "TGH" )', translated)
