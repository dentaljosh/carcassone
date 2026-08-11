export const meta = {
  name: 'core-audit-r3',
  description: 'Round 3 over both surfaces: the ALGORITHMIC CORE (MCTS search, v2.7 leaf, model/checkpoint, residual-target round-trip) + verify the just-applied fixes',
  phases: [
    { title: 'Audit', detail: '5 core dimensions: fix-verification, mcts-search, v2.7-leaf, model-checkpoint, data-roundtrip' },
    { title: 'Verify', detail: 'adversarially confirm each medium+ finding' },
  ],
}

const REPO = '/home/doctor/projects/carcassone'

const CONTEXT = [
  'READ-ONLY audit. Do NOT execute scripts/evals/training (a 24h flywheel is LIVE on the 3-box cluster; running anything contends with it). Do NOT modify files or processes. Repo: ' + REPO + '.',
  'This is ROUND 3 over an AlphaZero-style Carcassonne project. THREE prior multi-agent rounds already exist and their findings are FIXED or DEFERRED -- DO NOT re-report them:',
  ' - Round 1 (shell by-file) + Round 2 (training-pipeline wiring) + a shell-eval FAILURE-MODE audit already covered: the orchestrator/flywheel shell, eval provenance, elo-stats, stale-seeds, concurrency/shared-claim races, failure-recovery, ssh/quoting, process-lifecycle, the self-play->train->gate WIRING, and keep-best lineage.',
  ' - Already FIXED (commits): 702781e (round-1: heur-leaf v2_7 on the 6 flywheel evals, gate_elo nan-proofing, ITERS-override, orchestrator JSON/nan/stall/partial hygiene); e3a8f2a (ladder_asymmetric.py --heur-leaf default v2_7; CL-010 downgraded); 236f582 (eval partial temp -> .<stem>.<host>.<pid>.partial.json in eval_net_vs_heuristic.py AND eval_iter_head_to_head.py); gen_flywheel.sh (share) got a HOST!=5800x reset-skip + a remote git-sync rc-guard.',
  ' - Already RESOLVED: the +52.5-vs-(-29) odometer anomaly = R1-redux (old ladder used v1 leaf); +52.5 (matched v2_7) is trustworthy. DO NOT re-litigate.',
  ' - Already DEFERRED (do NOT re-report): in run_residual_flywheel.sh -- no per-loop deadline/heal-cap (D-S1), heal does not pkill prior pool (D-S2), _clean_stranded 4-min age < game length (D-S3), ssh rc=255 drops a box (D-S4); and eval_iter_head_to_head cache key omits config (D-S5).',
  'ROUND 3 GOES DEEPER -- into the ALGORITHMIC CORE that the wiring-focused rounds skipped, PLUS a fresh-eyes regression check of the just-applied fixes. The flywheel is mid-run (iter2), so a bug in the CORE (MCTS, the v2.7 leaf, the model, the residual target) would silently bias BOTH self-play and every eval -- higher stakes than the shell.',
  'Find REAL defects in the core algorithms or a REGRESSION in the recent fixes. Give file:line, severity, concrete fix. Severity by real impact on correctness of the live run or its strength claims.',
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
  { key: 'fix-verification', prompt: CONTEXT + '\n\n' +
    'DIMENSION: fresh-eyes REGRESSION CHECK of the just-applied fixes (the author wrote these in a hurry overnight). Read the CURRENT code: scripts/eval_net_vs_heuristic.py (the _save temp name ~line 116, now .<stem>.<host>.<pid>.partial.json), scripts/eval_iter_head_to_head.py (~line 170, same change + a new `import os`), scripts/ladder_asymmetric.py (run_rung now appends --heur-leaf; new arg default v2_7), and /mnt/c/carc-shared/code_sync/gen_flywheel.sh (HOST!=5800x reset-skip + rc-guard). Scrutinize: (1) does ANY code READ or glob the partial temp by its OLD name (<stem>.partial.json), or rely on it being non-dotted, so the rename breaks a reader/resume? (2) does the new dot-prefixed name actually get EXCLUDED by the wait-loop ls glob AND python glob.glob AND any find -name used on the same dirs (find -name DOES match dotfiles -- is any count done via find)? (3) is os/socket actually imported where used in both eval files (NameError risk)? (4) the gen_flywheel rc-guard: does `&& ... || { exit 1; }` have the intended precedence (could a fetch success + reset failure still slip through, or a `||` bind to the wrong command)? (5) the HOST!=5800x skip: any way the local box now runs DIFFERENT code than remotes in a way that biases self-play data? Report regressions in the recent fixes only.' },

  { key: 'mcts-search-core', prompt: CONTEXT + '\n\n' +
    'DIMENSION: the MCTS SEARCH CORE (used by BOTH self-play gen and every eval). Files: src/carcassonne_ai/mcts.py (and any neural-MCTS / search code). Scrutinize the ALGORITHM, not the shell: (1) PUCT selection -- c_puct, the prior weighting, the FPU (first-play-urgency) reduction sign/value, Q-value perspective (is Q always from the to-move player POV, including after the tile->meeple two-phase transition where the acting player may or may not change?). (2) value backup -- correct sign flipping per ply / per acting-player, no double-negation, terminal value handling. (3) virtual loss + transposition de-dup -- can a transposed-but-unexpanded node back up a bogus 0.0 (a class of bug fixed before -- is any variant still live)? (4) the residual leaf integration: how does leaf = clip(v2.7 + scale*Delta, +/-1) enter the search value, and is it applied identically in self-play (residual-scale on) and eval? (5) the search-derived value_target (search-Q) recorded for training -- correct POV/sign. Report concrete search-correctness defects that would bias self-play targets or eval results.' },

  { key: 'v27-leaf-foundation', prompt: CONTEXT + '\n\n' +
    'DIMENSION: the hand-crafted v2.7 LEAF (virtual_score_v2) -- the foundation everything rests on (the search leaf, the residual target baseline, AND the gate/odometer opponent). Find it (grep virtual_score / virtual_score_v2 / make_v25 in src/carcassonne_ai/). Scrutinize: (1) scoring correctness -- city/road/cloister/FARM scoring, the CAP=12 cap, DROP_THREE_OPEN, tie handling (canonical rules: all tied owners score full); any double-count or sign error in the score estimate? (2) is the leaf value normalized to the same scale/POV the network value head uses (so v2.7 + scale*Delta is dimensionally sane)? (3) determinism: is virtual_score_v2 start-independent / order-independent (a prior farm-region bug made it start-dependent -- is find_farm or any region traversal still nondeterministic)? (4) the residual Delta = search-Q minus tanh(vs2/15) (or whatever the actual formula): is the v2.7 contribution computed consistently between the residual TARGET (in training) and the residual LEAF (in search/eval)? A mismatch would make the value head learn the wrong target. Report concrete leaf/scoring defects.' },

  { key: 'model-checkpoint-residual', prompt: CONTEXT + '\n\n' +
    'DIMENSION: the NETWORK + CHECKPOINT + residual head. Files: the model definition (grep nn.Module / class .*Net / ResNet / value_head / residual in src/carcassonne_ai/), scripts/train_iter.py (save), and the warm-from load path. Scrutinize: (1) the forward pass -- policy/value/residual/aux heads, the value head activation (tanh? range +/-1 matching the leaf?), and the RESIDUAL head specifically (is it a separate head, and is its output the Delta that the leaf adds?). (2) warm-from: does loading best.pt correctly restore the trunk AND all heads, or can a key-mismatch/strict=False silently reinit the value/residual head (so each flywheel iter secretly restarts the value head from noise -> no compounding)? (3) checkpoint save: does iterN.pt persist the residual-head weights + the config (residual_scale, value_target) so eval reconstructs the same net? (4) any device/dtype (fp16) path that changes the value between train and eval. Report concrete model/checkpoint defects that would break residual learning or train/eval consistency.' },

  { key: 'data-roundtrip', prompt: CONTEXT + '\n\n' +
    'DIMENSION: the residual-target DATA ROUND-TRIP, end to end. Trace a single position: features built in self-play -> search-Q computed -> value_target=residual recorded -> .npz written (warmstart.py GameDataset.save) -> GameDataset load (window across iters) -> train batch -> value/residual loss. Files: scripts/run_selfplay_iter.py, src/carcassonne_ai/warmstart.py (GameDataset save/load), scripts/train_iter.py. Scrutinize: (1) is the residual target STORED and LOADED with the same key/shape/sign (no silent transpose, no outcome-vs-residual mixup in the npz schema)? (2) the data WINDOW (--window 10): which iter dirs does iterN actually load -- is it the intended flywheel_residual_v2/iterN_data set, or could it pool stale/foreign data or load 0 games and still train? (3) feature/label alignment -- does row i of features correspond to row i of the value target after any shuffling/streaming? (4) the value_outcome_corr diagnostic in the residual regime (round 2 flagged it is computed vs the residual target but printed against a 0.61 OUTCOME benchmark -- confirm whether that mislabeling could also affect any GATING/early-stop, not just the printout). Report concrete round-trip integrity defects.' },
]

