# Wheel roll-in 2026-09-01 — flattening + follow-ons A + L2 solver swap

Owner ruling 2026-09-01 ("fleet wheel rebuild approved"). Wheel built from HEAD
`9fa813bb`: `carc_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl`, sha256 `c1250fe2…`,
rustc 1.96.0 (pinned).

## Status
- **Local venv: INSTALLED + identity-verified** — champion leaf fingerprint triple
  exact; G2 leaf reconcile 42,136/0; G7 exact-solver reconcile PASS (the L2 swap's
  bit-identity claim); G3 search reconcile 180 searches / 1,440 checks / 0 mismatches;
  `tests/release/` 53/53; cargo 250 passed.
- **Phone APK: INSTALLED 2026-09-01 09:55:45** (`adb install -r` at port 43375,
  firstInstallTime preserved). APK sha256 `c373726b…`, wheel content-version
  `carc-rs-1.43281.30596`. ⚠️ versionCode stays 3 — discriminate builds by sha only.
  New BUILD epoch (bit-identical play expected); landed mid-E-5 batch.
- **Laptop venv: DEFERRED** — the live carcasum remote server (the E-5 opponent,
  PID 405720, up 2d9h+) runs from the shared venv; no install over a live tenant.
  Owner may authorize a between-games bounce, else wait for the batch to close.

## s/move at 22016 (PRODUCTION.yaml `measured_s_per_move` re-measure, owed since 2026-08-30)
- `informal_probe_searchonly/` — the roll-in agent's quick probe: **2179.5 ms/move**
  (candidate prefix, 70 moves, ONE game, W=1 quiet). ⛔ NOT governance-grade, kept as a
  directional record only: arbiter NOT armed (manifest `cand_tiearb.enabled=false`) and
  `CARCASSONNE_FIX_R9` NOT exported (`r9_env_ok=false`) despite `--rules-profile
  fixed_v1`. Direction: ~2.5× vs the pre-L2 ~5.38 deploy figure — consistent with the
  merged 1.174× flattening + solver-swap wins.
- `bench22016_deployed.sh` — the PROPER probe: ✅ RAN 2026-09-01, exclusive tenant,
  all gates green (r9_env_ok=True, arb both seats B=64). **2433 ms/move mean**
  (2371/2455/2473 over 3 games, 208 moves) → PRODUCTION.yaml `measured_s_per_move`
  stamped 2.433 from `bench22016_arbon/manifest.json`. Deploy arc: ~5.38 (pre-L2 est)
  → 2.433 measured ≈ 2.2×; arb increment over search-only ≈ +0.25 s.
