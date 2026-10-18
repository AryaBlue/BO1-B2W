from pathlib import Path
import json
import tempfile
import unittest
import wave
from PIL import Image
from waw2bo2.launcher import Settings
from waw2bo2.mapmenu import validate_settings
from waw2bo2.menuart import SIZES, read_art, stage_art, validate_art, load_artwork, composite_art, compressed_iwi
from waw2bo2.modzone import stage_menu_assets
from waw2bo2.iwi import FMT_DXT1, FMT_DXT5, read_iwi_header


class MenuArtworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings(project='zm_example', menu_title='Example Town', menu_description='Survive the town.')

    def artwork(self):
        for role, size in SIZES.items():
            image = Image.new('RGBA', size, (23, 45, 67, 255))
            if role == 'blit':
                image.putpixel((0, 0), (23, 45, 67, 0))
            path = self.root / (role + '.png')
            image.save(path)
            setattr(self.settings, 'menu_' + role, str(path))

    def test_exports_pixels_materials_and_streaming_registration(self):
        self.artwork()
        project = self.root / 'project'
        stage_art(self.settings, project)
        entries = stage_menu_assets(project, self.settings.project)
        self.assertIn('>ipak,zm_example_menu', entries)
        for role, size in {**SIZES, 'icon': (256, 256)}.items():
            pixels = (project / 'images' / f'menu_zm_example_{role}.iwi').read_bytes()
            header = read_iwi_header(pixels)
            self.assertEqual((header['width'], header['height']), size)
            # block-compressed like the Nuketown art: a 2048 RGBA backdrop
            # (16 MB) failed to allocate at startup
            self.assertEqual(header['format'], FMT_DXT5 if role in ('blit', 'icon') else FMT_DXT1)
            self.assertEqual(len(pixels) - 64, size[0] * size[1] // (1 if role in ('blit', 'icon') else 2))
        stream = json.loads((project / 'images/streaming.json').read_text())
        self.assertTrue(all(value == 2 for value in stream['streamingMode'].values()))
        self.assertIn('Example Town', (project / 'english/localizedstrings/menu_zm_example.str').read_text())

    def test_wrong_resolution_warns_and_opaque_blit_is_rejected(self):
        path = self.root / 'bad.png'
        Image.new('RGBA', (256, 256)).save(path)
        with self.assertWarnsRegex(UserWarning, '512 × 256'):
            read_art(str(path), 'blit')
        Image.new('RGB', SIZES['blit']).save(path)
        with self.assertRaisesRegex(ValueError, 'transparent'):
            read_art(str(path), 'blit')

    def test_partial_upload_is_rejected(self):
        self.settings.menu_large = 'large.png'
        with self.assertRaisesRegex(ValueError, 'all three'):
            validate_art(self.settings)

    def aligned_artwork(self):
        for role in SIZES:
            image = Image.new('RGBA', (128, 72), (25, 50, 100, 255))
            if role == 'blit':
                image.putalpha(0)
            for y in range(20, 52):
                for x in range(40, 88):
                    image.putpixel((x, y), (200, 100, 50, 255 if role == 'blit' else 0))
            image.save(self.root / (role + '.png'))
            setattr(self.settings, 'menu_' + role, str(self.root / (role + '.png')))
        from waw2bo2.menulayers import RUNTIME
        self.settings.bo2 = str(self.root / 'bo2')
        source = Path(self.settings.bo2) / 'raw' / RUNTIME
        source.parent.mkdir(parents=True)
        from waw2bo2 import menulayers
        compiled = Path(menulayers.__file__).parent / 'compat/menu_layers.luac'
        source.write_bytes(compiled.read_bytes()[:16] + b'stock-fixture')

    def test_aligned_layers_preserve_hole_and_register_native_runtime(self):
        self.aligned_artwork()
        validate_art(self.settings)
        image = composite_art(load_artwork(self.settings))
        self.assertEqual(image.getpixel((60, 30)), (200, 100, 50, 255))
        self.assertEqual(image.getpixel((10, 10)), (25, 50, 100, 255))
        stage_art(self.settings, self.root / 'project')
        data = json.loads((self.root / 'project/menu.json').read_text())
        entries = stage_menu_assets(self.root / 'project', self.settings.project)
        self.assertIn('rawfile,ui_mp/t6/zombie/gamemapzombie.lua', entries)
        self.assertIn('rawfile,ui_mp/t6/zombie/waw_gamemap_base.lua', entries)
        self.assertIn('stringtable,zm/waw_menu_layers.csv', entries)
        self.assertIn('material,menu_zm_example_blit', entries)
        self.assertEqual(data['blit'], 'menu_zm_example_loc')
        # The fixture's Blit square is centred on the canvas.
        self.assertEqual(data['start_location'], [0, 0])
        self.assertLess(len(data['blit']), 32)
        self.assertIn('material,menu_zm_example_loc', entries)
        report = data['texture_report']['blit']
        self.assertEqual((report['format'], report['bytes']), ('DXT5', 2048 * 2048 + 64))
        # Both states are baked: the cutout is filled in Map and in Map Blur.
        for role in ('large', 'blur', 'complete'):
            self.assertEqual(data['texture_report'][role]['format'], 'DXT1')
        self.assertLess(sum(r['bytes'] for r in data['texture_report'].values()), 16 * 1024 * 1024)
        for suffix in ('zclassic_default',):
            binding = json.loads((self.root / f'project/materials/loadscreen_zm_example_{suffix}.json').read_text())
            self.assertEqual(binding['textures'][0]['image'], 'menu_zm_example_complete')

    def test_blit_center_is_in_menu_units_from_the_screen_centre(self):
        from waw2bo2.menuart import blit_center
        blit = Image.new('RGBA', (160, 90))
        blit.paste((255, 0, 0, 255), (120, 0, 160, 30))   # top-right corner block
        self.assertEqual(blit_center(blit), [480, -240])

    def test_replacing_aligned_with_stock_removes_runtime(self):
        self.aligned_artwork()
        project = self.root / 'project'
        stage_art(self.settings, project)
        self.artwork()
        stage_art(self.settings, project)
        self.assertFalse((project / 'ui_mp/t6/zombie/gamemapzombie.lua').exists())
        self.assertFalse((project / 'zm/waw_menu_layers.csv').exists())
        self.assertNotIn('layer_layout', json.loads((project / 'menu.json').read_text()))

    def test_mixed_canvas_upload_warns_but_previews_and_exports(self):
        self.aligned_artwork()
        Image.new('RGBA', (129, 72)).save(self.settings.menu_blur)
        with self.assertWarnsRegex(UserWarning, 'canvas sizes differ'):
            validate_art(self.settings)
        images = load_artwork(self.settings)
        self.assertEqual(composite_art(images).size, (128, 72))
        self.assertEqual(composite_art(images, blurred=True).size, (128, 72))
        with self.assertWarnsRegex(UserWarning, 'canvas sizes differ'):
            stage_art(self.settings, self.root / 'project')
        data = json.loads((self.root / 'project/menu.json').read_text())
        self.assertEqual(data['layer_layout'], 'aligned')
        for role in ('large', 'blur', 'blit'):
            self.assertEqual(data['texture_report'][role]['width'], 2048)
            self.assertLess(data['texture_report'][role]['bytes'], 16 * 1024 * 1024)

    def test_compressor_rejects_lost_alpha_and_16_mib_texture(self):
        with self.assertRaisesRegex(ValueError, 'DXT5'):
            compressed_iwi(Image.new('RGBA', (8, 8)), 'DXT1')
        with self.assertRaisesRegex(ValueError, 'smaller than 16'):
            compressed_iwi(Image.new('RGBA', (4096, 4096)), 'DXT5')
        with self.assertRaisesRegex(ValueError, 'DXT1 or DXT5'):
            compressed_iwi(Image.new('RGB', (8, 8)), 'DXT3')

    def test_text_only_and_clear_keep_default_branding_without_art(self):
        self.artwork()
        project = self.root / 'project'
        stage_art(self.settings, project)
        for role in SIZES:
            setattr(self.settings, 'menu_' + role, '')
        stage_art(self.settings, project)
        self.assertEqual(stage_menu_assets(project, 'zm_example'), ['localize,menu_zm_example'])
        self.assertFalse((project / 'materials/menu_zm_example_map.json').exists())
        self.settings.menu_title = self.settings.menu_description = ''
        stage_art(self.settings, project)
        self.assertFalse((project / 'menu.json').exists())

    def test_mode_name_and_location_reach_menu_metadata(self):
        project = self.root / 'project'
        self.settings.menu_title = self.settings.menu_description = ''
        self.settings.menu_mode, self.settings.menu_location = 'Nacht', 'Germany, 1945'
        stage_art(self.settings, project)
        data = json.loads((project / 'menu.json').read_text())
        self.assertEqual((data['title'], data['mode'], data['location']), ('zm_example', 'Nacht', 'Germany, 1945'))

    def test_start_location_mode_list_is_localized(self):
        # SelectStartLocZombie.lua shows ZMUI_<mode>_<map>_CAPS over <col7>_DESC_<location>
        project = self.root / 'project'
        (project / 'zm').mkdir(parents=True)
        (project / 'zm/gametypestable.csv').write_text(
            '0,zclassic,ZMUI_CLASSIC_CAPS,ZMUI_CLASSIC_DESC,playlist_tdm,0,YES,ZMUI_CLASSIC,YES,zclassic\n'
            '6,20,zm_example,default,zclassic,0,left,YES\n')
        self.settings.menu_mode = 'Japan'
        stage_art(self.settings, project)
        stage_menu_assets(project, 'zm_example')
        text = (project / 'english/localizedstrings/menu_zm_example.str').read_text()
        for key, value in (('ZMUI_ZCLASSIC_ZM_EXAMPLE_CAPS', 'JAPAN'), ('ZMUI_ZCLASSIC_ZM_EXAMPLE', 'Japan'),
                           ('ZMUI_CLASSIC_DESC_DEFAULT', 'Survive the town.')):
            self.assertIn(f'REFERENCE {key}\nLANG_ENGLISH "{value}"', text)

    def test_globe_coordinates_reach_menu_metadata_and_are_range_checked(self):
        project = self.root / 'project'
        self.settings.menu_longitude, self.settings.menu_latitude = '-73.5', '45.5'
        stage_art(self.settings, project)
        data = json.loads((project / 'menu.json').read_text())
        self.assertEqual((data['longitude'], data['latitude']), (-73.5, 45.5))
        self.settings.menu_latitude = '91'
        with self.assertRaisesRegex(ValueError, 'Latitude'):
            validate_settings(self.settings)
        self.settings.menu_latitude = 'nan'
        with self.assertRaisesRegex(ValueError, 'Latitude'):
            validate_settings(self.settings)

    def test_loading_song_stages_streamed_music_bank_and_clears_it(self):
        source = self.root / 'song.wav'
        with wave.open(str(source), 'wb') as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b'\x01\x00\x02\x00' * 480)
        project = self.root / 'project'
        self.settings.loading_song = str(source)
        stage_art(self.settings, project)
        bank = json.loads((project / 'menu.json').read_text())['loading_song']['bank']
        self.assertIn('soundbank,' + bank, stage_menu_assets(project, 'zm_example'))
        aliases = (project / 'soundbank' / (bank + '.aliases.csv')).read_text()
        self.assertIn('mus_load_zm_example_patch', aliases)
        self.settings.loading_song = ''
        stage_art(self.settings, project)
        self.assertNotIn('loading_song', json.loads((project / 'menu.json').read_text()))
        self.assertFalse((project / 'soundbank' / (bank + '.aliases.csv')).exists())
