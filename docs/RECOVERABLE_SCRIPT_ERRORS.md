# Recoverable script errors and buildable item semantics

The converter must preserve WaW's continuation after recoverable builtin
parameter errors. An invalid call must remain visible in the conversion
report, but it must not park the source thread forever or receive invented
arguments.

Native inspection of the mapped WaW executable establishes this behavior:

- `MoveTo` (`0x531E60`) reads a vector at argument 0 and movement timing
  through `0x531D30`, which requires a positive duration at argument 1.
  An entity and no duration is invalid; it has no implicit origin/time default.
- The VM (`0x693E80`) enters through `_setjmp` at `0x693EBE`. Recoverable
  script errors reach its handler at `0x696FCD`.
- The builtin recovery cases 62–75 at `0x6972F8` call `0x693DA0` to remove
  argument references, create an undefined result (`type = 0`), then jump
  back to the dispatch loop at `0x693EA0`. The bytecode position has already
  advanced past the call. Terminal errors and developer-mode reporting are
  separate paths; this is not a claim that every VM error is recoverable.

T6 refuses to resolve a builtin call with too few arguments. A generated
reporting stub with an implicit undefined return implements this continuation
without emitting the invalid native call. The former `waw2bo2_never` wait
was based on an incorrect assumption about WaW error recovery.

Cheese Cube Unlimited exposes the difference: its rising mover first makes
an invalid one-argument `MoveTo`, waits 97 seconds, plays its alarm, waits
3 seconds, then runs `MoveZ(4600, 2000)`. The map's own contact check and
lethal damage code remain intact. No map source is patched.

The assembly path also exposed two general compatibility differences:

- A scripted animation item can retain default melee damage and put its idle
  animation in `meleeAnim`. That placeholder does not establish a held melee
  attack. The converter only synthesizes `useAsMelee` for a distinct melee
  animation, preserving explicitly authored values. This keeps the assembly
  knuckle animation and perk bottles out of that inference.
- WaW `SetVisibleToPlayer` (`0x5186B0`) first sets both client-mask words to
  all hidden, then clears the requested player's bit. T6 (`0x848B90`) only
  clears a bit in the existing mask. The wrapper first calls
  `SetInvisibleToAll`, then T6 `SetVisibleToPlayer`, preserving exclusive
  ownership of placement triggers. T6 `UseTriggerRequireLookAt` (`0x84B700`)
  retains the source's zero-argument behavior; it needs no adaptation.

These are converter fixes, not confirmation that the entire Iron Man suit
works in gameplay. Its normal power assembly, six-part construction,
purchase, movement and multiplayer behavior still require an in-game test.
The source gates one suit part on its buildable power switch, which uses a
knuckle animation and the retained `weapon_change_complete` event.

Local build and validation evidence is kept under
`work/cheese_quirks_20261012/`.
