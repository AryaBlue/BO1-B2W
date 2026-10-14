import unittest

from waw2bo2 import gsc, gscport
from waw2bo2.t6api import T6Api


class EntityLookupBridgeTests(unittest.TestCase):
    def translate(self, text):
        script = gsc.parse(text, 'test')
        translator = gscport.Translator(gscport.Sources([], [], None),
            T6Api({'getent': (2, 2), 'getentarray': (0, 2)}, {}), gscport.PortReport())
        translator.resolve_refs(script.tokens, script, 'test', set(),
                               {f.start for f in script.functions.values()})
        return gsc.emit(script.tokens)

    def test_link_fields_use_scan_and_native_fields_remain_native(self):
        result = self.translate('f(){a=GetEnt(parent.script_linkto,"script_linkname");'
            'b=getentarray("hinge","script_linkname");c=getent("door","targetname");'
            'd=getentarray();}')
        self.assertIn('::waw_getent_linkname(parent.script_linkto,"script_linkname")', result)
        self.assertIn('::waw_getentarray_linkname("hinge","script_linkname")', result)
        self.assertIn('getent("door","targetname")', result)
        self.assertIn('getentarray()', result)

    def test_custom_getent_is_not_replaced(self):
        result = self.translate('getent(a,b){return a;} f(){x=getent("a","script_linkname");}')
        self.assertNotIn('waw_getent_linkname', result)

    def test_dynamic_field_expression_is_not_assumed_to_be_a_literal(self):
        result = self.translate('f(){script_linkname="targetname";x=getent("a",script_linkname);}')
        self.assertNotIn('waw_getent_linkname', result)
