export const meta = {
  name: 'live-code-audit-r5',
  description: 'Fresh multi-agent audit of ALL live-code surfaces (shell orchestration + eval harness + provenance/core + training/leaf + this-session new tooling), each finding adversarially verified and deduped against the known REVIEW_LOG D-items so only genuinely-missed issues surface',
  phases: [
    { title: 'Find', detail: 'one finder per live-code surface; mark each finding NEW vs already-known' },
    { title: 'Verify', detail: 'adversarial refuter per NEW finding (default to refuted if uncertain)' },
    { title: 'Synthesize', detail: 'cross-surface dedup + severity ranking of confirmed-new issues' },
  ],
}

// ---- what is ALREADY known (so the audit reports only what we MISSED) ----
const KNOWN = [
  "D-S1 run_residual_flywheel.sh wait-loops: no per-loop deadline / max-heal cap -> can hang forever (DEADLINE dead because auto-chain leaves DURATION_HOURS unset).",
  "D-S2 run_residual_flywheel.sh heal relaunches the pool WITHOUT pkill'ing the prior one -> orphan mp spawn-workers accumulate.",
  "D-S3 run_residual_flywheel.sh _clean_stranded age=4min < a heur@800 game -> heal can delete a slow-but-ALIVE worker's claim -> duplicate seed.",
  "D-S4 run_residual_flywheel.sh ssh launches: rc=255 (Tailscale jitter) silently drops a box for the iter, no retry.",
  "D-S5 eval_iter_head_to_head.py _result_path: cache key omits c_puct/residual_scale/value_blend/leaf -> config change into same output-root reuses wrong cached games.",
  "D-S6 run_residual_flywheel.sh cp best.pt warm.pt: no existence guard + set -e off -> silently warms from nothing.",
  "D-S7 plateau `break` ran BEFORE the per-iter odometer block -> terminal-iter odometer skipped. ALREADY FIXED in run_residual_flywheel.next.sh (break after odometer + fires on any terminal iter) and recovered via odo_oneshot.sh.",
  "D-R4-1 warmstart.py split_files_train_val: with mix>0, with-replacement sampled files straddle the index-based train/val split -> same game in train AND val. NOT live (flywheel mix=0.0).",
  "D-R4-2 auto_chain_h2h_flywheel.sh count()/tally(): glob whole eval dir, no seed-range filter -> a pre-existing larger run in the same dir could end wait_h2h early.",
  "D-R3-2 train_iter.py value<->outcome corr diagnostic is residual-vs-residual in residual mode but printed against the 0.61 value-vs-OUTCOME ruler -> cosmetic mislabel.",
  "D2 features/encoding: TILES phase encodes state.next_tile (unrotated) vs MEEPLES phase last_tile_action.tile (rotated) -> same channel range, two meanings. Needs re-encode+retrain decision.",
  "D3 virtual_score_v2.py bonus_cap vs opp_bonus_cap asymmetry breaks v2 antisymmetry when the two caps differ.",
  "D16 virtual_score_v2.py _close_prob(0) returns 1.0 for a board-edge unfinished city with zero in-bounds open positions -> 100% closure bonus to a city that cannot close.",
  "KNOWN-SEEDS: run_pathb_cluster_loop.sh, rank_sweep.sh, lever_sequencer.sh, scaling_curve.sh, ladder_highsim.sh still carry pre-1e9 eval seeds -> the clean-seed guard would hard-error/hang them. Fix before reuse.",
  "S-R3-1 (NOT a bug, a research lever): residual target delta in [-2,2] saturates the tanh value head [-1,1] -> high-signal residuals under-learned. Attempt-#2 lever.",
  "R1-REDUX (already fixed): evals defaulting to --heur-leaf v1 while the net runs v2.7. All 6 flywheel gate/odometer eval calls now pass --heur-leaf v2_7; gate_elo nan-proofed; GATE_SEED=1e9.",
];

