# REVIEW_R2 — closing review of rev R1 (commit f7722ed3). VERDICT: FAIL

Round-1 disposition: 13/21 verified genuinely closed against the emitters (4, 6, 7, 8,
9, 10, 11, 12, 13, 14, 16, 19, 21 — branch tables re-derived total+disjoint; se
bracket consistent across both docs; cost reproduces to 0.1 wh; I7 verbatim-adopted
and is the strongest part of the document; --out behavior-preserving, one benign new
out_path key in the emitted JSON worth a commit-note line). Remaining/new defects:

## BLOCKING (fix before the pair can merge)

N1. G-BITEXACT@HEAD's new `git_rev == the run's` conjunct voids a healthy run twice:
   (i) format — verify_tier1_rust writes 40-char `rev-parse HEAD`; the run manifest's
   git_rev is 7-char `--short` (run_tiletie.check_git_clean:303-304); (ii) sequencing —
   the gate is produced at step 3-4 HEAD=X, the blind commit is step 5, so the run
   records HEAD=X+1 by construction. FIX: conjunct = "git_rev resolves to the §9
   step-2 W-code merge commit or a descendant whose diff touches nothing under
   scripts/tiletie/, src/, engine/, rust/"; compare via startswith on the short form.

N2. §9 step 4 (acceptance test) is sequenced BEFORE the corpus exists — every
   corpus-derived address (CHAMP_GAMES_VERIFY, GATE_DISJOINT incl strata_root_overlap,
   POSITIONS_PLAN/ARMS both strata, GATE_DRAW, RUN_MANIFEST_{S1,S2}, all
   READOUT::widening.*, per_position jsonl) is unresolvable at that point; also
   "run the smoke" (singular, S1 knobs) leaves all S2-side gates uncovered. FIX:
   split 4a (pre-commit, corpus-free: static schema audit of W3/W5/W6 outputs against
   fixtures + the smokes' own manifests) / 4b (post-corpus, pre-scoring: full address
   resolution against real corpus artifacts, which carry no outcome statistic). TWO
   smokes (S1 --m 128, S2 --m 32), each per-judge. Blind commit stays step 5, before
   band claim; 4b sits between corpus build and first scoring leg.

N3. Step 4 "blind, outcome-free" has no mechanism: resolving READ_RULE §4/§5
   addresses as worded means W3 computes arb/Δ/Δ_ora/CIs on real corpus positions
   pre-commit, and forces SEALED_G_REPLICATE.json into existence pre-commit. FIX:
   define the acceptance test as key-presence + type ONLY — prints resolved/UNRESOLVED
   per address, never a value; state that mechanism in §9 explicitly.

N4. SEALED_G_REPLICATE.json is registered as G-REPLICATE's FALLBACK address while
   §1.3 obliges the reader to open fallbacks and print resolved_at, and §7 forbids
   opening it — direct contradiction, colliding exactly when the seal matters (W3's
   boolean block missing). FIX: the sealed file is NOT an address; G-REPLICATE gets
   no fallback (missing boolean block = FAIL); sealed-file description moves to §7 as
   write-only. N4b: no work item OWNS writing the sealed file or the print-suppression
   contract — add both to the W3 row.

## REQUIRED (same class, fix in the same round)

N5. EXCLUDE_RIDS_all.txt vanished from every binding surface (DESIGN still names it;
   READ_RULE enumerates only four comparisons; the §4 knob table lost --exclude-rids).
   FIX: five comparisons (S1∪S2 vs the rid-txt, rid-layer only) + --exclude-rids in
   the knob table.

N6. §2 preamble lost "S1 gates bind BOTH rungs", and G-SALT/G-CRN address only S1 —
   S2's world_seed_salt, deployed_cap_j, per-rid cap_seed, and CRN integrity are
   ungated (S2 is a separately built corpus + separately launched run; nothing
   transfers). FIX: restore the sentence AND extend G-SALT/G-CRN to {S1,S2}.

N7. Per-leg fallbacks (resolved_config.*) and G-PREFIX's PRIMARY exist only on
   tier1-greedy legs; clair-puct legs (oracle_score_pilot manifests) have neither
   resolved_config nor preflight.seeds, and <judge> is unbound in the address. FIX:
   bind <judge> = tier1-greedy on all four; state prefix-stability is witnessed once
   on the ARB leg (property of the shared world_seed derivation).

N8. G-CRN per-record fallback path shape wrong: the emitter writes
   records/<rid>.json (one object per rid), not *.jsonl. FIX the path in both docs.

N9. GATE_DRAW.json has no owning work item (fallback reader-recompute is sufficient,
   but the primary is unowned code). FIX: assign to W5 or W6.

## COSMETIC (may ride): N10 c_worker_secs_per_playout None-handling; N11 name
--smoke-n ≥20; N12 G-BAND top-up disjunct needs two verify invocations or per-range
n_out_of_band; N13 one sentence acknowledging row 3's floor is deliberately a point
test; N14 significantly-negative arb_64 lands in W-INCONCLUSIVE (labelling nit).

## The class fix for the acceptance test (Part-3 answer, adopt verbatim)
Step 4b must "resolve EVERY address, PRIMARY AND FALLBACK INDEPENDENTLY, named
anywhere in READ_RULE §2/§4/§5 OR in DESIGN §7's c-remeasure obligation (incl.
GEN_SMOKE.json and the realized-vs-committed c block), on BOTH strata's smokes,
reporting resolved/UNRESOLVED per address and no values." Without primary-and-
fallback-independently, every fallback in the document stays unaudited until the
moment it is needed.
