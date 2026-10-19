import tempfile
import unittest
from pathlib import Path

from waw2bo2 import gscport
from waw2bo2.t6api import T6Api

ZOMBIEMODE = """main()
{
\tlevel thread check_for_jugg_perk();
}

check_for_jugg_perk()
{
\twhile(true)
\t{
\t\tplayers = getplayers();
\t\tfor(i = 0; i < players.size; i++)
\t\t{
\t\t\tif(players[i] hasperk("specialty_armorvest"))
\t\t\t{
\t\t\t\tif( !flag( "dog_round" ) )
\t\t\t\t\tplayers[i].health += 40;
\t\t\t\telse
\t\t\t\t\tplayers[i].health += 3;
\t\t\t\tif(players[i].health > 160)
\t\t\t\t\tplayers[i].health = 160;
\t\t\t}
\t\t}
\t\twait(0.5);
\t}
}
"""
PERKS = """vending_trigger_think()
{
\tif(perk == "specialty_armorvest")
\t{
\t\tplayer.maxhealth = 160;
\t\tplayer.health = 160;
\t}
}
"""


class JuggernogTest(unittest.TestCase):
    """WaW's Juggernog: 160 health and the 0.5 s regen loop (3 during dog rounds)."""

    def hooks(self, zombiemode: str, perks: str) -> tuple[list[str], gscport.Translator]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "maps").mkdir()
            (root / "maps/_zombiemode.gsc").write_text(zombiemode)
            (root / "maps/_zombiemode_perks.gsc").write_text(perks)
            translator = gscport.Translator(gscport.Sources([root], [], None), T6Api({}, {}), gscport.PortReport())
            return translator.juggernog_hooks(), translator

    def test_source_health_and_regen_loop_are_carried_over(self):
        calls, translator = self.hooks(ZOMBIEMODE, PERKS)
        self.assertIn('level.zombie_vars["zombie_perk_juggernaut_health"] = 160;', calls)
        self.assertIn(f"level thread {gscport.CORE}::zombiemode__check_for_jugg_perk();", calls)
        self.assertIn(("maps\\_zombiemode", "check_for_jugg_perk"), translator.core_funcs)

    def test_maps_without_the_loop_get_no_thread(self):
        calls, _ = self.hooks("main()\n{\n}\n\ncheck_for_jugg_perk()\n{\n}\n", "")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
