# Eff Linus round 3 — native Linux (Pop!_OS) vs WSL2, same laptop silicon

> **STATUS: DRAFT/READY 2026-07-30 — laptop booted to Pop!_OS by Joshua; awaiting ssh
> key authorization. Nothing run yet.**

## The question

Rounds 1–2 refuted "WSL is slower than native *Windows*" on both boxes (native Windows
was 1.06–1.25× SLOWER; the laptop divergence was an E-core scheduling artifact —
`83cd015`). But Joshua's original memory ("the laptop felt faster on Pop") is about
native *Linux*, never measured this era. This round: WSL2 vs bare-metal Linux, identical
hardware (i7-14650HX 8P+8E, RTX 4070 Laptop).

## Prior

WSL2's DRAM-latency profile has been repeatedly exonerated; expected result ≈ parity
(0.95–1.05×). The interesting branches: native Linux >1.1× faster (fleet upgrade on a
USB stick — but weigh the operational cost of dual-boot vs the gain) or >1.1× slower
(would localize a WSL *advantage*, surprising and worth a mechanism hunt).

## Protocol (mirror round 2, `83cd015`, exactly where possible)

1. **Access**: ssh <user>@192.168.0.221 (fresh ED25519 host key — do NOT reuse the
   `laptop`/`laptop-wsl` config entries; add a `laptop-pop` Host block). No share
   mount assumed — transport via scp/rsync (git bundle for the repo, per the offline
   sync memory).
2. **Provision** (no sudo assumed until confirmed): uv → CPython **3.13.14 exactly**
   (the A/B ran exact-patch-matched interpreters; keep that), venv + numpy/pyyaml,
   Cython build via system cc (check `cc` exists; if no toolchain, pure-python leaf
   is fine — but then compare against the WSL arm's pure-python cells only, like-for-like).
3. **Cells** (same driver family as round 2; P-core pinned via `taskset`, plus one
   unpinned control to see whether the Linux scheduler demotes background jobs the way
   Windows did — it shouldn't):
   - `champ_k1x32` (single-stream), `champ_k4x172` (k-parallel), `net_cpu_1t`
   - `net_cuda_b1` ONLY if nvidia drivers are present (`nvidia-smi` works) — Pop
     ships them on the nvidia ISO; if absent, skip, don't install drivers.
   - 3 reps alternating; report ratio vs the SAME cells from the WSL arm (laptop
     rows in `measurement/EFFJENSEN_BENCH_BATCH_20260729.md` + round-2 memo).
4. **Confounds to control** (round-2 lessons): CPU governor (`performance` vs
   `powersave` — record it; set `performance` if permitted), thermal (alternate reps),
   affinity (pin + record), and the pure-python-vs-Cython arm mismatch.
5. **Read-out**: append a round-3 section to the Eff Linus memo family
   (`measurement/EFFJENSEN_BENCH_BATCH_20260729.md` or a sibling), LEVER_INDEX
   eff_linus row update, one results-free commit (latency only, no results.csv row).

## Decision hooks

- ≥1.10× native-Linux win on champ cells → surface to Joshua: dual-boot gen fleet
  option (with the honest operational costs: no Windows share, manual boot switching,
  the box can't run its Windows duties).
- 0.95–1.05× → Eff Linus closes for good: WSL2 is a free abstraction on this workload,
  all three rounds agree; Pop reboot optional.
- The 4070 CUDA cell, if it runs: native-Linux CUDA vs WSL CUDA batch-1 latency is a
  bonus datum for the orch story (WSL's /dev/dxg vs native driver path).
