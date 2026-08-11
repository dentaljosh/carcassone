export const meta = {
  name: 'deep-reaudit-r4',
  description: 'Second-pass deep RE-AUDIT of already-covered surfaces (orchestrator, flywheel loop, eval harnesses, training, provenance/stats) — hunt the subtle bugs a first pass missed',
  phases: [
    { title: 'Reaudit', detail: '5 already-covered surfaces, second-pass deep dive' },
    { title: 'Verify', detail: 'adversarially confirm each medium+ finding is NEW and real' },
  ],
}

const REPO = '/home/doctor/projects/carcassone'

const CONTEXT = [
  'READ-ONLY second-pass RE-AUDIT. Do NOT execute scripts/evals/training (a 24h flywheel is LIVE on the 3-box cluster). Do NOT modify files or processes. Repo: ' + REPO + '.',
  'This is a DELIBERATE re-audit of surfaces that have ALREADY been audited once. Rationale (from the maintainer): first passes miss things; a fresh pass with different attention catches the subtle, second-order, edge-case bugs the first pass skimmed past. So: ASSUME the obvious/shallow bugs in these files are already found and FIXED -- do not waste a finding re-reporting them. Your value is the HARD stuff: off-by-ones, edge cases (n=0/1, ties, draws, empty dirs, first/last iteration, boundary seeds), order-dependence, subtle sign/scale errors, race windows narrower than the obvious ones, interactions between two functions that are each individually fine, silent fallbacks, and assumptions that hold in the common case but break at a boundary.',
  'Already FIXED (do NOT re-report): heur-leaf v2_7 on the flywheel evals; gate_elo nan continuity-correction + -9999 sentinel; the keep-best improved-awk string-nan guard; orchestrator verdict_label/in_escalation_band nan guards + JSON sanitize + count() partial-exclusion + stall-heal pkill; eval partial temp now .<stem>.<host>.<pid>.partial.json; ladder_asymmetric --heur-leaf default v2_7; gen_flywheel HOST!=5800x reset-skip + remote rc-guard; the EVAL_SEED_FLOOR=1e9 guard. Already RESOLVED: the +52.5-vs-(-29) odometer anomaly (R1-redux v1 leaf). Already DEFERRED (do NOT re-report): run_residual_flywheel.sh per-loop deadline/heal-cap, heal-pkill-prior-pool, _clean_stranded 4-min age, ssh rc=255 box-drop; eval_iter_head_to_head cache key omits config.',
  'A SEPARATE round-3 audit is concurrently covering the deep CORE (MCTS search internals, the v2.7 leaf scoring, the model/checkpoint, the residual-target round-trip) -- you do NOT need to cover those; focus on your assigned SURFACE and find what its first audit missed.',
  'Report only NEW, real defects (not in the fixed/deferred lists above). file:line, severity, concrete fix. Severity by real impact on the live run or a strength claim.',
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
  { key: 'orchestrator-2nd', prompt: CONTEXT + '\n\n' +
    'RE-AUDIT SURFACE: the auto-chain orchestrator scripts/auto_chain_h2h_flywheel.sh and scripts/run_h2h_residual_vs_iter11.sh. The first pass fixed nan/JSON/stall/partial issues. Go DEEPER for what it missed: (1) the deck-paired tally() math -- per-deck mean over seats when a deck has only ONE seat present (partial), the pstdev with nd==1, the z=elo/sig when sig is tiny, the wr clamp boundaries; could the REPORTED elo/z differ subtly from the true deck-paired value? (2) the escalation control flow: what if count() overshoots the target (more files than N due to a relaunch), or the second tally (post-escalation) reads a still-growing dir? (3) `read elo sig z ... < <(tally)` -- field-count mismatch if tally prints fewer/more tokens; IFS/whitespace edge cases. (4) launch_h2h idempotency on the FIRST (non-stall) call vs a relaunch. (5) any TOCTOU between count() reaching target and tally() reading. Report subtle NEW defects.' },

  { key: 'flywheel-loop-2nd', prompt: CONTEXT + '\n\n' +
    'RE-AUDIT SURFACE: scripts/run_residual_flywheel.sh (the live 12-iter loop). First pass + deferred list covered heal/deadline/age/partial/seed/heur-leaf/nan. Go DEEPER for the MISSED subtle logic: (1) keep-best/plateau: the flat counter reset/increment across a MIX of improve/regress iters, the >= vs > in the margin compare, what happens on the FIRST iter (best=iter0) and the LAST iter; can a regressed iter ever become warm.pt? (2) the scale-curve gate runs scale 0 AND scale=SCALE -- is the RIGHT subdir read back for the keep-best elo (knob_tag collisions, e.g. scale 0 vs 0.0 vs 0.25 tag)? (3) run_gate returns `echo $s25 | awk {print $1}` -- if gate_elo printed the -9999 sentinel or a blank, does run_gate propagate it correctly into BEST_ELO/the compare? (4) resume: done/genN markers + [ -f CKPT ] skip + best_elo.txt vs best.pt -- a crash between writing CKPT and updating best could desync. (5) cp best.pt warm.pt ordering vs the gen reading warm.pt. Report subtle NEW defects in the loop logic.' },

  { key: 'eval-harness-2nd', prompt: CONTEXT + '\n\n' +
    'RE-AUDIT SURFACE: scripts/eval_net_vs_heuristic.py + scripts/eval_iter_head_to_head.py + the eval-server / orchestrator IPC they use (src/carcassonne_ai/eval_server*.py). First pass covered provenance + the temp-file name + the cache key (deferred). Go DEEPER: (1) the orchestrator/eval-server batching path -- can a batched forward return priors/value mis-aligned to the requesting board (index/ordering bug under concurrency)? (2) fp16/autocast paths -- value differs from fp32 enough to flip close games? (3) the paired-seat aggregation and seed=seed vs seed+1 for the two MCTS instances -- any way the SAME rng feeds both players? (4) resume/cache hit detection: a job that died mid-write (now a unique dotfile partial) -- is it correctly NOT counted as done AND re-claimable? (5) the summary/elo computation at the end vs the per-game files -- consistent? (6) shutdown/cleanup leaving a server or queue that blocks the next iter. Report subtle NEW defects.' },

  { key: 'training-selfplay-2nd', prompt: CONTEXT + '\n\n' +
    'RE-AUDIT SURFACE: scripts/run_selfplay_iter.py + scripts/train_iter.py + src/carcassonne_ai/warmstart.py (GameDataset). Round 2 covered the residual-target wiring, the deck reuse, and the diagnostic mislabel. Go DEEPER for MISSED bugs: (1) loss weighting -- value_loss_weight=1.5 vs aux/rank/center/policy weights: does the relative scaling do what is intended, or could a weight be applied to the wrong term / double-counted? (2) the warmstart-mix-fraction=0.0 path -- off-by-one or an empty-mix edge that still pulls warmstart data? (3) streaming/shuffling in GameDataset -- can a partial .npz (the new .<stem>...partial.npz dotfile) be globbed into a training window, or a 0-row npz crash/skew a batch? (4) the optimizer/LR schedule across iters (warm-from resets or continues the schedule?). (5) gradient/NaN handling in train (clip, skip-on-nan). (6) the value_target=residual computation in run_selfplay_iter -- the exact residual formula and any clamp. Report subtle NEW defects that would bias learning.' },

  { key: 'provenance-stats-2nd', prompt: CONTEXT + '\n\n' +
    'RE-AUDIT SURFACE: src/carcassonne_ai/eval_provenance.py + src/carcassonne_ai/elo.py + the elo/sigma math wherever it gates a decision + governance/CLAIM_REGISTRY.csv consistency. First pass covered the seed-floor guard + the R1/R7 asserts. Go DEEPER: (1) can assert_provenance_consistent be satisfied while the ACTUAL runtime leaf differs -- e.g. the counters are only checked in --provenance-smoke (single-process), NOT the production Pool, so a Pool worker could run a different leaf undetected (is this a real gap, distinct from the deferred items)? (2) elo.py update_pair / the elo and sigma formulas -- any asymmetry, or a sigma that is unpaired where the caller treats it as paired (mislabeling that affects a gate threshold)? (3) deck_hash collisions / the hash truncation length. (4) CLAIM_REGISTRY: are the recent edits (CL-002 Disfavored, CL-005 Provisional, CL-010 Provisional, CL-017 added) internally consistent (superseded_claims pointers, falsifiers, no claim citing stale evidence)? Report subtle NEW defects.' },
]

