# DEVIATIONS — defense-primary standing instrument

## D-1 — census `corpus_tag` hardened PRE-TRIGGER (2026-09-02, statistics-blind)

Owner ruling 2026-09-02 ("fix the labels"): the phone app now DERIVES the archive's
`opponent_kind` from the Carcasum server's `/health` label (`carcasum_remote_p103500`
in fixed-playout mode) instead of the hardcoded `carcasum_remote_5000ms`. The census
classifier (`census_new_plies.corpus_tag`) was hardened in the same change:
(a) it keys the E-5 epoch off `remote.opponent.playouts` (the field of record), with a
`_p<N>` parse of the label only as a fallback — so the 9 banked epoch-A/B archives that
carry the OLD literal classify exactly as before; (b) an undeclared third playout pin now
REFUSES (loud) rather than being folded into `carcasum_p103500`; (c) a non-Carcasum server
label can never classify as a Carcasum game (allow-list). Tests added for both spellings,
epoch A/B separation, stale-label precedence, third-pin refusal, and the accrual path.

**No price exists; no banked ply was reclassified** — the agent re-ran the accrual and
the measurement content of `ACCRUAL.json` was byte-identical (only a `checked_at`
timestamp churned, which was reverted). Trigger count unchanged at 15/36. The PREREG's
corpus stratifier semantics are unchanged; this is instrument hardening ahead of the
trigger, disclosed here per the standing-prereg discipline.
