"""Live verification that O_EXCL claim creation is atomic on a shared mount.

`run_selfplay_iter.py --shared-claim` relies on `os.open(O_CREAT|O_EXCL)` being
atomic across machines on the shared (CIFS) filesystem. Local correctness is
unit-tested in `tests/test_selfplay_claim.py`; this script verifies the real
two-box mount — it is the deploy gate for work-stealing.

Procedure (same repo on both boxes; --claim-dir is each box's own path to the
shared folder — they may differ, e.g. a CIFS mount on one box and the drvfs
/mnt/c path on the other):

  # On BOTH boxes, same --start-at a few seconds in the future (epoch secs)
  # so the two boxes race the same seeds simultaneously:
  python scripts/verify_shared_claim.py --claim-dir <shared>/verify \\
      --n 1000 --host <boxname> --start-at <epoch>
  # Once both have finished, on either box:
  python scripts/verify_shared_claim.py --claim-dir <shared>/verify \\
      --n 1000 --tally

PASS = every seed 0..n-1 was won by exactly one box. A seed won by two boxes
means the filesystem did NOT honor O_EXCL across machines — work-stealing is
unsafe to deploy on that mount.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import socket
import sys
import time
import zlib
from pathlib import Path

# Import the REAL claim primitive from run_selfplay_iter.py so the verifier
# exercises production code, not a copy.
_SCRIPT = Path(__file__).resolve().parent / "run_selfplay_iter.py"
_spec = importlib.util.spec_from_file_location("run_selfplay_iter", _SCRIPT)
_rsi = importlib.util.module_from_spec(_spec)
sys.modules["run_selfplay_iter"] = _rsi
_spec.loader.exec_module(_rsi)


def _claim(claim_dir: Path, host: str, n: int, reset: bool,
           start_at: float | None) -> int:
    claim_dir.mkdir(parents=True, exist_ok=True)
    if reset:
        for pat in ("seed_*.claim", "result_*.json", ".*.recovering.*"):
            for f in claim_dir.glob(pat):
                f.unlink()
        print(f"reset {claim_dir}")
    if start_at is not None:
        delay = start_at - time.time()
        if delay > 0:
            print(f"waiting {delay:.1f}s for the synchronized start ...")
            sys.stdout.flush()
            if delay > 0.3:
                time.sleep(delay - 0.3)
            while time.time() < start_at:  # spin the last bit for precision
                pass
        elif delay < -2:
            print(f"WARNING: --start-at was {-delay:.0f}s ago; this box may "
                  f"race after the other has finished (no real contention)")
    # Walk seeds in a host-specific shuffled order — the same crc32(host)
    # shuffle run_selfplay_iter.py uses — so the two boxes traverse the range
    # differently and genuinely contend. (In lockstep order one box just stays
    # a hair ahead and sweeps every seed, which tests nothing.)
    seeds = list(range(n))
    random.Random(zlib.crc32(host.encode())).shuffle(seeds)
    won: list[int] = []
    t0 = time.perf_counter()
    for seed in seeds:
        # stale_secs huge -> no stale-recovery -> a pure O_EXCL create race.
        if _rsi._try_claim(_rsi._claim_path(claim_dir, seed), host, 10 ** 9):
            won.append(seed)
    dt = time.perf_counter() - t0
    result = claim_dir / f"result_{host}.json"
    result.write_text(json.dumps({"host": host, "n": n, "won": won}))
    print(f"{host}: won {len(won)}/{n} seeds in {dt:.2f}s -> {result.name}")
    return 0


def _tally(claim_dir: Path) -> int:
    results = sorted(claim_dir.glob("result_*.json"))
    if len(results) < 2:
        print(f"FAIL: need >=2 result_*.json in {claim_dir}, found {len(results)}")
        return 1
    winners: dict[int, list[str]] = {}
    hosts: list[str] = []
    race_ns: set[int] = set()
    for rf in results:
        r = json.loads(rf.read_text())
        hosts.append(r["host"])
        race_ns.add(int(r["n"]))
        for seed in r["won"]:
            winners.setdefault(seed, []).append(r["host"])
    # The authoritative seed count comes from the race result files, not a
    # CLI arg: a --tally invoked with a different --n than the race actually
    # used would otherwise report false "missing" seeds (false FAIL) or skip
    # checking high seeds (false PASS on a deploy gate). All boxes must agree.
    if len(race_ns) != 1:
        print(f"FAIL: result files disagree on the seed count raced: "
              f"{sorted(race_ns)}")
        return 1
    n = race_ns.pop()
    double = {s: h for s, h in winners.items() if len(h) > 1}
    missing = [s for s in range(n) if s not in winners]
    n_claims = len(list(claim_dir.glob("seed_*.claim")))
    print(f"boxes: {hosts}")
    print(f"seeds won: {len(winners)}/{n}   .claim files on disk: {n_claims}")
    if double:
        print(f"FAIL: {len(double)} seed(s) won by >1 box — O_EXCL is NOT "
              f"atomic across this mount. Examples: {dict(list(double.items())[:5])}")
        return 1
    if missing:
        print(f"FAIL: {len(missing)} seed(s) won by NOBODY — a _try_claim "
              f"swallowed an error. Examples: {missing[:5]}")
        return 1
    print(f"PASS: all {n} seeds won by exactly one box. O_EXCL is atomic "
          f"across this shared mount — work-stealing is safe to deploy.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="verify_shared_claim")
    p.add_argument("--claim-dir", type=Path, required=True,
                   help="Directory on the shared mount to race claims in.")
    p.add_argument("--n", type=int, default=1000, help="Seeds to race (0..n-1).")
    p.add_argument("--host", type=str, default=None,
                   help="This box's identity (claim mode). Default: hostname.")
    p.add_argument("--reset", action="store_true",
                   help="Wipe prior claim/result files before racing.")
    p.add_argument("--start-at", type=float, default=None,
                   help="Unix epoch time to begin the race. Pass the SAME "
                        "value on both boxes (a few seconds in the future) so "
                        "they race simultaneously — the contention is the "
                        "whole point of the test.")
    p.add_argument("--tally", action="store_true",
                   help="Tally mode: verify every seed was won exactly once.")
    args = p.parse_args(argv)
    if args.tally:
        return _tally(args.claim_dir)
    return _claim(
        args.claim_dir, args.host or socket.gethostname(),
        args.n, args.reset, args.start_at,
    )


if __name__ == "__main__":
    sys.exit(main())
