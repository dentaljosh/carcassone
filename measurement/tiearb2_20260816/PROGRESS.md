# PROGRESS LOG — tiearb2_20260816 (terminal-grounded tie arbitration, Stage 1b / successor)

Append-only. Timestamps are local (WSL2, box = 5900XT local unless stated).

## Owner authorization

2026-08-16, verbatim:

> "fund. both boxes. laptop w22, local w14 for now, but make it easy to bump to
> w30 later. get an agent on it"

⇒ Both boxes funded. Worker counts live in [WORKERS.conf](WORKERS.conf) — a
one-line edit bumps `W_LOCAL` 14 → 30. **The owner named W_LOCAL=30 as the value
he may bump to.**

---

## Log

- **[t0] Orientation.** Read the spent Stage-1 artifacts
  (`../tiearb_20260816/{READOUT,DESIGN,READ_RULE}.md`) and `docs/LEVER_INDEX.md`
  rows 212–217. Recorded re-open bar: successor needs (a) a NEW corpus at
  n ≈ 924+, (b) a fresh read-rule, (c) an argument handling the dev/holdout
  discrepancy, (d) an answer to the cost question.
- **[t0] Census.** Local: 0 python processes, loadavg 0.10, 32T, 41 GB.
  Laptop (`ssh laptop`): 0 python processes, loadavg 0.01, 24T, 11 GB.
  **Both boxes idle.** No co-tenant.
- **[t0] Run dir created**, `WORKERS.conf` written (the one-line worker bump).
