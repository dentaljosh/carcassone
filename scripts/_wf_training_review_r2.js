export const meta = {
  name: 'flywheel-training-review-r2',
  description: 'Round 2: review the live flywheel TRAINING pipeline + reconcile the odometer anomaly + regression-check the overnight fixes',
  phases: [
    { title: 'Review', detail: '5 dimensions: selfplay-gen, residual-train, leaf+odometer-anomaly, fix-regression, keep-best/lineage' },
    { title: 'Verify', detail: 'adversarially confirm each medium+ finding' },
  ],
}

const REPO = '/home/doctor/projects/carcassone'

const CONTEXT = [
  'READ-ONLY review. Do NOT execute scripts or evals (a 24h flywheel is LIVE on the 3-box cluster; running anything contends with it). Do NOT modify files or touch processes. Repo: ' + REPO + '.',
  'SITUATION: a Track-B "residual flywheel" is TRAINING now (flywheel_residual_v2, 12 iters). Per iter: 3-box residual-guided self-play (leaf = v2.7 + SCALE*Delta, value head active, value_target="residual") then train the residual value head on that co-adapted data then gate vs matched HeuristicMCTS@200-v2.7 (keep-best, +15 margin, plateau-stop on 2 flat) and every 3 iters an OUT-OF-LINEAGE odometer (best vs heur@800-v2.7, clean seed). GOAL: flip CL-011 (does learned strength COMPOUND across iters out-of-lineage?). iter0 baseline +76.8 in-ecosystem; iter1 climbed to +106.6.',
  'A PRIOR review (round 1) already covered the orchestrator/flywheel SHELL + eval provenance and fixed 16 bugs (commit 702781e): the big one was an R1-redux (gate/odometer defaulted to heur-leaf v1 while the net runs v2.7, fixed to v2_7), plus gate_elo nan-corruption, ITERS-override, orchestrator JSON/nan hygiene. DO NOT re-litigate round-1 findings. Round 2 focuses on the TRAINING pipeline, an open ANOMALY, and whether the round-1 FIXES regressed.',
  'KEY OPEN ANOMALY to help reconcile: the clean iter0 odometer = best(scale0.25)@200 vs heur@800-v2.7 = +52.5 (n=200, seed 1.5e9), but the 2026-06-07 odometer for the SAME matchup/net/harness was -29 (n=120, seed 950k). Same harness (ladder_asymmetric subprocesses eval_net_vs_heuristic). Diffs: seed (950k contaminated-zone vs clean 1.5e9) and code_rev (old 484dcfa predates the R7 residual-path fix). If +52.5 is real it reframes CL-010 (the v2.7 leaf ceiling). We need to know if +52.5 is TRUSTWORTHY or an artifact/bug.',
  'Find REAL defects that would corrupt the training, silently break learning, mislead the CL-011 verdict, or explain the anomaly. Give file:line, severity, concrete fix. Cluster: 5800x local (share /mnt/c/carc-shared) plus xeon-wsl and laptop (share /mnt/carc-shared); shared-claim coordinates boxes via .claim files.',
].join('\n')

const FINDINGS = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, file: { type: 'string' }, line: { type: 'string' },
      severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
      category: { type: 'string' }, description: { type: 'string' },
      why_it_matters: { type: 'string' }, suggested_fix: { type: 'string' },
    }, required: ['title', 'file', 'severity', 'category', 'description', 'suggested_fix'] } },
  }, required: ['findings'],
}
const VERDICT = {
  type: 'object',
  properties: {
    is_real: { type: 'boolean' }, confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    severity_final: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] }, reasoning: { type: 'string' },
  }, required: ['is_real', 'confidence', 'severity_final', 'reasoning'],
}

