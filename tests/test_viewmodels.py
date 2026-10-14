import json
import tempfile
import unittest
from pathlib import Path
from waw2bo2 import viewmodels, weapons


class ViewmodelTests(unittest.TestCase):
    def test_shared_world_model_and_material_keep_shadow_casting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def write(name, data):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            write('weapons.stage.json', {'weapons':[{'name':'gun'}], 'models':{'models':[
                {'name':'waw_xmodel/shared','waw':'shared','materials':['metal']} ]}})
            write('weapons.visuals.json', {'materials':[{'name':'waw_material/metal','notes':[]}],
                                          'material_images':{'waw_material/metal':['source_image']}})
            write('materials/waw_material/metal.json', {'gameFlags':['CASTS_SHADOW','10'], 'textures':[]})
            write('xmodel/waw_xmodel/shared.json', {'lods':[{'file':'model_export/shared.gltf'}]})
            write('model_export/shared.gltf', {'materials':[{'name':'waw_material/metal'}]})
            path = root / 'weapons/gun'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('WEAPONFILE\\gunModel\\waw_xmodel/shared\\worldModel\\waw_xmodel/shared')
            viewmodels.stage_shadow_variants(root)
            fields = weapons.read_info_file(path)
            self.assertNotEqual(fields['gunModel'], fields['worldModel'])
            self.assertEqual(fields['worldModel'], 'waw_xmodel/shared')
            original = json.loads((root/'materials/waw_material/metal.json').read_text())
            clone = json.loads((root/'materials/waw_material/viewmodel_shadowless/metal.json').read_text())
            self.assertIn('CASTS_SHADOW', original['gameFlags'])
            self.assertEqual(clone['gameFlags'], ['10'])
