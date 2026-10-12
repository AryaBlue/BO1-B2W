// Local McDonald's Zombies test: godmode and the original BO1 FAMAS.
// Install under Plutonium/storage/t6/scripts/zm, then restart the map.
// Delete the installed script to remove this test setup.
main()
{
    if ( getdvar( "mapname" ) != "zm_mcdonalds_waw" )
        return;

    level thread test_connections();
}

test_connections()
{
    for ( ;; )
    {
        level waittill( "connected", player );
        player thread test_spawns();
    }
}

test_spawns()
{
    self endon( "disconnect" );
    for ( ;; )
    {
        self waittill( "spawned_player" );
        self enableinvulnerability();
        // Let the map finish assigning its starting loadout first.
        wait 1;
        if ( !self hasweapon( "famas" ) )
            self giveweapon( "famas" );
        self givemaxammo( "famas" );
        self switchtoweapon( "famas" );
        self iprintlnbold( "FAMAS test: godmode enabled" );
    }
}