const DIMENSIONS = [
  { key: 'selfplay-gen', prompt: CONTEXT + '\n\n' +
    'TARGET: the residual-guided SELF-PLAY generator. Files: scripts/run_selfplay_iter.py and the shared launcher /mnt/c/carc-shared/code_sync/gen_flywheel.sh (which calls run_selfplay_iter.py with --iter 0 --residual-scale 0.25 --value-target residual --value-blend 0 --anchor-fraction 0 --seed-start 0 --shared-claim). Scrutinize: (1) is the residual leaf (v2.7 + scale*Delta, value head ACTIVE) actually used to GUIDE the self-play search, or does a code path silently fall back to pure v2.7 / pure policy (the R7 class)? (2) is value_target=residual RECORDED correctly per position (what exactly is the target: search-Q minus the v2.7 leaf, or a residual delta; sign/scale right)? (3) --seed-start 0 on ALL 3 boxes with --shared-claim: do the boxes produce DISJOINT games or can two boxes generate the SAME seed game (duplicate/inconsistent training data)? (4) does self-play warm from the right checkpoint (warm.pt = best.pt)? Report concrete defects that would corrupt or bias the training distribution.' },

  { key: 'residual-train', prompt: CONTEXT + '\n\n' +
    'TARGET: the residual value-head TRAINING. Files: scripts/train_iter.py (called with --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight 1.5 --warm-from best.pt --output iterN.pt) and the residual value_target loading (GameDataset / data window). Scrutinize: (1) does training actually optimize the value head toward the residual target, or is there a target/loss mismatch (e.g. trains on outcome while gen recorded residual)? (2) the --window 10 + warmstart-mix-fraction 0: which iters data does iterN train on (only iterN_data or a window), and does the window resolve to the RIGHT dirs (flywheel_residual_v2/iterN_data)? (3) warm-from best.pt: does it correctly resume trunk/heads or reinit something? (4) does VLW=1.5 actually reach the value loss term (vs ignored/mis-keyed)? (5) any path where train silently no-ops or trains an empty/0-game dataset yet still writes a checkpoint. Report defects that would make the training not actually improve the residual head.' },

  { key: 'leaf-and-odometer-anomaly', prompt: CONTEXT + '\n\n' +
    'TARGET: the residual LEAF mechanism + the +52.5-vs-(-29) ODOMETER ANOMALY. Files: src/carcassonne_ai/evaluators.py (make_v25_value_wrapper / _V25Wrapped / residual_scale), src/carcassonne_ai/mcts.py, the LeafConfig.residual_scale + CARCASSONNE_V25_RESIDUAL_SCALE env, scripts/eval_net_vs_heuristic.py (how it applies residual_scale and heur_sims), and the odometer wiring in scripts/run_residual_flywheel.sh (_odo_launch, gate_elo, run_odometer). JOB: determine whether the clean +52.5 is TRUSTWORTHY or inflated by a bug. Check: (1) is the residual leaf clip(v2.7 + scale*Delta, +/-1) computed correctly, and is Delta applied with the right sign/scale in EVAL (could eval over-credit the net)? (2) the R7 angle: in the OLD code (484dcfa) could residual_scale>0 have silently NOT fired (net effectively pure-v2.7, hence weaker -29) while current code fires it correctly (+52.5)? i.e. is the anomaly EXPLAINED by the R7 fix? (3) does gate_elo count won_by_net correctly (no inversion, draws as 0.5, the new continuity-correction unbiased)? (4) is heur@800 really 800 sims for the opponent (heur-sims plumbed through)? (5) any deck-overlap or seed bug making the clean odometer easier. Give a concrete most-likely explanation for the 81-elo gap.' },

  { key: 'fix-regression', prompt: CONTEXT + '\n\n' +
    'TARGET: regression-check the round-1 FIXES (commit 702781e) plus the post-incident gen-guard. Read the CURRENT state of: scripts/run_residual_flywheel.sh (gate_elo continuity-correction + -9999 sentinel; the keep-best improved awk with string-nan guard; heur-leaf v2_7 on all 6 eval calls; GATE_SEED=1e9; ODO_SEED), scripts/auto_chain_h2h_flywheel.sh (verdict_label/in_escalation_band nan guards; JSON sanitize; stall-heal pkill-before-relaunch; count partial exclusion), and /mnt/c/carc-shared/code_sync/gen_flywheel.sh (the new guard: if HOST != 5800x then git reset). Scrutinize for NEW bugs introduced by the fixes: (1) does the +/-0.5-game continuity correction BIAS the gate elo (systematically shrink it) enough to distort keep-best? (2) does the gen-guard make the LOCAL box run DIFFERENT code than the remotes (training-data code inconsistency) if local HEAD diverges from the bundle? (3) the stall-heal pkill patterns: self-match or killing the wrong process? (4) does the -9999 sentinel interact badly with the plateau/flat counter? (5) any quoting or set -uo pipefail breakage from the edits. Report regressions only.' },

  { key: 'keep-best-lineage', prompt: CONTEXT + '\n\n' +
    'TARGET: keep-best / checkpoint LINEAGE + data integrity across 12 iters. File: scripts/run_residual_flywheel.sh (main loop, best.pt/warm.pt/best_elo.txt handling, flat/plateau, per-iter cp best.pt to warm.pt, resume markers done/genN and the CKPT skip). Scrutinize: (1) does each iter warm from the CURRENT best (re-branch on reject), or can a rejected/regressed iter checkpoint leak forward as warm-start? (2) resume logic (done/genN, [ -f CKPT ] skip): on restart could it skip gen but train on a half-written/empty data dir, or reuse a stale CKPT? (3) best_elo.txt vs best.pt consistency (could elo and ckpt desync so keep-best compares the wrong baseline?). (4) the data window as iters accrue: does iterN train on intended data and not accidentally pool ALL iters co-adapted data in a way that breaks the experiment? (5) is iter0 best.pt actually the residual net (ITER0_CKPT) and not overwritten? Report lineage/integrity defects that would silently invalidate the CL-011 verdict.' },
]

