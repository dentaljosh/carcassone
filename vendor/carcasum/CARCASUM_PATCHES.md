# `vendor/carcasum` — the patch list

Upstream: `TripleWhy/Carcasum` @ **`5f5e3654d31ce8cef0eebeb80a7fb989ef7c2550`** (2014-07-24), AGPL-3.0.

Every deviation from that commit is listed here. The list is kept **minimal and
re-appliable**: recover it at any time with

```sh
diff -ru --exclude=.git --exclude='build-*' <pristine-clone> vendor/carcasum
```

Patches are in two classes, and the distinction is load-bearing:

* **BUILD** — makes 2014 gcc-4.8-era code compile on a modern toolchain. **Zero
  behavioural change.** A build patch that could change a result is not a build patch.
* **RULES** — brings their rules into agreement with our `fixed_v1` profile, so that a
  match result is a strength result and not a rules result.

**Nothing in `Carcasum/player/**` is patched for behaviour.** That directory is the
search — it is the thing being measured, and touching it would make the measurement
meaningless. The one edit that lands there is a compile guard around an assertion
(B4), which is a no-op in release builds by construction.

---

## RULES patches

### R1 — tiny-city exception removed (original-2000 → modern)

**File:** `Carcasum/core/game.cpp`, `Game::cityClosed` and `Game::cityUnclosed`.

Upstream deliberately implements the **original-2000** rule (thesis §2.3, "Rules
Used"): a completed city of exactly two tiles scores **2 points, not 4**.

```c
-	int score = n->getScore();
-	if (score > 2)
-		score *= 2;
+	int score = n->getScore();
+	score *= 2;
```

**Why it is exactly this.** `CityNode::getScore()` returns
`uniqueTileCount() + pennants`. So upstream's `score > 2` guard fires only on a
**plain two-tile city** — a two-tile city *with* a pennant already scored 3 → 6, which
is the modern answer. The single behavioural delta is therefore
`plain 2-tile completed city: 2 → 4`, which is precisely the divergence the inventory
flagged ([`docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md`](../../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md) §3.1 item 4).

**Both functions must change together.** `cityUnclosed`/`unscoreNode` is the *undo*
path the MCTS simulation uses to roll a node back; a scored/unscored pair that
disagreed by 2 points would silently corrupt the search's own board, not merely
mis-score the game of record. They are patched as a pair and must stay that way.

Endgame scoring needs no patch: an *incomplete* city scores `getScore()` unchanged
(1/tile + 1/pennant), which is already the modern rule.

**Audit obligation.** This patch is not taken on faith from a diff — check 6 of
[`measurement/carcasum_match_prep/AUDIT_PLAN.md`](../../measurement/carcasum_match_prep/AUDIT_PLAN.md)
requires a plain two-tile city to *positively complete and score 4* in the audit
corpus, constructing the case if the corpus does not contain one.

### R-none — `calcUpperScoreBound` deliberately NOT patched

**File:** `Carcasum/core/game.cpp:~1087`, `Game::calcUpperScoreBound`.

This function carries the same stale rule (`((tinyCities / 2) * 3) + (cities * 2) + …`)
and is **left alone on purpose.** It feeds `Game::getUpperScoreBound()`, which is read
**only** by the *normalising* utility providers in `player/utilities.h` (the Heyden-style
ones). Our pre-registered opponent is
`MCTSPlayer<Utilities::PortionUtility, Playouts::RandomPlayout>`, and
`PortionUtility::utility()` is `scores[me] / sum(scores)` — it never touches
`upperScoreBound`. The site is therefore **inert for the configuration being measured**,
and patching it would be a gratuitous edit to AI-adjacent code that changes a reward
normaliser for no measurable gain.

⚠️ **If a rung-2 ever switches the opponent to a normalised / Heyden utility, this
becomes live and must be patched first.** Flagged here rather than in a comment
because the person who makes that switch will be reading this file, not `game.cpp`.

### R-none — `jczplayer.cpp:417` deliberately NOT patched

`if (city->uniqueTileCount() > 2)` inside their *port of the JCloisterZone AI*'s
evaluation. That is AI code, it belongs to a player we do not use as the opponent of
record, and a stale rule in an evaluator is an AI-quality matter rather than a rules
divergence. Left alone. Noted so a future reader's grep for `> 2` does not think it
was missed.

---

## BUILD patches

All four are mechanical. None changes a value, an ordering, or a control-flow path.

| # | file | change | why |
|---|---|---|---|
| **B1** | `Carcasum/Carcasum.pro` | `REVISION = $$system(git rev-parse HEAD)` → `REVISION = 5f5e3654…` | vendored trees carry no `.git`, so the `$$system` call would bake a garbage/empty revision into `APP_REVISION`. Pinning the literal keeps the binary self-identifying — the driver echoes it in its `ready` line and it lands in every match manifest. |
| **B2** | `Carcasum/core/game.cpp` | `+#include <QDataStream>` | `storeToFile`/`loadFromFile` use `QDataStream`; Qt 5.15 no longer pulls it in transitively via `<QFile>`. |
| **B3** | `Carcasum/core/util.h` | `+#include <cmath>` | `std::sqrt`/`std::log` used without the header; libstdc++ no longer leaks it in transitively. |
| **B4** | `Carcasum/player/mctsplayer.tpp` | wrapped one `Q_ASSERT` in `#if ASSERT_ENABLED` | the assertion references `childNSum`, which is itself declared under `#if ASSERT_ENABLED`. Qt 5.15's release-mode `Q_ASSERT(cond)` expands to `static_cast<void>(false && (cond))`, which **still parses** `cond` → undeclared identifier. Guarding the assert matches the guard already on its operand. No-op in release either way. |

### Toolchain, not a patch

Qt 5 is not installed system-wide on the local box and `sudo` requires a password, so
the build uses a **rootless** prefix at `/home/doctor/opt/carcasum-toolchain`,
reproduced from scratch by
[`scripts/carcasum_match/bootstrap_toolchain.sh`](../../scripts/carcasum_match/bootstrap_toolchain.sh)
(`apt-get download` + `dpkg-deb -x` + a generated `qt.conf`). Nothing in the source
tree depends on that path; it is a build-environment fact, recorded here so the next
box does not have to rediscover it.

The `tournament` and `driver` targets link QtGui because upstream's `.pro` never does
`QT -= gui` (there is an upstream comment saying `QTransform` needs it). They are
still pure console programs and need **no X display** — verified, not assumed.