// ---- live-code surfaces to fan out over ----
const SURFACES = [
  {
    key: "shell-flywheel",
    label: "shell: flywheel runner + restart batch",
    files: "scripts/run_residual_flywheel.sh (LIVE) and scripts/run_residual_flywheel.next.sh (restart-staged copy = live + D-S1/2/3/6/7). NOTE: next.sh intentionally carries fixes not in live; that is the restart-batch design, NOT a finding.",
    focus: "iter-loop control flow, keep-best/plateau logic, the D-S7-fixed ordering, gate_elo nan-handling, _clean_stranded race, seed namespaces (GATE_SEED/ODO_SEED >= 1e9), warm.pt staging, exit codes, set -uo pipefail interactions, awk float/nan correctness.",
  },
  {
    key: "shell-orch",
    label: "shell: auto-chain + gen + NEW recovery tooling",
    files: "scripts/auto_chain_h2h_flywheel.sh, the share copy /mnt/c/carc-shared/code_sync/gen_flywheel.sh (HOST!=5800x reset guard), and scripts/odo_oneshot.sh (NEW this session, NOT yet reviewed).",
    focus: "3-box launch quoting (cmd.exe/ssh), seed-range filters in count/tally, deck-paired tally math, the gen-sync git-reset guard, odo_oneshot stall-heal correctness (does the heal clean+relaunch safely? can it delete a live claim? does pkill match the right procs?), env/ENVV/leaf consistency vs the flywheel's run_odometer it replicates.",
  },
  {
    key: "eval-harness",
    label: "python: net-vs-heur + h2h eval scripts",
    files: "scripts/eval_net_vs_heuristic.py, scripts/eval_iter_head_to_head.py.",
    focus: "the R1-redux class (leaf actually matched on BOTH sides at runtime), --seed-start 1e9 guard + assert_clean_eval_seed_range, deck_hash, paired/balanced-seat logic, W/D/L + won_by_net/drew accounting, shared-claim O_EXCL race + partial.json temp-naming, residual-scale wiring, provenance manifest emission.",
  },
  {
    key: "eval-tally",
    label: "python: ladder + odometer tally math",
    files: "scripts/ladder_asymmetric.py, scripts/odo_paired_tally.py (NEW this session, NOT yet reviewed), and the gate_elo/tally heredocs inside run_residual_flywheel.sh + auto_chain_h2h_flywheel.sh.",
    focus: "elo = 400*log10(wr/(1-wr)) and paired-SE/z math correctness, deck-pairing on common seeds, nan/inf/degenerate handling (wr=0 or 1, nd<=1), continuity correction, the --heur-leaf default (v2_7?) on ladder_asymmetric, off-by-one or seat-imbalance in the pairing.",
  },
  {
    key: "provenance-core",
    label: "python: provenance guards + MCTS/evaluators",
    files: "src/carcassonne_ai/eval_provenance.py, src/carcassonne_ai/run_manifest.py, src/carcassonne_ai/evaluators.py, src/carcassonne_ai/mcts.py.",
    focus: "does assert_provenance_consistent ACTUALLY catch the R1 (claim v2.7 ran v1) and R7 (residual_scale>0 but residual path never fired) classes at runtime? the _V25Wrapped/HeuristicMCTS leaf-path counters, residual-scale and value-blend leaf math, sha256/dirty stamping, schema validity, any path where a counter can be wrong/zero while the manifest claims success.",
  },
  {
    key: "train-leaf",
    label: "python: training + selfplay + leaf eval",
    files: "src/carcassonne_ai/train_iter.py, src/carcassonne_ai/selfplay.py, src/carcassonne_ai/warmstart.py, src/carcassonne_ai/virtual_score_v2.py.",
    focus: "value_target='residual' target construction + the tanh clip (does training silently clip/saturate beyond S-R3-1?), train/val split (D-R4-1 is known for mix>0 — look for OTHER leakage at mix=0), augmentation/rotation correctness for value-only rows, GameDataset masking, virtual_score antisymmetry/edge cases beyond D3/D16, residual_scale env plumbing into the leaf.",
  },
];

const FINDING_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    findings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          id: { type: "string", description: "short slug e.g. shell-flywheel-1" },
          file: { type: "string" },
          location: { type: "string", description: "line number(s) or function" },
          severity: { type: "string", enum: ["critical", "high", "medium", "low", "cosmetic"] },
          title: { type: "string" },
          description: { type: "string", description: "what is wrong and the exact trigger condition" },
          impact: { type: "string", description: "what breaks, and whether it could affect a RESULT vs just robustness" },
          is_known: { type: "boolean", description: "true iff it matches one of the KNOWN items given" },
          known_ref: { type: "string", description: "which KNOWN item, or '' if new" },
          fix: { type: "string" },
        },
        required: ["id", "file", "location", "severity", "title", "description", "impact", "is_known", "known_ref", "fix"],
      },
    },
  },
  required: ["findings"],
};

const VERDICT_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    is_real: { type: "boolean", description: "true only if the bug genuinely exists and triggers as described" },
    confidence: { type: "number", description: "0..1" },
    severity_adjusted: { type: "string", enum: ["critical", "high", "medium", "low", "cosmetic", "not-a-bug"] },
    reasoning: { type: "string", description: "the refutation attempt and why it survived or failed" },
  },
  required: ["is_real", "confidence", "severity_adjusted", "reasoning"],
};

