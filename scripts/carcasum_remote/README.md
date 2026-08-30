# `carcasum_remote` — the phone plays Carcasum, over the tailnet

**Status: BUILT 2026-08-30. Serves the owner session in
[`measurement/carcasum_owner_session_prep/`](../../measurement/carcasum_owner_session_prep/PROTOCOL.md).**

The adaptation-share discriminator needs the owner to play the CALIBRATED
Carcasum opponent **under his normal phone conditions** — same app, same board,
same archive, same everything except who is on the other side. This is that:
the Kotlin app gains a "Remote Carcasum" opponent, and every opponent move is a
tailnet round-trip to a small daemon on the laptop that wraps the EXISTING
engine-vs-engine Carcasum bridge. **Nothing is ported to Android.**

| file | what it is |
|---|---|
| [`server.py`](server.py) | the daemon: `/health`, `/move`, `/end`. Wraps `scripts/carcasum_match/match.py` — no game logic of its own |
| [`launch_laptop.sh`](launch_laptop.sh) | detached launch on the laptop (`systemd-run --user --scope` + linger), gates checked before the socket binds |
| [`smoke_client.py`](smoke_client.py) | end-to-end smoke: plays a whole game against the daemon with random-legal moves, no phone needed |

Phone side: `android_bridge.RemoteOpponent` + the `OpponentMode` selector in
Settings. Tests: [`tests/test_carcasum_remote_server.py`](../../tests/test_carcasum_remote_server.py),
[`tests/android/test_bridge_remote_opponent.py`](../../tests/android/test_bridge_remote_opponent.py),
`android/app/src/test/java/com/jishal/carcassonne/OpponentModeTest.kt`.

---

## Run it

```bash
ssh laptop-wsl 'bash -s' < scripts/carcasum_remote/launch_laptop.sh
```

It prints the tailnet URL. Put that in the phone: **Settings → Opponent → Remote
Carcasum → Change server…**. Then start a game as normal.

Smoke it without a phone (plumbing check — note the reduced budget):

```bash
# on the laptop, against a server started with --budget-ms 50
scripts/carcasum_remote/smoke_client.py --url http://100.x.y.z:8971 \
    --deck-seed 4242 --blip-every 5
```

---

## The three things worth knowing before you rely on it

### 1. It reuses the bridge; it does not re-implement it

`scripts/carcasum_match/match.py` already owns the whole correspondence between
our engine and Carcasum — the coordinate frame taken live from the handshake,
the rotation-period reduction, the meeple half-edge label rotation, the
forward-map-and-match inversion discipline, the void taxonomy, the score
diffing. `server.py` injects an agent and a per-ply callback into
`play_one_match` (the two additive `agent=` / `on_apply=` parameters) and adds
nothing else. A second inverter would be a second thing that can quietly
disagree with our engine about what a Carcasum move means, and that disagreement
would arrive dressed as a rules finding.

### 2. Retry is idempotent; RESUME AFTER A SERVER DEATH is not

Every `/move` carries the full `(deck_seed, actions)` root-replay pair — the
same lossless representation the phone archives already use — and the answer is
a pure function of `(session, ply index)` read out of the log the server already
committed. So a dropped connection, a sleeping phone, a backgrounded app: the
client re-sends and gets the identical move, with no second search and no second
move applied. That is tested (`--blip-every`, and the JVM/pytest retry tests).

**What it cannot do is rebuild a game.** Carcasum's RNG seed is compile-time only
and the driver protocol takes a forced *deck*, never a forced *history* — so
replaying a log into a FRESH Carcasum process yields a different opponent from
the one that played. The server therefore holds the live process for the game's
duration and treats the client's log as a consistency key. If the daemon dies
mid-game, that game is over: the phone gets `session_lost`, and the honest
answer is to log it `abandoned` per PROTOCOL.md §3. Making this resumable means
teaching the C++ driver to load a `MoveHistory`, which changes the binary and
therefore breaks the `G-BINARY` anchor identity — deliberately not done.

An app restart alone is fine: `game_id` is derived from `(deck_seed, seat)` and
the save carries `remote_url`, so a restored game reconnects to the same live
session.

### 3. ⛔ The archive label is the thing that protects the program

A remote game is archived with `opponent: "carcasum_remote_5000ms"`, never
`"champion"`, and [`scripts/e4_archives.py`](../e4_archives.py) excludes anything
that is not exactly `"champion"` from the owner-vs-champion E4 anchor — with an
**absent** stamp excluded too, loudly. Both halves are needed: a label nothing
conditions on protects nothing.

That anchor (`A = +13.265 pts/game`, n=49) is the single number the session's
whole read is chained through. One Carcasum game pooled into it moves the answer
in the direction that manufactures the headline result.

The archive also carries a `remote` block — the server's binary sha256, its
`G-BINARY` gate state, and the live tiny-city probe result — so a remote game is
auditable against `RULES_DELTA.md` §2.1 without trusting a note somebody typed.

---

## Gates (`G-BINARY`, PROTOCOL.md §7)

The daemon refuses to bind the socket unless BOTH pass:

1. **sha256 identity** — the binary must be the anchor binary named in
   `SETUP.md` §2 (`c090847e…`). A different hash is a different opponent and the
   session's `B` anchor does not apply to it. `--allow-any-binary` overrides and
   stamps `binary_gate: "OVERRIDDEN"` into `/health` and every `/move` response,
   so an unvetted session can never be mistaken for an anchored one.
2. **A live scoring probe** — a constructed plain two-tile city must score **4**,
   not upstream's original-2000 **2**. Same construction as
   `tests/test_carcasum_rules_patch.py`. A patch that compiles is not a patch
   that is live in the binary.

## Security

**None beyond the tailnet.** Plain HTTP, no auth, and `--host` has no default so
nobody binds `0.0.0.0` by accident — this endpoint spawns processes. The Android
side needs `INTERNET` and `usesCleartextTraffic` for the same reason
(`AndroidManifest.xml` carries the note); the app makes no other network call of
any kind, and sends nothing but `(deck_seed, actions)`.
