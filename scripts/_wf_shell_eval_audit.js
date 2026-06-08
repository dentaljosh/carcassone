export const meta = {
  name: 'shell-eval-surface-audit',
  description: 'Deep re-audit of the shell + eval-harness surface by failure-mode: concurrency/shared-claim races, box-death recovery, eval game/scoring internals, ssh/quoting robustness, process lifecycle',
  phases: [
    { title: 'Audit', detail: '5 failure-mode lenses across the shell + eval harnesses' },
    { title: 'Verify', detail: 'adversarially confirm each medium+ finding' },
  ],
}

const REPO = '/home/doctor/projects/carcassone'

const CONTEXT = [
  'READ-ONLY audit. Do NOT execute scripts or evals (a 24h flywheel is LIVE on the 3-box cluster). Do NOT modify files or touch processes. Repo: ' + REPO + '.',
  'You are auditing the SHELL + EVAL-HARNESS surface of an AlphaZero-style Carcassonne project by FAILURE MODE. Two other reviews already ran: round 1 covered the shell by-file and fixed 16 bugs (commit 702781e); a concurrent round 2 covers the TRAINING pipeline + an odometer anomaly + fix-regression. Do NOT duplicate those: this audit hunts CONCURRENCY, FAILURE-RECOVERY, EVAL-HARNESS-INTERNAL, and PROCESS-LIFECYCLE defects in the live cluster scripts.',
  'Key scripts: scripts/run_residual_flywheel.sh (the live 12-iter loop: 3-box gate + odometer + gen via shared-claim, self-heal), scripts/auto_chain_h2h_flywheel.sh (the orchestrator that ran the h2h), scripts/run_h2h_residual_vs_iter11.sh, scripts/eval_net_vs_heuristic.py and scripts/eval_iter_head_to_head.py (the eval harnesses that actually play+score games), and /mnt/c/carc-shared/code_sync/gen_flywheel.sh.',
  'Cluster facts: 5800x local (share /mnt/c/carc-shared, repo /home/doctor/projects/carcassone, W=14) plus xeon-wsl (share /mnt/carc-shared, W=10, reached via ssh xeon-wsl into WSL2 - cmd.exe/quoting traps) plus laptop (share /mnt/carc-shared, W=14-20, native linux, ssh laptop, intermittent Tailscale rc=255 jitter). --shared-claim coordinates boxes by writing .claim files next to outputs; a .claim with no output = stranded (orphan-stall / the 556-600 bug). Killing a multiprocessing main does NOT reap its spawn workers (they orphan). The share can unmount mid-run (NoSuchFile / permission errors). SSH can die (SIGHUP) - long jobs use nohup/setsid.',
  'Find REAL defects that would, under a realistic failure (box death, ssh jitter, share unmount, disk full, partial write, simultaneous gate+odo+gen), cause: data corruption, a hang/infinite-loop, a silently-wrong eval number, a resource leak, or double-counted/duplicate games. Give file:line, severity, and a concrete fix. Severity by real-world impact on the LIVE run, not style.',
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
  { key: 'shared-claim-races', prompt: CONTEXT + '\n\n' +
    'LENS: CONCURRENCY / SHARED-CLAIM CORRECTNESS across the 3-box pools (gate, odometer, gen, h2h). Read the claim/skip logic in scripts/eval_net_vs_heuristic.py and scripts/eval_iter_head_to_head.py (how a worker CLAIMS a seed: does it atomically create the .claim before computing, is there a check-then-act TOCTOU window where two boxes claim the same seed?), and the self-heal in run_residual_flywheel.sh (_clean_stranded with age guard, the stall->relaunch). Scrutinize: (1) can two boxes (or two workers) compute the SAME seed and both write the output (double-count / inconsistent overwrite)? (2) does _clean_stranded race with a LIVE worker (delete a claim that a slow-but-alive worker still holds, causing a duplicate)? (3) the wait-loop count vs target: can it conclude early (counts a partial/duplicate) or spin forever? (4) NFS/CIFS atomicity: is .claim creation atomic on the CIFS share (O_CREAT|O_EXCL vs open+write)? Report concrete race/double-count defects.' },

  { key: 'failure-recovery', prompt: CONTEXT + '\n\n' +
    'LENS: FAILURE-MODE RECOVERY. Walk each script through realistic failures and check it detects+recovers rather than hangs/corrupts. Files: run_residual_flywheel.sh, auto_chain_h2h_flywheel.sh, gen_flywheel.sh, run_h2h_residual_vs_iter11.sh. Scenarios: (1) a remote ssh launch returns rc=255 (Tailscale jitter) - does the box silently drop out with no retry, stalling throughput? (2) the CIFS share unmounts mid-run (writes fail with permission/NoSuchFile) - does a worker crash-loop, write partial files, or hang the wait loop? (3) a worker dies mid-game leaving a partial .json/.npz - does the count/elo logic skip it or choke? (4) disk full on the share - silent data loss? (5) the GPU eval-server dies - do workers block forever on IPC? (6) does any wait-loop lack a max-iteration / deadline backstop so a permanent failure hangs the 24h run indefinitely? Report concrete unrecovered-failure defects.' },

  { key: 'eval-harness-internals', prompt: CONTEXT + '\n\n' +
    'LENS: the EVAL HARNESS GAME + SCORING internals (the code that actually determines every eval number). Files: scripts/eval_net_vs_heuristic.py and scripts/eval_iter_head_to_head.py. Round 1 audited provenance; you audit the GAME LOOP and SCORING. Scrutinize: (1) seat/color assignment + paired logic: in --paired, are the two seats for a deck truly the SAME deck played both ways, and is the per-deck result aggregated without double counting? (2) won_by_net / won_by_new / drew / diff: correct sign from the intended perspective, draws handled, no off-by-one in score_p0 vs score_p1? (3) the resume/cache: a cached result from a DIFFERENT config (sims/c_puct/leaf/residual_scale) - can it be silently reused for the current run (filename/key collision)? (4) net_player rotation: does the net actually play the claimed seat, or could a bug swap net/heur? (5) determinism: same seed -> same game (seeds for net vs heur set correctly, e.g. seed vs seed+1)? Report concrete scoring/seat/cache defects that would bias the numbers.' },

  { key: 'ssh-quoting-env', prompt: CONTEXT + '\n\n' +
    'LENS: ssh / QUOTING / ENV-PROPAGATION robustness across the cmd.exe->wsl and native-linux hops. Files: run_residual_flywheel.sh (_gate_launch, _odo_launch, _gen_launch ssh lines), auto_chain_h2h_flywheel.sh (launch_h2h ssh lines), gen_flywheel.sh. Scrutinize: (1) do env vars (CARCASSONNE_V25_RESIDUAL_SCALE, CAP, DROP_THREE_OPEN, SCALE, GAMES) actually propagate INTO the remote process, or get lost across ssh/wsl/setsid (so a remote box runs with WRONG knobs - silent eval contamination)? (2) the SHARE_LOCAL vs SHARE_REMOTE path translation (the ckpt rckpt substitution): any path that reaches a remote box with the LOCAL /mnt/c path (NoSuchFile) or vice-versa? (3) shell-operator mangling on the xeon cmd.exe->wsl hop (&&, |, redirects interpreted by the wrong shell)? (4) setsid/nohup/disown correctness so remote jobs survive ssh death AND the wsl-teardown failure mode? (5) does a remote launch failure get detected (rc check) or silently swallowed? Report concrete env/path/quoting defects causing wrong-knob or missing-box runs.' },

  { key: 'process-lifecycle', prompt: CONTEXT + '\n\n' +
    'LENS: PROCESS / RESOURCE LIFECYCLE. Files: run_residual_flywheel.sh, auto_chain_h2h_flywheel.sh, gen_flywheel.sh. Scrutinize: (1) orphan reaping: when the loop relaunches a box (self-heal) or moves to the next iter, are the PRIOR iter workers actually dead, or do orphaned spawn-workers accumulate across 12 iters (killing the mp main does NOT reap workers) - eating cores/VRAM and corrupting the next iter throughput? (2) when gate + odometer + gen could overlap (or back-to-back), is there GPU/CPU oversubscription that thrashes (worker-count-by-bottleneck: orchestrator W~18 vs cpu-leaf W<=10)? (3) nice levels: are ALL long workers nice -n 19 (including remote ssh ones) so they yield to interactive use? (4) /tmp log files and stage dirs (/tmp/fw_stage_$it): cleaned up, or accumulate/clash across iters? (5) the detached flywheel main on the 5800x: does anything (ssh death, wsl) kill it mid-run, losing 24h of progress? Report concrete leak/oversubscription/teardown defects.' },
]

