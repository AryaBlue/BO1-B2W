import json
from pathlib import Path
import tempfile
import unittest

from waw2bo2 import entities


class ClientModelTests(unittest.TestCase):
    def test_listener_named_client_models_become_server_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entities.json"
            ents = [
                {"classname": "script_model", "targetname": "lamp", "spawnflags": "2", "model": "a"},
                {"classname": "script_model", "targetname": "lamp", "spawnflags": "10", "model": "b"},
                {"classname": "script_model", "targetname": "lamp", "spawnflags": "0", "model": "c"},
                {"classname": "script_model", "targetname": "decor", "spawnflags": "2", "model": "d"},
                {"classname": "trigger_use", "targetname": "lamp", "spawnflags": "2"},
            ]
            path.write_text(json.dumps({"entities": ents}))
            self.assertEqual(entities.network_client_models(path, {"lamp"}), ["lamp (2)"])
            flags = [e.get("spawnflags") for e in json.loads(path.read_text())["entities"]]
        # only client-side script_models the listeners name; other flag bits stay
        self.assertEqual(flags, ["0", "8", "0", "2", "2"])


if __name__ == "__main__":
    unittest.main()