phase('Audit')
const reviewed = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, { label: 'r3:' + d.key, phase: 'Audit', schema: FINDINGS }),
  (rev, d) => {
    const fs = ((rev && rev.findings) || []).filter(f => f.severity !== 'low')
    if (!fs.length) return []
    return parallel(fs.map(f => () =>
      agent(CONTEXT + '\n\nADVERSARIALLY VERIFY this round-3 finding from the ' + d.key + ' audit. Default to is_real=false unless you confirm, by reading the actual code at ' + f.file + ':' + (f.line || '?') + ', that the defect is genuine and would really bias the live run or a strength claim (or is a real regression in the recent fixes). Re-derive it yourself; do not trust the report. Confirm it is NOT one of the already-fixed/deferred items listed in the context. Set the FINAL severity.\n\nFINDING:\ntitle: ' + f.title + '\nseverity(reported): ' + f.severity + '\ncategory: ' + f.category + '\ndescription: ' + f.description + '\nwhy_it_matters: ' + (f.why_it_matters || '') + '\nsuggested_fix: ' + f.suggested_fix,
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
log('r3 core audit: ' + all.length + ' reviewed, ' + confirmed.length + ' confirmed real')
return {
  confirmed_count: confirmed.length,
  reviewed_count: all.length,
  confirmed: confirmed.map(f => ({
    severity: f.verdict.severity_final, confidence: f.verdict.confidence, dimension: f.dimension,
    title: f.title, file: f.file, line: f.line, category: f.category,
    description: f.description, suggested_fix: f.suggested_fix, verify_reasoning: f.verdict.reasoning,
  })),
}
