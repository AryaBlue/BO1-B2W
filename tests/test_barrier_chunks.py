import json
import tempfile
import unittest
from pathlib import Path

from waw2bo2 import barriers


class ReplacedChunkTests(unittest.TestCase):
    def test_native_barrier_windows_drop_their_source_brushes(self):
        with tempfile.TemporaryDirectory() as tmp:
            bsp = Path(tmp)
            es = [{'classname': 'script_struct', 'targetname': 'exterior_goal', 'target': 'w1'},
                  {'classname': 'zbarrier_zmcore_BasicWoodBarrier', 'targetname': 'w1'},
                  {'classname': 'script_struct', 'targetname': 'w1'},
                  {'classname': 'node_negotiation_begin', 'targetname': 'w1'},
                  *[{'classname': 'script_brushmodel', 'targetname': 'w1', 'model': f'*{i}'} for i in range(6)],
                  {'classname': 'script_brushmodel', 'targetname': 'w1', 'script_noteworthy': 'clip', 'model': '*6'},
                  # a goal BO2 does not own (no native zbarrier) keeps its brushes
                  {'classname': 'script_struct', 'targetname': 'exterior_goal', 'target': 'w2'},
                  {'classname': 'script_brushmodel', 'targetname': 'w2', 'model': '*7'},
                  {'classname': 'script_brushmodel', 'targetname': 'door', 'model': '*8'}]
            (bsp / 'entities.json').write_text(json.dumps({'entities': es}))
            self.assertEqual(barriers.drop_replaced_chunks(bsp), {'windows': 1, 'dropped_brushes': 7})
            kept = json.loads((bsp / 'entities.json').read_text())['entities']
            self.assertEqual([e.get('model') for e in kept if e['classname'] == 'script_brushmodel'], ['*7', '*8'])
            self.assertEqual(sum(e.get('targetname') == 'w1' for e in kept), 3)


if __name__ == '__main__':
    unittest.main()
