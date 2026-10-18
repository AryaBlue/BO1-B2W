import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from waw2bo2 import waterbullets

WAW_TABLE = ("BULLET_PEN_TABLE\\small_wood\\72\\small_water\\96\\medium_water\\128\\large_water\\128"
             "\\large_wood\\192")


def _weapon(folder: Path, name: str, **fields) -> None:
    body = "WEAPONFILE" + "".join(f"\\{k}\\{v}" for k, v in fields.items())
    (folder / name).write_text(body, encoding="utf-8")


class WaterBulletsTest(unittest.TestCase):
    def test_depths_come_from_the_waw_table(self):
        self.assertEqual(waterbullets.water_depths(WAW_TABLE), {"small": 96.0, "medium": 128.0, "large": 128.0})

    def test_only_brushes_with_water_contents_count(self):
        clip = SimpleNamespace(brushes=[SimpleNamespace(contents=0x1), SimpleNamespace(contents=0x8000020)])
        self.assertTrue(waterbullets.has_water(clip))
        self.assertFalse(waterbullets.has_water(SimpleNamespace(brushes=[SimpleNamespace(contents=0x1)])))

    def test_rows_keep_hitscan_weapons_that_penetrate_water(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp)
            (content / "weapons").mkdir()
            _weapon(content / "weapons", "zombie_shotgun", weaponType="bullet", penetrateType="medium", shotCount=8,
                    hipSpreadStandMin=4, hipSpreadMax=4, adsSpread=5.5)
            _weapon(content / "weapons", "ray_gun", weaponType="projectile", penetrateType="none", shotCount=0)
            _weapon(content / "weapons", "pistol_none", weaponType="bullet", penetrateType="none", shotCount=1)
            table = {"zombie_shotgun": "zombie_shotgun", "ray_gun": "ray_gun", "pistol_none": "pistol_none",
                     "missing": "missing_file"}
            rows = waterbullets.weapon_rows(content, table, waterbullets.water_depths(WAW_TABLE))
        self.assertEqual(list(rows), ["zombie_shotgun"])
        row = rows["zombie_shotgun"]
        self.assertEqual(row[0], 4.0)
        self.assertEqual(row[9], 5.5)
        self.assertEqual(row[10:], [8, 128.0])

    def test_source_continues_bullets_from_under_the_surface(self):
        source = waterbullets.water_bullets_source({"zombie_colt": [3, 2.5, 2, 6, 5, 4, 4, 1, 4.5, 0.2, 1, 96]})
        self.assertIn('level.waw_water_bullets["zombie_colt"] = waw_water_row( 3, 2.5, 2, 6, 5, 4, 4, 1, 4.5, 0.2, 1, 96 );',
                      source)
        self.assertIn('self waittill( "weapon_fired", weapon );', source)
        self.assertIn('trace["surfacetype"] != "water"', source)
        self.assertIn("magicbullet( weapon, start, start + dir * row[11], self );", source)
        self.assertNotIn("WEAPON_TABLE", source)

    def test_empty_source_is_a_no_op(self):
        source = waterbullets.water_bullets_source({})
        self.assertIn("init()\n{\n}", source)
        self.assertNotIn("weapon_fired", source)


if __name__ == "__main__":
    unittest.main()
