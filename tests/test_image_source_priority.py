import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from waw2bo2 import iwi, t6bridge, wavelet, weapons


def image(value):
    return (b'IWi\x06' + bytes([iwi.FMT_DXT1, iwi.FLAG_NOMIPMAPS]) +
            struct.pack('<3H4I', 4, 4, 1, 36, 0, 0, 0) + bytes([value]) * 8)


class ImageSourcePriorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.map_images = self.root / 'map/images'
        self.stock_images = self.root / 'stock/images'
        self.mod_iwds = self.root / 'mod_iwds'
        self.stock_iwds = self.root / 'stock_iwds'
        for folder in (self.map_images, self.stock_images, self.mod_iwds, self.stock_iwds):
            folder.mkdir(parents=True)
        self.stock = self.stock_images / 'skin.dds'
        self.stock.write_bytes(iwi.iwi6_to_dds(image(10)))
        self.archive(self.mod_iwds, image(20))
        self.archive(self.stock_iwds, image(30))

    def archive(self, folder, data):
        with zipfile.ZipFile(folder / 'images.iwd', 'w') as z:
            z.writestr('images/skin.iwi', data)

    def recovery(self):
        return wavelet.IwdRecovery([self.mod_iwds, self.stock_iwds], None, self.root / 'recovery',
            source_image_roots=[self.map_images], override_directories=[self.mod_iwds])

    def test_map_iwd_precedes_stock_dump_in_world_staging(self):
        report = t6bridge.StageReport('test')
        output = self.root / 'world'
        t6bridge.stage_images(report, [self.map_images, self.stock_images], output,
                              iwd_dirs=[], extra_images=['skin'], wavelets=self.recovery())
        self.assertEqual((output / 'images/skin.iwi').read_bytes(),
                         iwi.dds_to_iwi(iwi.iwi6_to_dds(image(20))))
        entry = next(e for e in report.images if e['name'] == 'skin')
        self.assertEqual(entry['wavelet']['archive'], str(self.mod_iwds / 'images.iwd'))
        self.assertEqual(report.errors, [])

    def test_map_zone_pixels_remain_authoritative(self):
        own = self.map_images / 'skin.dds'
        own.write_bytes(iwi.iwi6_to_dds(image(40)))
        recovery = self.recovery()
        self.assertEqual(recovery.resolve('skin', own), own)
        self.assertEqual(recovery.recovered, {})

    def test_stock_iwd_does_not_override_available_zone_pixels(self):
        (self.mod_iwds / 'images.iwd').unlink()
        self.assertEqual(self.recovery().resolve('skin', self.stock), self.stock)

    def test_weapon_images_use_the_same_priority_and_record_archive(self):
        report = t6bridge.StageReport('test')
        output = self.root / 'weapon'
        error = weapons._stage_image([self.stock_images.parent], output, 'skin',
                                     'waw_image/skin', self.recovery(), report)
        self.assertIsNone(error)
        self.assertEqual((output / 'images/waw_image/skin.iwi').read_bytes(),
                         iwi.dds_to_iwi(iwi.iwi6_to_dds(image(20))))
        self.assertEqual(report.images[0]['iwd_recovery']['archive'], str(self.mod_iwds / 'images.iwd'))

    def test_unconvertible_map_override_is_reported_without_stock_substitution(self):
        self.archive(self.mod_iwds, b'unsupported')
        report = t6bridge.StageReport('test')
        output = self.root / 'world'
        t6bridge.stage_images(report, [self.stock_images], output,
                              iwd_dirs=[], extra_images=['skin'], wavelets=self.recovery())
        self.assertTrue(any('unsupported IWI format' in e for e in report.errors))
        self.assertFalse((output / 'images/skin.iwi').exists())

    def test_weapon_override_keeps_the_full_nested_image_name(self):
        (self.stock_images / 'nested').mkdir()
        (self.stock_images / 'nested/skin.dds').write_bytes(self.stock.read_bytes())
        with zipfile.ZipFile(self.mod_iwds / 'nested.iwd', 'w') as z:
            z.writestr('images/nested/skin.iwi', image(60))
        report = t6bridge.StageReport('test')
        output = self.root / 'weapon'
        error = weapons._stage_image([self.stock_images.parent], output, 'nested/skin',
                                     'waw_image/nested/skin', self.recovery(), report)
        self.assertIsNone(error)
        self.assertEqual((output / 'images/waw_image/nested/skin.iwi').read_bytes(),
                         iwi.dds_to_iwi(iwi.iwi6_to_dds(image(60))))

    def test_new_build_decodes_current_archive_instead_of_old_recovery_file(self):
        self.recovery().resolve('skin', self.stock)
        self.archive(self.mod_iwds, image(50))
        source = self.recovery().resolve('skin', self.stock)
        self.assertEqual(source.read_bytes(), iwi.iwi6_to_dds(image(50)))


if __name__ == '__main__':
    unittest.main()
