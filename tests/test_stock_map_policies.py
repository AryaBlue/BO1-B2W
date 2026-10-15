import tempfile
import unittest
from pathlib import Path

from waw2bo2 import gsc, gscport
from waw2bo2.t6api import T6Api

ROUND_SPAWNING = '''
round_spawning()
{
	ai_calculate_health();
	count = 0;
	players = get_players();
	max = level.zombie_vars["zombie_max_ai"];
	multiplier = level.round_number / 5;
	if( multiplier < 1 )
		multiplier = 1;
	max += int( ( ( get_players().size - 1 ) * level.zombie_vars["zombie_ai_per_player"] ) * multiplier );
	if(level.round_number < 3 && level.script == "nazi_zombie_asylum")
		max = 6;
	else if ( level.first_round )
		max = int( max * 0.2 );
	level.zombie_total = max;
	while( count < max )
		count++;
}
'''

PERKS = '''
vending_trigger_think()
{
	perk = self.script_noteworthy;
	for( ;; )
	{
		self waittill( "trigger", player );
		cost = level.zombie_vars["zombie_perk_cost"];
		switch( perk )
		{
		case "specialty_armorvest":
			cost = 2500;
			break;
		case "specialty_quickrevive":
			cost = 1500;
			break;
		}
		player SetPerk( perk );
	}
}
'''


def _api() -> T6Api:
    return T6Api(builtins={"int": (1, 1), "get_players": (0, 0), "getplayers": (0, 0)},
                 scripts={"maps\\mp\\zombies\\_zm": {"init": 0},
                          "maps\\mp\\zombies\\_zm_utility": {"get_players": 0}},
                 methods={"setperk": (1, 1), "waittill": (1, 3)})


def _port(root: Path, stock_map: bool, level: str = "testmap") -> tuple[str, str]:
    (root / "maps").mkdir(exist_ok=True)
    (root / f"maps/{level}.gsc").write_text(
        "main() { maps\\_zombiemode::main(); maps\\_zombiemode_perks::init(); }")
    (root / "maps/_zombiemode.gsc").write_text("main() {}\n" + ROUND_SPAWNING)
    (root / "maps/_zombiemode_perks.gsc").write_text("init() { thread vending_trigger_think(); }\n" + PERKS)
    gscport.port_map(gscport.Sources([root], [], root), _api(), level, root / "out", stock_map=stock_map)
    generated = root / "out/maps/mp/waw"
    perks = (generated / "_zombiemode_perks.gsc")
    return (generated / "_waw2bo2_core.gsc").read_text(), perks.read_text() if perks.exists() else ""


class StockMapPolicyTests(unittest.TestCase):
    def test_source_round_count_formula_becomes_bo2_max_zombie_func(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, _ = _port(Path(tmp), stock_map=False)
            fn = core[core.index("zombiemode__round_spawning_total( bo2_max )"):]
            fn = fn[:fn.index("\n}") + 2]
            self.assertIn('max = level.zombie_vars["zombie_max_ai"];', fn)
            self.assertIn("max = int( max * 0.2 );", fn)
            self.assertIn("level.waw_script", fn)   # level.script is the WaW level name
            self.assertIn("return max;", fn)
            self.assertNotIn("count", fn)
            self.assertNotIn("ai_calculate_health", fn)
            self.assertIn("level.max_zombie_func = ::zombiemode__round_spawning_total;", core)
            self.assertIn("zombiemode__round_spawning_total_register();", core)

    def test_round_formula_reading_earlier_locals_is_reported_not_ported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "maps").mkdir()
            (root / "maps/_zombiemode.gsc").write_text(
                "round_spawning() { players = get_players(); max = players.size * 6; level.zombie_total = max; }")
            tr = gscport.Translator(gscport.Sources([root], [], None), _api(), gscport.PortReport())
            self.assertIsNone(tr.extract_round_total())
            self.assertTrue(any("earlier locals players" in e for e in tr.report.errors))

    def test_custom_maps_keep_their_own_quick_revive_logic(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, perks = _port(Path(tmp), stock_map=False)
            self.assertNotIn("waw2bo2_stock_map_policies", core)
            self.assertNotIn("waw_stock_perk_cost", perks)
            self.assertIn("cost = 1500;", perks)

    def test_stock_maps_price_solo_quick_revive_through_the_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            core, perks = _port(Path(tmp), stock_map=True, level="nazi_zombie_sumpf")
            self.assertIn('cost = maps\\mp\\waw\\_waw2bo2_compat::waw_stock_perk_cost( '
                          '"specialty_quickrevive", 1500 );', perks)
            self.assertIn("cost = 2500;", perks)   # other perks keep the source price
            self.assertIn('level.waw2bo2_solo_revive["cost"] = 500;', core)
            self.assertIn('level.waw2bo2_solo_revive["limit"] = 3;', core)
            self.assertIn('&"ZOMBIE_PERK_QUICKREVIVE_SOLO"', core)
            self.assertIn("waw_stock_health_overflow()", core)
            self.assertIn("\twaw2bo2_stock_map_policies();", core)

    def test_der_riese_keeps_bo2_health_but_gets_solo_revive(self):
        policy = gscport.stock_map_policy(gscport.API["stock_map_policies"], "nazi_zombie_factory")
        self.assertNotIn("waw_stock_health_overflow", policy)
        self.assertIn("waw_stock_solo_revive()", policy)
        self.assertIn("waw_stock_health_overflow",
                      gscport.stock_map_policy(gscport.API["stock_map_policies"], "nazi_zombie_asylum"))

    def test_compat_runtime_defines_the_policy_functions(self):
        script = gsc.parse((gscport.COMPAT_DIR / "_waw2bo2_compat.gsc").read_text(), "compat")
        for name in ("waw_stock_perk_cost", "waw_stock_solo_revive", "waw_stock_solo_revive_bought",
                     "waw_stock_health_overflow", "waw_round_health", "waw_player_damage_override",
                     "waw_linkto", "waw_linked_trigger_contacts"):
            self.assertIn(name, script.functions)
        health = script.functions["waw_round_health"]
        body = gsc.emit(script.tokens[health.body_open:health.body_close + 1])
        self.assertIn("if ( health <= 0 )\n        return start;", body)

    def test_explicit_waw_damage_override_call_keeps_waw_semantics(self):
        self.assertEqual(gscport.API["function_renames"]["player_damage_override"],
                         "maps\\mp\\waw\\_waw2bo2_compat::waw_player_damage_override")


if __name__ == "__main__":
    unittest.main()
