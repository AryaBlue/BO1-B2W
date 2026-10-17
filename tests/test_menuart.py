from pathlib import Path
import json
import tempfile
import unittest
from PIL import Image
from waw2bo2.launcher import Settings
from waw2bo2.menuart import SIZES, read_art, stage_art, validate_art
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

    def test_wrong_resolution_and_opaque_blit_are_rejected(self):
        path = self.root / 'bad.png'
        Image.new('RGBA', (256, 256)).save(path)
        with self.assertRaisesRegex(ValueError, '512 × 256'):
            read_art(str(path), 'blit')
        Image.new('RGB', SIZES['blit']).save(path)
        with self.assertRaisesRegex(ValueError, 'transparent'):
            read_art(str(path), 'blit')

    def test_partial_upload_is_rejected(self):
        self.settings.menu_large = 'large.png'
        with self.assertRaisesRegex(ValueError, 'all three'):
            validate_art(self.settings)

    def test_text_only_and_clear_remove_previous_generated_art(self):
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
