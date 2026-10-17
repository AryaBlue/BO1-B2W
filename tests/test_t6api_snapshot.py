import json
import tempfile
import unittest
from pathlib import Path

from waw2bo2 import t6api


class ShippedScriptApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_snapshot_has_no_client_only_animation_builtins(self):
        # client tables misread as server tables (a raw folder without
        # clientscripts) made T6 link setanimknob/setflaggedanimknob natively
        stock = t6api.load_snapshot()
        self.assertIsNotNone(stock)
        for name in ('setanimknob', 'setflaggedanimknob', 'setanimknobrestart', 'setflaggedanimknobrestart'):
            self.assertNotIn(name, stock['methods'])
            self.assertNotIn(name, stock['builtins'])
        self.assertIn('setanim', stock['methods'])

    def test_build_uses_snapshot_whatever_the_local_raw_holds(self):
        game = self.root / 'game'
        (game / 'raw' / 'maps').mkdir(parents=True)
        api = t6api.build(game, self.root / 'cache.json')
        stock = t6api.load_snapshot()
        self.assertEqual(set(api.methods), set(stock['methods']))
        self.assertEqual(set(api.scripts), set(stock['scripts']))

    def test_snapshot_overrides_a_cache_indexed_from_incomplete_raw(self):
        cache = self.root / 'cache.json'
        cache.write_text(json.dumps({'version': t6api.CACHE_VERSION, 'builtins': {},
                                     'methods': {'setanimknob': [1, 4]}, 'scripts': {},
                                     'stock_assets': {'script': ['maps/common.gsc']}}))
        api = t6api.build(self.root / 'game', cache, Path('unlinker.exe'))
        self.assertIsNone(api.builtin_accepts('setanimknob', 4, True))
        self.assertEqual(api.stock_assets, {'script': {'maps/common.gsc'}})

    def test_snapshot_requires_complete_mod_tools_raw(self):
        game = self.root / 'game'
        for sub in ('maps', 'common_scripts'):
            (game / 'raw' / sub).mkdir(parents=True)
        with self.assertRaisesRegex(FileNotFoundError, 'clientscripts'):
            t6api.write_snapshot(game, self.root / 'snapshot.json')


if __name__ == '__main__':
    unittest.main()
