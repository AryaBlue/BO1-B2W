import tempfile
import json
import unittest
from pathlib import Path

from waw2bo2 import weapons, t6bridge
from waw2bo2.assetresolve import Resolver


class FlameTableTests(unittest.TestCase):
    def test_t6_carrier_stays_within_authored_stream_and_restores_t4_brightness(self):
        original = {'flameVar_streamFuelLength': '300', 'flameVar_streamFlameLength': '246.744',
                    'flameVar_streamChunkSpeed': '1000.71', 'flameVar_streamChunkDuration': '1.6397'}
        translated = weapons.translate_flame_table(original)
        self.assertLessEqual(float(translated['flameVar_streamChunkDuration']) * 1000.71, 300.000001)
        self.assertEqual(translated['flameVar_fireBrightness'], '1')
        self.assertEqual(translated['flameVar_dripsBrightness'], '1')
        explicit = dict(original, flameVar_fireBrightness='0.4', flameVar_dripsBrightness='0',
                        flameVar_streamChunkDuration='0.1')
        self.assertEqual(weapons.translate_flame_table(explicit), explicit)

    def test_native_initializer_is_gated_by_carried_gas_weapon(self):
        with tempfile.TemporaryDirectory() as folder:
            content = Path(folder)
            source = 'init()\n{\n}\n'
            self.assertEqual(t6bridge.flame_environment_source(source, content), source)
            (content / 'weapons').mkdir()
            (content / 'weapons/flamer').write_text('WEAPONFILE\\weaponType\\gas\\flameTableFirstPerson\\source_flame')
            report = content / 'weapons.runtime.json'
            report.write_text(json.dumps({'weapons': [], 'table': {'flamer': ''}}))
            self.assertEqual(t6bridge.flame_environment_source(source, content), source)
            report.write_text(json.dumps({'weapons': ['flamer'], 'table': {'flamer': 'flamer'}}))
            initialized = t6bridge.flame_environment_source(source, content)
            self.assertIn('enableflamesystem();', initialized)
            self.assertNotIn('setdvar(', initialized)

    def test_weapon_keeps_flame_table_dependency_and_isolates_its_name(self):
        schema = {'flameTableFirstPerson': 'CSPFT_STRING'}
        weapon = weapons.convert('flamer', {'flameTableFirstPerson': 'authored_flame'}, schema, schema)
        self.assertEqual(weapon.dependencies['flametable'], {'authored_flame'})
        self.assertEqual(weapon.fields['flameTableFirstPerson'], 'waw_flametable/authored_flame')

    def test_nested_table_assets_are_resolved_and_values_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source/weapons/flame'
            source.parent.mkdir(parents=True)
            source.write_text('FLAMETABLEFILE\\name\\flame\\flameVar_streamChunkSpeed\\721.25'
                              '\\fire\\authored_fire\\flameCooldownSound\\authored_cooldown')
            children = Resolver([root / 'source'], None).children('flametable', source)
            self.assertEqual(children, {('material', 'authored_fire'), ('sound', 'authored_cooldown')})
            project = root / 'project'
            entries = weapons.stage_flame_tables([root / 'source'], project, {'flame'})
            result = weapons.read_flame_table(project / entries[0]['file'])
            self.assertEqual(result['flameVar_streamChunkSpeed'], '721.25')
            self.assertEqual(result['fire'], 'waw_material/authored_fire')
            self.assertEqual(result['flameCooldownSound'], 'waw/authored_cooldown')
            self.assertEqual(result['name'], 'waw_flametable/flame')

    def test_missing_or_unknown_table_data_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(weapons.WeaponError, 'missing compiled flame table'):
                weapons.stage_flame_tables([root], root / 'out', {'flame'})
            source = root / 'weapons/flame'
            source.parent.mkdir()
            source.write_text('FLAMETABLEFILE\\unknown_simulation_field\\15')
            with self.assertRaisesRegex(weapons.WeaponError, 'unknown T6 fields'):
                weapons.stage_flame_tables([root], root / 'out', {'flame'})
