import copy
import json
from pathlib import Path
import tempfile
import unittest

from waw2bo2 import modelhitboxes


class ModelHitboxAuditTests(unittest.TestCase):
    def test_audit_matches_bone_names_and_detects_lost_invisible_head_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            source, built = Path(temp) / 'source', Path(temp) / 'built'
            for root in (source, built):
                (root / 'xmodel').mkdir(parents=True)
            head = {'bone': 'j_head', 'mins': [-1.5, -4.1, -3.7], 'maxs': [7.7, 5.9, 3.7],
                    'offset': [3.1, 0.9, 0], 'radiusSquared': 59.9, 'hitloc': 'head'}
            neck = dict(head, bone='j_neck')
            (source / 'xmodel/body.json').write_text(json.dumps({'type': 'animated', 'boneInfo': [head, neck]}))
            target = built / 'xmodel/body.json'
            target.write_text(json.dumps({'boneInfo': [neck, head]}))
            self.assertTrue(modelhitboxes.has_authored_hitboxes(source))
            self.assertEqual(modelhitboxes.audit(source, built), {'models': 1, 'bones': 2, 'errors': []})
            collapsed = copy.deepcopy(head)
            collapsed.update(mins=[0, 0, 0], maxs=[0, 0, 0], offset=[0, 0, 0], radiusSquared=0)
            target.write_text(json.dumps({'boneInfo': [neck, collapsed]}))
            failed = modelhitboxes.audit(source, built)
            self.assertEqual(len(failed['errors']), 4)
            self.assertTrue(all('j_head' in error for error in failed['errors']))
            misclassified = dict(head, hitloc='none')
            target.write_text(json.dumps({'boneInfo': [neck, misclassified]}))
            self.assertIn('hit location changed', modelhitboxes.audit(source, built)['errors'][0])
            target.write_text(json.dumps({'boneInfo': [neck]}))
            self.assertIn('missing hitbox bone j_head', modelhitboxes.audit(source, built)['errors'][0])


if __name__ == '__main__':
    unittest.main()