phase('Review')
const reviewed = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, { label: 'r2:' + d.key, phase: 'Review', schema: FINDINGS }),
  (rev, d) => {
    const fs = ((rev && rev.findings) || []).filter(f => f.severity !== 'low')
    if (!fs.length) return []
    return parallel(fs.map(f => () =>
      agent(CONTEXT + '\n\nADVERSARIALLY VERIFY this round-2 finding from the ' + d.key + ' review. Default to is_real=false unless you confirm, by reading the actual code at ' + f.file + ':' + (f.line || '?') + ', that the defect is genuine and would really bite the LIVE training run (or genuinely explains the odometer anomaly). Re-derive it yourself. Set the FINAL severity.\n\nFINDING:\ntitle: ' + f.title + '\nseverity(reported): ' + f.severity + '\ncategory: ' + f.category + '\ndescription: ' + f.description + '\nwhy_it_matters: ' + (f.why_it_matters || '') + '\nsuggested_fix: ' + f.suggested_fix,
      { label: 'verify:' + f.file.split('/').pop() + ':' + (f.title || '').slice(0, 22), phase: 'Verify', schema: VERDICT })
      .then(v => ({ ...f, dimension: d.key, verdict: v }))
      .catch(() => null)
    ))
  }
)

const all = reviewed.flat().filter(Boolean)
const confirmed = all.filter(f => f.verdict && f.verdict.is_real)
const rank = { critical: 0, high: 1, medium: 2, low: 3 }
confirmed.sort((a, b) => (rank[a.verdict.severity_final] ?? 9) - (rank[b.verdict.severity_final] ?? 9))
log('r2 review: ' + all.length + ' reviewed, ' + confirmed.length + ' confirmed real')
return {
  confirmed_count: confirmed.length,
  reviewed_count: all.length,
  confirmed: confirmed.map(f => ({
    severity: f.verdict.severity_final, confidence: f.verdict.confidence, dimension: f.dimension,
    title: f.title, file: f.file, line: f.line, category: f.category,
    description: f.description, suggested_fix: f.suggested_fix, verify_reasoning: f.verdict.reasoning,
  })),
}
