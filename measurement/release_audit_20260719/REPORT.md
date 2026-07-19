# F1 release-integrity audit — PASS

Generated 2026-07-19T23:55:19.398683+00:00 by `scripts/release_audit.sh`.
Gate: **zero semantic/configuration divergences** before any headline claim. Re-run after any leaf/search/config change touching the champion.

## Property suite (`tests/release/`)

| Property | Module | Tests | Result |
|---|---|---:|---|
| dual-farm / same-city terminal scoring (P1-L5) | `test_farm_scoring` | 7 | PASS |
| crop boundary strict mode (P1-R1) | `test_crop_boundary` | 4 | PASS |
| legal-cache / state-key collisions (P1-R7/S6) | `test_key_collision` | 3 | PASS |
| rotation-alias canonicalization (P1-A3) | `test_rotation_alias` | 3 | PASS |
| deck canonicalization / no hidden-order leak (CL-056) | `test_deck_canonicalization` | 3 | PASS |
| current-tile / bag invariants | `test_bag_invariants` | 5 | PASS |
| result-sign semantics (won_by_champ/diff) | `test_sign_semantics` | 3 | PASS |
| factory manifest golden + hash dialects | `test_factory_manifest` | 10 | PASS |

**Suite total: 38/38 passed** (pytest rc=0). Full log: `pytest.log` / `pytest.xml`.

## Adversarial state replay (`scripts/release/replay_audit.py`)

- **Result: PASS** (rc=0)
- Corpus source: `/home/doctor/projects/carcassone/.claude/worktrees/agent-affbf918036532428/measurement/window_audit/gen_games.jsonl`
- States replayed: **2159** (15 production + 5 synthetic games); by source {'prod': 2159, 'synth': 0}
- Strict-window drops — **production (GATED): 0** | synthetic (adversarial probe): 5
- **Dangerous key collisions (GATED, count-differing): 0**
- Rotation-alias label fragmentation (P1-A3, benign/measured): 0 (built-in detector logs: 0)
- Champion manifest drift mid-run: **False**
- Champion leaf hash (harness dialect): `a36d2e15a3b3d71d`
- Wall: 4.0s. Scope note: F1 smoke pathway (~2k states); the full >=100k replay is a later free-box execution with a bigger --games/--synthetic/--workers and the real window-audit corpus. Gate = production drops + DANGEROUS (count-differing) collisions + manifest drift; synthetic drops and P1-A3 label fragmentation are measured, not gating.

### Replay failures
```
[
 {
  "game": "synthetic_max_0",
  "source": "synth",
  "kind": "window_overflow",
  "detail": "STRICT window: 1/68 legal actions fall outside the 25x25 window centered at (-1, 15). CARCASSONNE_WINDOW_STRICT=1 fails loud on any dropped legal action."
 },
 {
  "game": "synthetic_max_1",
  "source": "synth",
  "kind": "window_overflow",
  "detail": "STRICT window: 1/66 legal actions fall outside the 25x25 window centered at (2, 14). CARCASSONNE_WINDOW_STRICT=1 fails loud on any dropped legal action."
 },
 {
  "game": "synthetic_max_2",
  "source": "synth",
  "kind": "window_overflow",
  "detail": "STRICT window: 4/60 legal actions fall outside the 25x25 window centered at (2, 14). CARCASSONNE_WINDOW_STRICT=1 fails loud on any dropped legal action."
 },
 {
  "game": "synthetic_max_3",
  "source": "synth",
  "kind": "window_overflow",
  "detail": "STRICT window: 4/60 legal actions fall outside the 25x25 window centered at (-2, 15). CARCASSONNE_WINDOW_STRICT=1 fails loud on any dropped legal action."
 },
 {
  "game": "synthetic_max_4",
  "source": "synth",
  "kind": "window_overflow",
  "detail": "STRICT window: 2/73 legal actions fall outside the 25x25 window centered at (0, 14). CARCASSONNE_WINDOW_STRICT=1 fails loud on any dropped legal action."
 }
]
```

## Champion of record (governance/PRODUCTION.yaml)

Verified at construction by `champion_factory.make_production_champion` — leaf proven on real boards (curve125 values + a leaf-output panel + three hash dialects). `champion_factory.LEAF_HASH_*` are the runtime-verified fingerprints:

| Dialect | Hash |
|---|---|
| `_leaf_hash` (harness, meeple_k=2.0) | `a36d2e15a3b3d71d` |
| `_frozen_config_hash` (champ_env, meeple_k=0.0) | `6dfffd57051690f2` |
| `_frozen_config_hash` (meeple_k=2.0) | `158f17ff76adaa02` |

## Artifacts

- `pytest.log`, `pytest.xml` — property-suite output
- `replay.json`, `replay.log` — adversarial replay
- `collisions/` — built-in state-key collision detector output (empty on PASS)

> STATUS wiring: paste the runner's `STATUS one-liner` into STATUS.md at merge-time close-out (this runner does not edit the live doc).
