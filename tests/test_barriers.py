import json
import struct
import tempfile
import unittest
from pathlib import Path
from waw2bo2 import barriers


class BarrierTests(unittest.TestCase):
    def test_repaired_delta_is_read_from_final_key_not_a_guessed_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'repair'
            # 4 frames, two translation keys at 0 and 3, no delta rotation.
            path.write_bytes(struct.pack('<3H2BH2H2BB6f6H', 19, 4, 1, 2, 2, 30,
                                         0, 2, 0, 3, 0, -10, 0, -20, 40, 0, 60,
                                         0, 0, 0, 65535, 0, 65535))
            self.assertEqual(barriers.repaired_translation(path), (30, 0, 40))
            path.write_bytes(struct.pack('<3H2BH2H3f', 19, 4, 1, 2, 2, 30, 0, 1, 33, 0, 44))
            self.assertEqual(barriers.repaired_translation(path), (33, 0, 44))

    def test_boards_match_source_plane_without_moving_goal_or_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'raw/xanim').mkdir(parents=True)
            (root / 'raw/xanim/repair').write_bytes(
                struct.pack('<3H2BH2H3f', 19, 4, 1, 2, 2, 30, 0, 1, 30, 0, 40))
            goal = {'targetname': 'exterior_goal', 'target': 'win', 'origin': '10 20 0', 'angles': '0 90 0'}
            entry = {'classname': 'script_struct', 'targetname': 'win', 'origin': '10 68 0'}
            board = {'classname': 'script_brushmodel', 'targetname': 'win', 'script_noteworthy': '1',
                     'origin': '10 66 40'}
            barrier = {'classname': 'zbarrier_zmcore_BasicWoodBarrier', 'targetname': 'win',
                       'origin': '10 68 0', 'zbarriernumboards': '1', 'zbarrierboardanim1': 'repair'}
            path = root / 'entities.json'
            path.write_text(json.dumps({'entities': [goal, entry, board, barrier]}))
            result = barriers.align_native_boards(root, root)
            es = json.loads(path.read_text())['entities']
            self.assertEqual(es[0], goal)
            self.assertEqual(es[1], entry)
            origin = [float(x) for x in es[3]['origin'].split()]
            self.assertAlmostEqual(origin[1] + 30, 66)
            self.assertLess(origin[1], 66)  # native attack slots stay outside
            self.assertEqual(result['aligned'][0]['root_advance'], 16)
            barriers.align_native_boards(root, root)
            self.assertEqual(json.loads(path.read_text())['entities'], es)
