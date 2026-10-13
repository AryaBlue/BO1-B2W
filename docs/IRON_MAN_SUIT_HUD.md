# Iron Man suit depletion and HUD investigation

The supplied screenshots report a persistent helmet and two masks after suit
depletion. The reporter's suit and action sequence are unknown. A depleted
helmet remaining visible is authored behavior; overlapping helmets are not
established as a conversion regression by these screenshots alone.

## Likely overlapping-mask mechanism in the source map

Cheese Cube Unlimited's original `_iron_man_mk3::jarvis_power_supply` starts
`mask_power_out` when the battery reaches zero, then assigns
`self.used_suit = undefined`. It leaves `self.mk3_suit` at 1.
`mask_power_out` destroys its HUD only when `self.mk3_suit == 0`.

Another suit's deployment tests `!isdefined(iron_guy.used_suit)` and sets its
own active flag. It does not clear the other suit's flag. Thus a depleted
Mk3 helmet can remain present when another suit is equipped. Mk4, Mk5, Mk6
and Mk16 have the same depletion pattern. Mk1 also unlocks `used_suit`
without clearing its active flag, and its persistent mask waits for that
flag to clear. War Machine's depletion path does not unlock `used_suit`.

The converted scripts preserve these assignments and mask lifetime checks.
WaW and BO2 `create_simple_hud`/`destroy_hud` helpers have matching behavior
for valid HUDs. The converter has not added a map-specific suit state rewrite.
A source gameplay repair should keep ownership of the empty suit until its
return/charging path completes, or explicitly retire the previous suit's
entire lifecycle before allowing another deployment. Clearing just the mask
or active flag risks leaving deployment counts, weapons, movement and charge
threads inconsistent.

## Shared HUD cleanup adaptation

Mk16 can destroy its `self.hint_hud` from several cleanup paths and later use
that field again. This exposes a general missing/repeated HUD receiver case.
The converter already guarded native `destroyElem`; it now also guards the
native Zombies `destroy_hud` helper. A resolved zero-argument cleanup on a
simple or dotted receiver is lowered to `waw_destroy_hud(element)`. The wrapper
tests whether the HUD exists before calling the native helper, which still
owns destruction and HUD-count bookkeeping. Local source destructors retain
their behavior. This protects caller continuation; it does not resolve the
source's overlapping-suit ownership or use-after-destroy logic.

## Validation and gameplay checks

506 unit tests pass. All 99 staged scripts compile and match their linked
fastfile bytes. The candidate retains the water fix: model 242 has 32 authored
water triangles and contents 0x20. Evidence is under
`work/suit_hud_check/`, including `verification.json` and the candidate in
`linked/`. The candidate has not replaced the installed map while the user
tests the water fix. Live suit behavior remains unverified.

For a useful reproduction, deplete Mk3, then try equipping a different suit
before returning Mk3 to its station. Record which suit is worn and whether
each station still offers a return/charge action. Compare with returning
the depleted suit before deploying another. Separately test Mk16 depletion
after toggling cloak, then return and recharge it; monitor console errors and
whether weapons, sprint/jump and cloak return to their expected states.
