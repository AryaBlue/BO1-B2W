import tempfile
import unittest
from pathlib import Path

from waw2bo2 import gscport
from waw2bo2.t6api import T6Api


class BuiltinArgumentCountTest(unittest.TestCase):
    """WaW raises a runtime error, ending the thread, when a builtin gets too few
    arguments; T6 refuses to link the call (Cheese Cube: ``ent MoveTo(ent2)``)."""

    def translate(self, body: str) -> gscport.Translator:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "maps").mkdir()
            (root / "maps/test.gsc").write_text("main()\n{\n" + body + "\n}\n")
            translator = gscport.Translator(gscport.Sources([root], [], None),
                                            T6Api({}, {}, methods={"moveto": (2, 4), "movez": (2, 4)}),
                                            gscport.PortReport())
            self.source = translator.translate(r"maps\test")
            return translator

    def test_too_few_arguments_stub_stops_the_thread(self):
        translator = self.translate("\tcheese MoveTo(start);\n\tcheese MoveZ( 4600, 2000 );")
        self.assertIn("::stub_moveto_1args_T6_takes_2_4_WaW_runtime_error_ends_the_thread(start);", self.source)
        self.assertIn("cheese MoveZ( 4600, 2000 );", self.source)
        stubs = translator.stub_source()
        body = stubs[stubs.index("stub_moveto_1args"):]
        self.assertIn('level waittill( "waw2bo2_never" );', body.split("}")[0])

    def test_too_many_arguments_are_dropped_not_halted(self):
        translator = self.translate("\tcheese MoveZ( 1, 2, 0, 0, 5 );")
        self.assertIn("cheese MoveZ( 1, 2, 0, 0", self.source)
        self.assertNotIn("waw2bo2_never", translator.stub_source())


if __name__ == "__main__":
    unittest.main()
