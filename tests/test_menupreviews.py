import unittest

from PIL import Image

from waw2bo2 import menupreviews as mp


def aligned():
    images = {}
    for role in ('large', 'blur', 'blit'):
        image = Image.new('RGBA', (320, 180), (25, 50, 100, 255))
        if role == 'blit':
            image.putalpha(0)
        for y in range(40, 100):
            for x in range(200, 300):
                image.putpixel((x, y), (200, 100, 50, 255 if role == 'blit' else 0))
        images[role] = image
    return images


class MenuPreviewTests(unittest.TestCase):
    def test_every_screen_renders_at_menu_size_without_bo2(self):
        images = aligned()
        for frame in (mp.map_selection(images, 'Test Town', 'A description.', point='250,70'),
                      mp.map_selection(images, 'Test Town', 'A description.', focused=True),
                      mp.lobby(images, None, 'Test Town', 'Survival'),
                      mp.loading(images, None, 'Test Town', 'Berlin'),
                      mp.Globe(None, 120).scene(0, [(0, 0, None, 'Test Town', True)])):
            self.assertEqual(frame.size, mp.SCREEN)

    def test_missing_layers_draw_a_placeholder(self):
        frame = mp.map_selection({}, 'Test Town', '')
        self.assertEqual(frame.size, mp.SCREEN)

    def test_click_on_map_selection_maps_back_to_blit_pixels(self):
        images = aligned()
        # 320 x 180 is already 16:9: screen (1280, 720) scales by 4.
        self.assertEqual(mp.screen_to_canvas(images, (1000, 280)), (250, 70))
        self.assertIsNone(mp.screen_to_canvas({}, (10, 10)))

    def test_globe_pick_inverts_projection_in_bo2_convention(self):
        globe = mp.Globe(None, 400)
        for lon, lat in ((-138, 36), (122, 35), (-11, 49)):
            center = -lon   # BO2 longitude is geographic with the sign flipped
            x, y = globe.project(center, lon, lat)
            self.assertEqual(globe.pick(center, x, y), (lon, lat))
        self.assertIsNone(globe.project(0, 180, 0))   # the far side is hidden

    def test_stock_maps_reads_bo2_mapstable(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            table = Path(temp) / 'raw/zm/mapstable.csv'
            table.parent.mkdir(parents=True)
            row = ['zm_prison', 'g', 'i', 'ZMUI_PRISON', 'menu_zm_map_signpost_prison'] + [''] * 11 + ['122', '35', '0', 'left']
            table.write_text(','.join(row) + '\n')
            self.assertEqual(mp.stock_maps(temp), [(122.0, 35.0, 'menu_zm_map_signpost_prison', 'Mob of the Dead')])
            self.assertEqual(mp.stock_maps(None), [])


if __name__ == '__main__':
    unittest.main()
