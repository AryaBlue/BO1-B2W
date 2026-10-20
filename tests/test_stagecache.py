import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from waw2bo2 import stagecache


class StageCacheModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / 'stage'
        self.cache = stagecache.StageCache(self.root / 'stage_cache')

    def write(self, rel, text):
        path = self.stage / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_enabled_only_on_explicit_opt_in(self):
        for value in ('', '0', 'false', 'FALSE', 'off', 'No'):
            with patch.dict(os.environ, {'WAW2BO2_STAGE_CACHE': value}):
                self.assertFalse(stagecache.enabled())
        for value in ('1', 'true', 'yes', 'on'):
            with patch.dict(os.environ, {'WAW2BO2_STAGE_CACHE': value}):
                self.assertTrue(stagecache.enabled())
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(stagecache.enabled())

    def test_snapshot_and_changed_detect_new_and_modified_files(self):
        self.assertEqual(stagecache.snapshot(self.stage), {})   # missing dir
        before = stagecache.snapshot(self.stage)
        self.write('content_source/weapons/ak47', 'fields')
        self.write('content_source/keep.txt', 'seed')
        after = stagecache.snapshot(self.stage)
        self.assertEqual(stagecache.changed(before, after),
                         ['content_source/keep.txt', 'content_source/weapons/ak47'])
        # An unchanged file is not reported; only the edited one is.
        mid = stagecache.snapshot(self.stage)
        os.utime(self.stage / 'content_source/weapons/ak47', (10 ** 9, 10 ** 9))
        self.write('content_source/weapons/ak47', 'fields-v2')
        self.assertEqual(stagecache.changed(mid, stagecache.snapshot(self.stage)),
                         ['content_source/weapons/ak47'])

    def test_store_restore_round_trips_the_staged_diff(self):
        before = stagecache.snapshot(self.stage)
        self.write('content_source/weapons/ak47', 'fields')
        self.write('content_source/fx/muzzle.json', '{}')
        files = stagecache.changed(before, stagecache.snapshot(self.stage))
        token = self.cache.token({'map': 'cellar'})
        self.assertTrue(self.cache.store(token, self.stage, files, meta={'project': 'zm_cellar'}))

        # Wipe the staged output; a restore must reproduce it byte for byte.
        import shutil
        shutil.rmtree(self.stage)
        self.assertIsNotNone(self.cache.lookup(token))
        manifest = self.cache.restore(token, self.stage)
        self.assertEqual(manifest['meta']['project'], 'zm_cellar')
        self.assertEqual((self.stage / 'content_source/weapons/ak47').read_text(), 'fields')
        self.assertEqual((self.stage / 'content_source/fx/muzzle.json').read_text(), '{}')

    def test_restored_file_is_a_copy_not_a_link_into_the_cache(self):
        self.write('a.txt', 'one')
        token = self.cache.token({'k': 1})
        self.cache.store(token, self.stage, ['a.txt'])
        self.cache.restore(token, self.stage)
        # Editing the restored file must not corrupt the cached copy.
        (self.stage / 'a.txt').write_text('mutated')
        self.cache.restore(token, self.stage)
        self.assertEqual((self.stage / 'a.txt').read_text(), 'one')

    def test_different_inputs_miss_and_schema_bump_invalidates(self):
        self.write('a.txt', 'x')
        token = self.cache.token({'tool': 'v1'})
        self.cache.store(token, self.stage, ['a.txt'])
        self.assertIsNone(self.cache.lookup(self.cache.token({'tool': 'v2'})))
        with patch.object(stagecache, 'SCHEMA', stagecache.SCHEMA + 1):
            self.assertIsNone(self.cache.lookup(self.cache.token({'tool': 'v1'})))

    def test_empty_diff_is_never_stored(self):
        token = self.cache.token({'k': 1})
        self.assertFalse(self.cache.store(token, self.stage, []))
        self.assertIsNone(self.cache.lookup(token))

    def test_incomplete_entry_is_not_a_hit(self):
        self.write('a.txt', 'x')
        token = self.cache.token({'k': 1})
        self.cache.store(token, self.stage, ['a.txt'])
        self.assertIsNotNone(self.cache.lookup(token))
        # A missing cached file invalidates the whole entry (no partial skip).
        (self.cache.root / token / 'tree' / 'a.txt').unlink()
        self.assertIsNone(self.cache.lookup(token))
        with self.assertRaises(KeyError):
            self.cache.restore(token, self.stage)

    def test_restore_overwrites_a_stale_file_already_in_stage(self):
        self.write('a.txt', 'cached')
        token = self.cache.token({'k': 1})
        self.cache.store(token, self.stage, ['a.txt'])
        (self.stage / 'a.txt').write_text('stale from a previous build')
        self.cache.restore(token, self.stage)
        self.assertEqual((self.stage / 'a.txt').read_text(), 'cached')


if __name__ == '__main__':
    unittest.main()
