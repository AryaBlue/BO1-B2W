"""WaW bullets keep going through water; T6 bullets stop dealing damage there.

Both games trace bullets against CONTENTS_WATER brushes (mask 0x280E833) and
both use those volumes for player_waterSpeedScale, wading ripples and swim
state, so the WaW water brushes are converted unchanged. The difference is the
penetration loop. After a T6 bullet enters water its forward trace and its
reverse (exit) trace both start inside the water brush; that startsolid branch
of the server bullet loop (t6zm sub_81AA80 in the Steam IDB) spends power and
loops without calling the hit handler, so whatever stands in the water is never
damaged. Measured on Shi No Numa: colt shots through the surface 2/30 hit,
the same targets shot from a point already under the surface 18/30.

The runtime script continues each player bullet that hits water: it rebuilds
the pellet directions from the weapon's own spread fields (the same tan-cone
model both engines use) and fires the bullet on from just under the surface,
as far as WaW's bullet_penetration_sp lets that penetrate type travel through
water.
"""
from __future__ import annotations

from pathlib import Path

from . import weapons

WATER = 0x20
PENETRATION_TABLE = Path("info/bullet_penetration_sp")
PENETRATE_TYPES = ("small", "medium", "large")
SPREAD_FIELDS = ("hipSpreadStandMin", "hipSpreadDuckedMin", "hipSpreadProneMin",
                 "hipSpreadMax", "hipSpreadDuckedMax", "hipSpreadProneMax",
                 "hipSpreadDecayRate", "hipSpreadFireAdd", "hipSpreadMoveAdd", "adsSpread")


def has_water(clip) -> bool:
    return any(brush.contents & WATER for brush in clip.brushes)


def water_depths(table_text: str) -> dict[str, float]:
    """Water penetration depth per penetrate type from a WaW BULLET_PEN_TABLE."""
    values = table_text.strip().split("\\")
    pairs = dict(zip(values[1::2], values[2::2]))
    return {kind: float(pairs[f"{kind}_water"]) for kind in PENETRATE_TYPES if f"{kind}_water" in pairs}


def _number(fields: dict[str, str], key: str) -> float:
    try:
        return float(fields.get(key) or 0)
    except ValueError:
        return 0.0


def weapon_rows(content: Path, table: dict[str, str], depths: dict[str, float]) -> dict[str, list[float]]:
    """T6 weapon name -> spread fields, pellet count and water depth.

    Only hitscan weapons whose penetrate type reaches through water in WaW."""
    rows = {}
    for name in sorted(set(table.values())):
        path = content / "weapons" / name
        if not path.is_file():
            continue
        fields = weapons.read_info_file(path)
        depth = depths.get(fields.get("penetrateType", ""), 0.0)
        if fields.get("weaponType") != "bullet" or depth <= 0:
            continue
        shots = max(1, int(_number(fields, "shotCount")))
        rows[name] = [_number(fields, key) for key in SPREAD_FIELDS] + [shots, depth]
    return rows


def _num(value: float) -> str:
    return f"{value:g}"


def water_bullets_source(rows: dict[str, list[float]]) -> str:
    if not rows:
        return "// waw2bo2: no water brushes or no bullet weapon penetrates water.\n\ninit()\n{\n}\n"
    table = "".join(f'    level.waw_water_bullets["{name}"] = waw_water_row( {", ".join(_num(v) for v in row)} );\n'
                    for name, row in sorted(rows.items()))
    return WATER_BULLETS_GSC.replace("    // WEAPON_TABLE\n", table)


WATER_BULLETS_GSC = r'''// waw2bo2: WaW bullets go on through water; T6 never damages what stands in it.
// See waw2bo2/waterbullets.py. Each row: hip stand/ducked/prone min, hip
// stand/ducked/prone max, decay rate, fire add, move add, ADS spread, pellets,
// WaW water penetration depth.

init()
{
    level.waw_water_bullets = [];
    // WEAPON_TABLE
    level thread waw_water_bullet_players();
}

waw_water_row( a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11 )
{
    row = [];
    row[0] = a0;
    row[1] = a1;
    row[2] = a2;
    row[3] = a3;
    row[4] = a4;
    row[5] = a5;
    row[6] = a6;
    row[7] = a7;
    row[8] = a8;
    row[9] = a9;
    row[10] = a10;
    row[11] = a11;
    return row;
}

waw_water_bullet_players()
{
    for (;;)
    {
        level waittill( "connected", player );
        player thread waw_water_bullets();
    }
}

waw_water_bullets()
{
    self endon( "disconnect" );
    self.waw_water_spread = 0;
    self.waw_water_spread_time = gettime();

    for (;;)
    {
        self waittill( "weapon_fired", weapon );

        if ( !isdefined( weapon ) || !isdefined( level.waw_water_bullets[weapon] ) )
            continue;

        row = level.waw_water_bullets[weapon];
        spread = self waw_water_spread( row );
        eye = self geteye();
        angles = self getplayerangles();
        forward = anglestoforward( angles );
        right = anglestoright( angles );
        up = anglestoup( angles );
        cone = tan( spread );

        for ( i = 0; i < row[10]; i++ )
        {
            radius = randomfloat( 1 ) * cone;
            turn = randomfloat( 360 );
            dir = vectornormalize( forward + right * ( cos( turn ) * radius ) + up * ( sin( turn ) * radius ) );
            trace = bullettrace( eye, eye + dir * 8192, 1, self );

            if ( !isdefined( trace["surfacetype"] ) || trace["surfacetype"] != "water" || isdefined( trace["entity"] ) )
                continue;

            start = trace["position"] + dir * 0.5;
            magicbullet( weapon, start, start + dir * row[11], self );
        }
    }
}

// Hip spread as both engines evolve it: stance minimum, plus the fire add
// decaying at its rate, plus the move add; blended to ADS spread.
waw_water_spread( row )
{
    stance = self getstance();
    low = row[0];
    high = row[3];

    if ( stance == "crouch" )
    {
        low = row[1];
        high = row[4];
    }
    else if ( stance == "prone" )
    {
        low = row[2];
        high = row[5];
    }

    now = gettime();
    self.waw_water_spread = max( 0, self.waw_water_spread - row[6] * ( now - self.waw_water_spread_time ) / 1000 );
    self.waw_water_spread_time = now;
    velocity = self getvelocity();
    moving = min( 1, length( ( velocity[0], velocity[1], 0 ) ) / max( 1, getdvarfloat( "g_speed" ) ) );
    hip = min( high, low + self.waw_water_spread + row[8] * moving );
    self.waw_water_spread = min( high - low, self.waw_water_spread + row[7] );
    ads = self playerads();
    return hip + ( row[9] - hip ) * ads;
}
'''