phase('Audit')
const reviewed = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, { label: 'shell:' + d.key, phase: 'Audit', schema: FINDINGS }),
  (rev, d) => {
    const fs = ((rev && rev.findings) || []).filter(f => f.severity !== 'low')
    if (!fs.length) return []
    return parallel(fs.map(f => () =>
      agent(CONTEXT + '\n\nADVERSARIALLY VERIFY this finding from the ' + d.key + ' audit. Default to is_real=false unless you confirm, by reading the actual code at ' + f.file + ':' + (f.line || '?') + ', that the defect is genuine and would really bite the LIVE run under a realistic failure. Re-derive it yourself. Set the FINAL severity.\n\nFINDING:\ntitle: ' + f.title + '\nseverity(reported): ' + f.severity + '\ncategory: ' + f.category + '\ndescription: ' + f.description + '\nwhy_it_matters: ' + (f.why_it_matters || '') + '\nsuggested_fix: ' + f.suggested_fix,
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
log('shell-eval audit: ' + all.length + ' reviewed, ' + confirmed.length + ' confirmed real')
return {
  confirmed_count: confirmed.length,
  reviewed_count: all.length,
  confirmed: confirmed.map(f => ({
    severity: f.verdict.severity_final, confidence: f.verdict.confidence, dimension: f.dimension,
    title: f.title, file: f.file, line: f.line, category: f.category,
    description: f.description, suggested_fix: f.suggested_fix, verify_reasoning: f.verdict.reasoning,
  })),
}
