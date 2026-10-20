#include clientscripts\mp\_utility;

init()
{
    registersystem( "waw_sun", ::sun_state );
    level.waw_global_vision = [];
    level.waw_player_vision = [];
    registersystem( "waw_vision_global", ::global_vision_state );
    registersystem( "waw_vision_player", ::player_vision_state );
}

global_vision_state( localclientnum, state )
{
    if ( state == "" )
        return;
    level.waw_global_vision[localclientnum] = int( state );
    apply_vision( localclientnum );
}

player_vision_state( localclientnum, state )
{
    if ( state == "" )
        return;
    level.waw_player_vision[localclientnum] = int( state );
    apply_vision( localclientnum );
}

apply_vision( localclientnum )
{
    index = 0;
    if ( isdefined( level.waw_global_vision[localclientnum] ) )
        index = level.waw_global_vision[localclientnum];
    if ( isdefined( level.waw_player_vision[localclientnum] ) && level.waw_player_vision[localclientnum] >= 0 )
        index = level.waw_player_vision[localclientnum];
    setdvar( "vc_LUT", index + 1 );
}

// Both sun tweak dvars are SAVED (0x1200): plain setdvar is refused for them.
sun_state( localclientnum, state )
{
    if ( !isdefined( level.waw_saved_sun ) )
    {
        level.waw_saved_sun = spawnstruct();
        level.waw_saved_sun.color = getdvar( #"r_lightTweakSunColor" );
        level.waw_saved_sun.light = getdvar( #"r_lightTweakSunLight" );
    }
    if ( state == "" )
        return;
    if ( state == "reset" )
    {
        setsaveddvar( "r_lightTweakSunColor", level.waw_saved_sun.color );
        setsaveddvar( "r_lightTweakSunLight", level.waw_saved_sun.light );
        return;
    }
    values = strtok( state, " " );
    if ( values.size != 3 )
        return;
    // WaW sun values are gamma; T6 sun light is linear (as the world sun)
    r = float( values[0] ) * float( values[0] );
    g = float( values[1] ) * float( values[1] );
    b = float( values[2] ) * float( values[2] );
    strength = max( r, max( g, b ) );
    color = "0 0 0";
    if ( strength > 0 )
        color = ( r / strength ) + " " + ( g / strength ) + " " + ( b / strength );
    setsaveddvar( "r_lightTweakSunColor", color );
    setsaveddvar( "r_lightTweakSunLight", strength );
}

// Client loop watchdog: see the compat GSC's waw_loop_guard.
waw_loop_guard( id )
{
    now = gettime();
    if ( !isdefined( level.waw2bo2_loop_time ) )
    {
        level.waw2bo2_loop_time = [];
        level.waw2bo2_loop_count = [];
        level.waw2bo2_loop_reported = [];
    }
    if ( !isdefined( level.waw2bo2_loop_time[id] ) || level.waw2bo2_loop_time[id] != now )
    {
        level.waw2bo2_loop_time[id] = now;
        level.waw2bo2_loop_count[id] = 0;
        return;
    }
    level.waw2bo2_loop_count[id]++;
    if ( level.waw2bo2_loop_count[id] < 500 )
        return;
    level.waw2bo2_loop_count[id] = 0;
    if ( !isdefined( level.waw2bo2_loop_reported[id] ) )
    {
        level.waw2bo2_loop_reported[id] = 1;
        println( "WAW2BO2 SPIN client " + id + " (500 passes in one frame; waiting a frame so the thread survives)" );
    }
    wait 0.01;
}
