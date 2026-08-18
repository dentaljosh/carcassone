#!/usr/bin/env python3
"""WHICH prereg pair is live, for python callers — rev R4.5, ONE definition.

The R4 pair lives in `shared_run_r4/`, not `shared_run/`. The R3.3 pair is
SPENT-BY-GATE-FAILURE (`PREREG_FAILURE.md`) — frozen history, never amended,
revived or re-read — but its directory is still on disk and still holds the
RETAINED band-135e9 corpus, so both names are live objects with opposite
permissions:

    shared_run/      SPENT pair. READ-ONLY FOREVER. Holds the retained 135e9
                     positions, which are REUSABLE INPUT (the run stopped
                     PRE-SCORING; no arb/ora/Δ/CI/per-position value was ever
                     computed for them). Writing here would be a mid-run write
                     to a closed run's tracked artifacts — the JCZ failure mode.
    shared_run_r4/   LIVE pair. Everything this campaign writes goes here.

Six scripts hard-coded `shared_run` before R4.5 and every one of them would have
written the live run's artifacts into the DEAD pair's directory, where the
READ_RULE does not look. The name therefore lives in exactly one file —
`measurement/tiearb_widening_20260817/WORKERS.conf` — which the shell launchers
source directly and which this module parses for python callers, so shell and
python cannot drift apart.

This is a deliberately dumb parser: `KEY=value` lines with optional quotes and
`$VAR` interpolation against what it has already read. It exists so python does
not need a shell, and so nobody is tempted to re-type the directory name.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN_ID = "tiearb_widening_20260817"
CAMPAIGN = REPO / "measurement" / RUN_ID
WORKERS_CONF = CAMPAIGN / "WORKERS.conf"

#: Fallbacks used ONLY when WORKERS.conf is unreadable (e.g. a unit test running
#: against a scratch tree). They must agree with the conf; `test_widening_paths`
#: asserts it, so a drift is a test failure rather than a silent divergence.
_FALLBACK = {
    "PREREG_DIR_NAME": "shared_run_r4",
    "BANKED_PREREG_DIR_NAME": "shared_run",
    "BANKED_CORPUS_SUBDIR": "corpus",
    "UNION_CORPUS_SUBDIR": "corpus",
    "EXTENSION_POSITIONS_SUFFIX": "_ext",
}

_LINE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$")


def parse_conf(path=WORKERS_CONF) -> dict:
    """`KEY=value` pairs from a WORKERS.conf-shaped file. Comments and blanks
    ignored; `"..."` stripped; `$VAR` / `${VAR}` resolved against earlier keys."""
    out: dict = {}
    p = Path(path)
    if not p.is_file():
        return dict(_FALLBACK)
    for raw in p.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        m = _LINE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        val = re.sub(r"\$\{?([A-Z_][A-Z0-9_]*)\}?",
                     lambda mm: out.get(mm.group(1), ""), val)
        out[key] = val
    for k, v in _FALLBACK.items():
        out.setdefault(k, v)
    return out


def _conf(conf=None) -> dict:
    return conf if conf is not None else parse_conf()


def run_dir(campaign=CAMPAIGN, conf=None) -> Path:
    """The LIVE prereg dir — everything this campaign writes goes here."""
    return Path(campaign) / _conf(conf)["PREREG_DIR_NAME"]


def banked_dir(campaign=CAMPAIGN, conf=None) -> Path:
    """The SPENT pair's dir. ⚠️ READ-ONLY FOREVER — the retained 135e9 corpus
    is read from here and nothing is ever written back."""
    return Path(campaign) / _conf(conf)["BANKED_PREREG_DIR_NAME"]


def banked_positions(stratum: str, campaign=CAMPAIGN, conf=None) -> Path:
    c = _conf(conf)
    return (banked_dir(campaign, c) / c["BANKED_CORPUS_SUBDIR"]
            / f"positions_{stratum.lower()}")


def extension_positions(stratum: str, campaign=CAMPAIGN, conf=None) -> Path:
    c = _conf(conf)
    return (run_dir(campaign, c) / c["UNION_CORPUS_SUBDIR"]
            / f"positions_{stratum.lower()}{c['EXTENSION_POSITIONS_SUFFIX']}")


def union_positions(stratum: str, campaign=CAMPAIGN, conf=None) -> Path:
    """The corpus of record: banked (retained) + extension, under the LIVE run.
    This is the path every gate and the analyzer read."""
    c = _conf(conf)
    return (run_dir(campaign, c) / c["UNION_CORPUS_SUBDIR"]
            / f"positions_{stratum.lower()}")


def design_doc(conf=None) -> str:
    return f"measurement/{RUN_ID}/{_conf(conf)['PREREG_DIR_NAME']}/DESIGN.md"


def read_rule(conf=None) -> str:
    return f"measurement/{RUN_ID}/{_conf(conf)['PREREG_DIR_NAME']}/READ_RULE.md"


if __name__ == "__main__":
    c = parse_conf()
    print(f"PREREG_DIR_NAME        = {c['PREREG_DIR_NAME']}")
    print(f"BANKED_PREREG_DIR_NAME = {c['BANKED_PREREG_DIR_NAME']} (READ-ONLY)")
    print(f"run_dir                = {run_dir()}")
    print(f"banked_dir             = {banked_dir()}")
    for s in ("s1", "s2"):
        print(f"  {s}: banked={banked_positions(s).name} "
              f"ext={extension_positions(s).name} union={union_positions(s).name}")
    print(f"design_doc             = {design_doc()}")
    print(f"read_rule              = {read_rule()}")
