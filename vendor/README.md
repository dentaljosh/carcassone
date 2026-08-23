# `vendor/` — third-party source trees, vendored with patches

Same discipline as [`engine/`](../engine/): the upstream tree is copied in **without its
`.git`**, pinned by commit sha, and then patched. Do **not** `git pull` upstream into a vendored
tree — we vendor specifically to keep the patches. Re-extract only if you also re-apply them.

Every entry below states its upstream, its pin, its licence, and where its patch list lives.

---

## `carcasum/` — Carcasum (Yannick Müller, 2014)

| | |
|---|---|
| upstream | `https://github.com/TripleWhy/Carcasum` |
| **pinned commit** | **`5f5e3654d31ce8cef0eebeb80a7fb989ef7c2550`** (`Merge branch 'master' into release`, 2014-07-24) |
| licence | **AGPL-3.0** — see [`carcasum/LICENSE`](carcasum/LICENSE) |
| language | C++11 / Qt 5 (`QT += core`; the `tournament` and `driver` targets also link QtGui because the `.pro` does not `QT -= gui`) |
| upstream status | dead — last push 2014-07 |
| what it is | an MCTS-with-chance-nodes Carcassonne program from a master's thesis, plus a flat Monte-Carlo player, a 1-ply UCB player, three greedy heuristics, and a native port of the JCloisterZone AI |
| **why we vendored it** | it is the only candidate in two rounds of external-reference sweeping that clears every gate at once — exactly our rules scope (2p, base + farmers, no expansions), an open licence, a working headless path, and — uniquely — **a budget knob**. See [`docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md`](../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md) §2. |
| **patch list** | [`carcasum/CARCASUM_PATCHES.md`](carcasum/CARCASUM_PATCHES.md) — every edit, why, and whether it is a *build* fix or a *rules* fix. Kept minimal and re-appliable. |
| harness | [`scripts/carcasum_match/`](../scripts/carcasum_match/) — protocol in `PROTOCOL.md`, driver in `carcasum/Carcasum/driver/main.cpp` |
| toolchain | Qt5 is not installed system-wide on the local box and `sudo` needs a password, so the build uses a **rootless** prefix at `/home/doctor/opt/carcasum-toolchain`, reproduced by [`scripts/carcasum_match/bootstrap_toolchain.sh`](../scripts/carcasum_match/bootstrap_toolchain.sh) (downloads `.deb`s with `apt-get download` and `dpkg-deb -x`s them). |

### AGPL note

The AGPL's network-service clause is not triggered by anything we do here: Carcasum is built and
run **locally, as a subprocess of a measurement harness**, and is not offered to users over a
network. It is vendored for internal research use. Its source — including our modifications —
lives in this tree alongside the licence, which is what the licence asks for. Nothing derived
from Carcasum is linked into `src/carcassonne_ai`, the champion, or any shipped artefact; the
only coupling is a line-delimited JSON pipe between two separate processes.

### Two facts a reader needs before touching this tree

1. **Their tile pack is the 2014 (pre-garden) JCloisterZone `basic.xml`: 24 kinds, 72 tiles.**
   Ours is `basic:2`: 32 kinds, 72 tiles. The difference is the eight C3 "garden"/flowers
   graphic variants, which their pack folds back into their non-garden counterparts. The
   OUR-kind → THEIR-id map is therefore total and **many-to-one**, and the deck-count multiset
   agrees exactly. Mapping + provenance: [`tests/data/carcasum/`](../tests/data/carcasum/).
2. **R9 recurs verbatim.** Their `RCr` (our `city_top_straight_road`, and their start tile)
   declares `<farm city="N">EL WR</farm>` — the same half-edge convention that produced our R9
   remediation. Our engine matches it under `CARCASSONNE_FIX_R9=1`, which is why every Carcasum
   match runs `fixed_v1` + R9 and is **not** comparable to `walled` production elo.