phase('Reaudit')
const reviewed = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, { label: 'r4:' + d.key, phase: 'Reaudit', schema: FINDINGS }),
  (rev, d) => {
    const fs = ((rev && rev.findings) || []).filter(f => f.severity !== 'low')
    if (!fs.length) return []
    return parallel(fs.map(f => () =>
      agent(CONTEXT + '\n\nADVERSARIALLY VERIFY this second-pass finding from the ' + d.key + ' re-audit. Default to is_real=false unless you confirm, by reading the actual code at ' + f.file + ':' + (f.line || '?') + ', that the defect is genuine, would really bite the live run or a strength claim, AND is NOT one of the already-fixed/deferred/resolved items in the context (a re-find of a known item = is_real=false). Re-derive it yourself. Set the FINAL severity.\n\nFINDING:\ntitle: ' + f.title + '\nseverity(reported): ' + f.severity + '\ncategory: ' + f.category + '\ndescription: ' + f.description + '\nwhy_it_matters: ' + (f.why_it_matters || '') + '\nsuggested_fix: ' + f.suggested_fix,
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
log('r4 re-audit: ' + all.length + ' reviewed, ' + confirmed.length + ' confirmed NEW+real')
return {
  confirmed_count: confirmed.length,
  reviewed_count: all.length,
  confirmed: confirmed.map(f => ({
    severity: f.verdict.severity_final, confidence: f.verdict.confidence, dimension: f.dimension,
    title: f.title, file: f.file, line: f.line, category: f.category,
    description: f.description, suggested_fix: f.suggested_fix, verify_reasoning: f.verdict.reasoning,
  })),
}