function findPrompt(s) {
  return [
    "You are auditing ONE surface of a live AlphaZero-Carcassonne codebase for MISSED bugs. Repo root is the cwd.",
    "",
    "SURFACE: " + s.label,
    "FILES: " + s.files,
    "FOCUS: " + s.focus,
    "",
    "Read the actual files (they reflect HEAD 61e4fcc). Hunt for correctness bugs, races, silent-wrong-result paths, exit-code/error-swallowing, math errors, seed/leaf mismatches, and resource leaks. Prioritise anything that could make an EVAL or TRAINING RESULT silently wrong (that is the bug class this whole effort exists to kill).",
    "",
    "These items are ALREADY KNOWN AND LOGGED. If you find one of them, set is_known=true and cite it in known_ref; do NOT pad the report with known items. We want what we MISSED:",
    KNOWN.map(function (k, i) { return "  - " + k; }).join("\n"),
    "",
    "Be precise: every finding needs an exact file + line/function and a concrete trigger condition. If a surface is clean, return an empty findings array — do NOT invent issues. Quality over quantity.",
  ].join("\n");
}

function verifyPrompt(f) {
  return [
    "Adversarially REFUTE this claimed bug. Default to is_real=false unless you can confirm the exact trigger by reading the code.",
    "",
    "CLAIM: [" + f.severity + "] " + f.title,
    "FILE: " + f.file + " @ " + f.location,
    "DESCRIPTION: " + f.description,
    "IMPACT: " + f.impact,
    "PROPOSED FIX: " + f.fix,
    "",
    "Read the cited code and its call sites. Try to prove the bug is NOT real: a guard upstream, an unreachable path, a misread of the logic, or it is actually already-correct. Only set is_real=true if the bug genuinely triggers as described. Adjust severity if the real impact differs (use 'not-a-bug' if refuted).",
  ].join("\n");
}

phase("Find");
log("R5 live-code audit: " + SURFACES.length + " surfaces, find -> adversarial-verify -> synthesize");

const perSurface = await pipeline(
  SURFACES,
  function (s) {
    return agent(findPrompt(s), { label: "find:" + s.key, phase: "Find", schema: FINDING_SCHEMA, agentType: "Explore" });
  },
  async function (found, s) {
    if (!found || !Array.isArray(found.findings)) return { surface: s.key, confirmed: [], knownHits: [], total: 0 };
    const fresh = found.findings.filter(function (f) { return !f.is_known; });
    const knownHits = found.findings.filter(function (f) { return f.is_known; });
    const verified = await parallel(fresh.map(function (f) {
      return function () {
        return agent(verifyPrompt(f), { label: "verify:" + f.id, phase: "Verify", schema: VERDICT_SCHEMA })
          .then(function (v) { return Object.assign({}, f, { verdict: v }); });
      };
    }));
    const confirmed = verified.filter(Boolean).filter(function (x) { return x.verdict && x.verdict.is_real; });
    return { surface: s.key, confirmed: confirmed, knownHits: knownHits, total: found.findings.length };
  }
);

phase("Synthesize");
const allConfirmed = perSurface.flatMap(function (r) { return r.confirmed || []; });
const knownCount = perSurface.reduce(function (a, r) { return a + (r.knownHits ? r.knownHits.length : 0); }, 0);
log("confirmed-new=" + allConfirmed.length + " across surfaces; known-rediscovered=" + knownCount);

let synthesis = "No confirmed-new issues; all surfaces clean or only re-surfaced known items.";
if (allConfirmed.length > 0) {
  synthesis = await agent([
    "You are the synthesis lead for a code-audit round. Below are ADVERSARIALLY-CONFIRMED new bugs (each already survived a refuter) across code surfaces of a live AlphaZero-Carcassonne repo.",
    "Cross-surface DEDUP (same root cause reported on two surfaces = one item), then rank by severity and by whether each could make an EVAL/TRAINING RESULT silently wrong vs mere robustness.",
    "Output a tight markdown report: a ranked table (id | file:line | severity | result-affecting? | one-line), then for each a 2-3 line what/why/fix. End with a one-line bottom-line: did we miss anything that matters, yes/no.",
    "",
    "CONFIRMED-NEW FINDINGS (JSON):",
    JSON.stringify(allConfirmed, null, 2),
  ].join("\n"), { label: "synthesize", phase: "Synthesize" });
}

return {
  surfaces_audited: SURFACES.length,
  confirmed_new: allConfirmed.length,
  known_rediscovered: knownCount,
  per_surface: perSurface.map(function (r) { return { surface: r.surface, total: r.total, confirmed_new: (r.confirmed || []).length, known: (r.knownHits || []).length }; }),
  confirmed_findings: allConfirmed,
  report: synthesis,
};
