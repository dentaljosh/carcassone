⛔⛔ SYNTHETIC SELFTEST FIXTURE — NOT THE CELL, NOT A MEASUREMENT.
CELL_H2H2_FPU02__c0..c3/ are hand-made by make_fixture.py. Deck seeds
are on the THROWAWAY sub-range 169999999xxx; no claimed band is
touched. It exists so analyze_h2h.py --selftest can prove the gates
fire and the cell branches against a real directory tree.

⭐⭐ IT IS A **TWO-BOX** FIXTURE, ON PURPOSE. Chunks c0/c1 carry host
laptop-wsl and c2/c3 carry 5800x-box, with DIFFERENT (box-local)
carc_rs_binary_sha values and the SAME code_rev. That is the exact
shape DESIGN §6.4's flexible-box clause produces when the owner adds
the local box partway through a round, and it is what makes G-CHUNKS,
G-NODUP, G-SHARD-IDENT, the provenance-only G-HOST and the per-box
G-WHEEL-SAME TESTED rather than merely written down.

⭐ The MANIFEST SHAPE is copied from a REAL emitted archive
(/mnt/c/carc-shared/fpu_ladder/SMOKE_ARBON_H2H/manifest.json,
2026-08-31) — PG-A1: a fixture written from the DESIGN teaches the
gates wrong addresses. ⚠️ The OPPONENT-side arbiter shape comes from
tests/test_opp_tiearb_plumbing.py::test_real_run_manifest_shape,
because no banked archive predates the 2026-08-31 plumbing — a
DISCLOSED weakness, and the reason the launcher's --smoke reads the
shape back off a live manifest before the round.

⚠️ THE GOLDEN GATE IS NOT HERE AND IS NOT REBUILT BY THIS ROUND: it is
INHERITED from ../../fpu_ladder_prep/FPU_BITEXACT_LADDER.json with the
wheel re-asserted at launch, and its two named gaps are paid by the
launcher's --smoke IDENT legs (DESIGN §9).
