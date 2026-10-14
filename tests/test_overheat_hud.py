import unittest
from waw2bo2.overheathud import repair_bytecode


class OverheatHudTests(unittest.TestCase):
    def test_only_stock_typos_change_and_offsets_are_preserved(self):
        original = b'\x1bLuaQ\x00header\x00beingAnimation\x00body\x00pluse_low\x00tail'
        fixed = repair_bytecode(original)
        self.assertEqual(len(fixed), len(original))
        self.assertEqual(fixed, original.replace(b'beingAnimation', b'beginAnimation').replace(b'pluse_low', b'pulse_low'))

    def test_unrecognized_bytecode_is_rejected(self):
        for original in (b'not Lua', b'\x1bLuaQ\x00beginAnimation\x00pulse_low\x00'):
            with self.assertRaises(ValueError):
                repair_bytecode(original)
