#!/usr/bin/env python3
"""Unit tests for `measurement/jcz_tiearb_20260817/adjudicate.py` — the MECHANICAL
ADJUDICATOR for the JCZ out-of-lineage pricing of the tie arbiter.

Everything here runs on SYNTHETIC JSONL fixtures built in `tmp_path`: no real
games, no rust, no JVM, no cluster, single-threaded. The point is that each §3
gate can be failed EXACTLY ONE AT A TIME (so a `U-UNREADABLE` names the right
gate), that the §4 branch table fires in its committed order, that `D` / `z_D` are
the arithmetic the read-rule specifies, and that §4.3's companion table — CELL A's
absolute result above all — is printed on `U-UNREADABLE` too.

The healthy fixture is deliberately built to satisfy every gate: 320 decks × 2
seatings × 2 cells (the `G-N` floor), one band, one binary sha, a degenerate
commit range, and a two-sided pre-flight.

⭐ **The healthy fixture is TWO-BOX (READ_RULE §0.F.1, owner ruling "make sure its
both boxes, w22 and w30 respectively").** Both cells carry the SAME deck→host
split across `Doctor` and `laptop-wsl`, each host has its own
`PREFLIGHT_<host>_FIRST.json` (`G-J13`) and `PREFLIGHT_<host>_ENV.json` (`G-JCZ`
per-host jar sha, `G-TOOL` cross-host build identity), and the two hosts carry
DIFFERENT JVM packaging strings — which must be REPORTED and must NOT fail
anything, because `G-SPLIT` is what makes the runtime difference incapable of
touching `D`.
"""
from __future__ import annotations

import importlib.util
import json
import math
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ADJ_PATH = REPO / "measurement/jcz_tiearb_20260817/adjudicate.py"

_spec = importlib.util.spec_from_file_location("jcz_tiearb_adjudicate", ADJ_PATH)
adj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adj)


# --------------------------------------------------------------------------- #
# Fixture construction                                                          #
# --------------------------------------------------------------------------- #
BAND = 133_000_000_000
LEAF = "a36d2e15a3b3d71d"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER_COMMIT = "89abcdef0123456789abcdef0123456789abcdef"
BINSHA = "a4318fd59d9d8349"
BUILD_ID = f"carc_rs-0.1.0+{COMMIT[:12]}+rustc1.96.0"
N_DECKS = adj.N_COMMON_FLOOR              # 320 — the G-N deck floor, exactly
FUTURE = time.time() + 3600.0             # every record finishes AFTER the sentinel

# §0.F.1 — the two boxes. `Doctor` is the 5900XT box (W30), `laptop-wsl` the
# laptop (W22); READ_RULE `G-J13` names exactly this pair as EXPECTED.
HOST_LOCAL = "Doctor"
HOST_LAPTOP = "laptop-wsl"
# ⚠️ The disclosed per-host difference (DESIGN §0.1): SAME OpenJDK 17.0.19, a
# different distro base. REPORTED, never a branch input.
JAVA_LOCAL = ('openjdk version "17.0.19" 2026-01-20 / OpenJDK Runtime Environment '
              '(build 17.0.19+10-1-24.04.2-Ubuntu)')
JAVA_LAPTOP = ('openjdk version "17.0.19" 2026-01-20 / OpenJDK Runtime Environment '
               '(build 17.0.19+10-1-26.04.2-Ubuntu)')


def default_split(i: int, n: int) -> str:
    """The static, contiguous deck split of DESIGN §0.1.1: the first 60% of the
    range on the local box, the tail on the laptop."""
    return HOST_LOCAL if i < (n * 3) // 5 else HOST_LAPTOP


def manifest(*, cell_b: bool, leaf=LEAF, rules="fixed_v1", r9="1",
             jcz_rev=None, binsha=BINSHA, commit=COMMIT, tiearb_on_a=False) -> dict:
    """A minimal manifest carrying every witness the §3 gates read, at the
    addresses `scripts/jcz_match/match.py` actually writes them to.

    `binsha=None` omits `carc_rs_binary_sha` entirely — which is what the REAL
    harness does (READ_RULE §0.F.2b: `match.py` never stamps it), and the case
    `G-TOOL` must still pass on."""
    m = {
        "schema": "carcassonne-jcz-match/v1",
        "our_git_rev": commit,
        "jcz_git_rev": jcz_rev or adj.WORKERS_CONF_FALLBACK["JCZ_REV"],
        "jcz_jar": adj.WORKERS_CONF_FALLBACK["JCZ_JAR"],
        "jcz_jar_sha256_16": adj.WORKERS_CONF_FALLBACK["JCZ_JAR_SHA256"][:16],
        "jcz_ai_class": adj.WORKERS_CONF_FALLBACK["JCZ_AI_CLASS"],
        "jcz_ai_config": {},
        "tile_set": "basic:2",
        "rules_profile": rules,
        "r9_env": r9,
        "rules_manifest": {"name": rules, "r9_env_ok": True},
        "cand_leaf_hash": leaf,
        "champion_manifest": {"leaf_hashes": {"harness_leaf_hash": leaf},
                              "code_commit": commit},
    }
    if binsha is not None:
        m["carc_rs_binary_sha"] = binsha
    if cell_b or tiearb_on_a:
        m["champ_tiearb"] = {"enabled": True, "B": 16, "J": 4, "mode": "argmax",
                             "salt": "tiearb2-deploy-v1", "eps": 0.0}
    return m


def record(*, deck, seat, margin, cell_b, fired=5, errors=0, real=None,
           counts=None, final_agree=True, host=None, replicate=0, **mkw) -> dict:
    margin = int(margin)
    winner = "champ" if margin > 0 else ("jcz" if margin < 0 else "draw")
    r = {
        "schema": "carcassonne-jcz-match/v1",
        "deck_seed": deck, "champ_seat": seat, "replicate": replicate,
        "margin_champ_minus_jcz": margin,
        "champ_score": 70 + margin, "jcz_score": 70,
        "winner": winner, "final_agree": final_agree, "replay_ok": True,
        "void": None, "void_detail": None,
        "real": dict(real or {}), "counts": dict(counts or {}),
        "ms_per_move_champ": 2100.0 if cell_b else 780.0,
        "ms_per_move_jcz": 39.0,
        "wall_secs": 266.0 if cell_b else 98.0,
        "finished_at": FUTURE,
        "moves_by_seat": {"0": 71, "1": 71}, "n_actions": 142,
        "manifest": manifest(cell_b=cell_b, **mkw),
    }
    if cell_b:
        r["champ_tiearb"] = {
            "tile_plies": 36, "fired_plies": fired, "fires": fired,
            "pickchanges": 2, "arms_total": 4 * fired, "playouts_total": 64 * fired,
            "secs": 9.57 * fired, "errors": errors, "first_error": None,
            "partial_argmax": 0, "max_plies": 40, "mode": "argmax", "B": 16, "J": 4}
    if host is not None:
        r["host"] = host          # the record-stamp SOURCE G-SPLIT also accepts
    return r


def write_cells(tmp_path: Path, *, diffs, n_decks=N_DECKS, band=BAND,
                a_kw=None, b_kw=None, a_rec=None, b_rec=None,
                hostmap=True, a_split=None, b_split=None, deck_seed_of=None):
    """Write CELL A / CELL B archives **and their `<cell>.hostmap.json` sidecars**.

    `diffs` is a callable `deck_index -> (a_margin, b_margin)`; both seatings of a
    deck get the same margin, so the per-deck paired observation IS that margin and
    `D` is exactly `mean(b - a)` over decks — hand-checkable.

    `a_split` / `b_split` are `(deck_index, n_decks) -> host`; they default to the
    SAME contiguous split on both cells, which is what `G-SPLIT` requires. The two
    sidecars are deliberately written in the TWO different accepted shapes (CELL A
    the `{deck_seed: host}` map, CELL B the inverted `{host: [deck_seed]}` one) so
    both parses are exercised on the healthy path.
    """
    a_path, b_path = tmp_path / "cell_a.jsonl", tmp_path / "cell_b.jsonl"
    a_split = a_split or default_split
    b_split = b_split or a_split
    seed_of = deck_seed_of or (lambda i: band + i)
    for path, is_b in ((a_path, False), (b_path, True)):
        split = b_split if is_b else a_split
        lines, hmap = [], {}
        for i in range(n_decks):
            ma, mb = diffs(i)
            hmap[seed_of(i)] = split(i, n_decks)
            for seat in (0, 1):
                kw = dict((b_kw or {}) if is_b else (a_kw or {}))
                extra = dict((b_rec or {}) if is_b else (a_rec or {}))
                if extra.get("_first_only") and not (i == 0 and seat == 0):
                    extra = {}
                extra.pop("_first_only", None)
                lines.append(json.dumps(record(
                    deck=seed_of(i), seat=seat, margin=(mb if is_b else ma),
                    cell_b=is_b, **kw, **extra)))
        path.write_text("\n".join(lines) + "\n")
        if hostmap:
            side = path.with_suffix(".hostmap.json")
            if is_b:                       # the INVERTED shape, host -> [deck_seed]
                inv: dict = {}
                for d, h in hmap.items():
                    inv.setdefault(h, []).append(d)
                side.write_text(json.dumps(inv))
            else:                          # the deck_seed -> host shape
                side.write_text(json.dumps({str(d): h for d, h in hmap.items()}))
    return a_path, b_path


def write_support(tmp_path: Path, *, band=BAND, commit=COMMIT, binsha=BINSHA,
                  pick_changed=True, bits_unchanged=True,
                  hosts=(HOST_LOCAL, HOST_LAPTOP), build_id=BUILD_ID,
                  env_overrides=None, first_overrides=None):
    """The band sentinel + the PER-HOST `verdicts/PREFLIGHT_<host>_FIRST.json`
    (`G-J13`) and `verdicts/PREFLIGHT_<host>_ENV.json` (`G-JCZ` per-host jar sha,
    `G-TOOL` cross-host build identity) witnesses.

    The two hosts get DIFFERENT JVM packaging strings on purpose (DESIGN §0.1's
    disclosed difference) and the SAME jar sha, build id and binary sha.
    """
    sentinel = tmp_path / "BAND_CLAIM.txt"
    sentinel.write_text(f"{band}\nJCZ out-of-lineage pricing\nclaimed 2026-08-17\n")
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir(exist_ok=True)
    java = {HOST_LOCAL: JAVA_LOCAL, HOST_LAPTOP: JAVA_LAPTOP}
    for h in hosts:
        first = {
            "kind": "jcz_tiearb_preflight", "host": h,
            "toolchain": {"code_rev": commit}, "carc_rs_binary_sha": binsha,
            "all_preflight_pass": True,
            "two_sided": {"pick_changed": pick_changed,
                          "root_leaf_value_bits_unchanged": bits_unchanged},
        }
        first.update((first_overrides or {}).get(h, {}))
        (verdicts / f"PREFLIGHT_{h}_FIRST.json").write_text(json.dumps(first))
        env = {
            "witness": "G-TOOL", "label": "FIRST", "host": h,
            "git_head": commit, "git_dirty_code_paths": [],
            "carc_rs_binary_sha": binsha, "carc_rs_build_id": build_id,
            "carc_rs_version": "0.1.0", "rustc": "rustc 1.96.0",
            "java": java.get(h, JAVA_LOCAL),
            "jcz_jar": adj.WORKERS_CONF_FALLBACK["JCZ_JAR"],
            "jcz_jar_sha256": adj.WORKERS_CONF_FALLBACK["JCZ_JAR_SHA256"],
            "jcz_jar_sha256_expected": adj.WORKERS_CONF_FALLBACK["JCZ_JAR_SHA256"],
            "jcz_jar_sha256_match": True,
            "jcz_rev": adj.WORKERS_CONF_FALLBACK["JCZ_REV"],
            "jcz_ai_class": adj.WORKERS_CONF_FALLBACK["JCZ_AI_CLASS"],
            "jcz_tiles": adj.WORKERS_CONF_FALLBACK["JCZ_TILES"],
        }
        env.update((env_overrides or {}).get(h, {}))
        (verdicts / f"PREFLIGHT_{h}_ENV.json").write_text(json.dumps(env))
    return sentinel, verdicts


def run(tmp_path, a_path, b_path, sentinel, verdicts, capsys=None):
    """Invoke `main()` exactly as the CLI does, and return `(readout, stdout)`."""
    out_json = tmp_path / "READOUT.json"
    rc = adj.main(["--cell-a", str(a_path), "--cell-b", str(b_path),
                   "--json", str(out_json), "--band-claim", str(sentinel),
                   "--verdicts-dir", str(verdicts), "--run-dir", str(tmp_path),
                   "--repo", str(REPO)])
    assert rc == 0, "exit MUST be 0 on every branch, U-UNREADABLE included"
    stdout = capsys.readouterr().out if capsys is not None else ""
    return json.loads(out_json.read_text()), stdout


def healthy(tmp_path, diffs, **kw):
    a, b = write_cells(tmp_path, diffs=diffs, **kw)
    s, v = write_support(tmp_path)
    return a, b, s, v


def rewrite(path: Path, fn):
    """Apply `fn(record, index) -> record` to every line of a cell archive."""
    lines = []
    for i, line in enumerate(path.read_text().splitlines()):
        r = json.loads(line)
        lines.append(json.dumps(fn(r, i) or r))
    path.write_text("\n".join(lines) + "\n")


def host_of(rec, n=N_DECKS) -> str:
    """The host the healthy fixture's contiguous split put this record's deck on."""
    return default_split(rec["deck_seed"] - BAND, n)


def use_champion_manifest_cand_tiearb(path: Path, *, over=None, drop=()):
    """Move CELL B's rung from the manifest's TOP LEVEL to the address the real
    harness stamps the RESOLVED CONFIG at — `champion_manifest.cand_tiearb` — and
    leave `record.champ_tiearb` as the pure firing TELEMETRY it really is (no
    `enabled` / `salt` / `eps` anywhere in it).

    ⚠️ The two are DIFFERENT OBJECTS, not two spellings of one: `cand_tiearb` is the
    config the champion was constructed with, `champ_tiearb` is the per-game counter
    block. Their only overlap is `mode` / `B` / `J`.
    """
    def f(r, i):
        rung = dict(r["manifest"].pop("champ_tiearb"))
        rung.update(over or {})
        for k in drop:
            rung.pop(k, None)
        r["manifest"]["champion_manifest"]["cand_tiearb"] = rung
        for k in ("enabled", "salt", "eps"):
            r["champ_tiearb"].pop(k, None)
        return r
    rewrite(path, f)


# --------------------------------------------------------------------------- #
# 1-3 — the branch table on healthy cells                                       #
# --------------------------------------------------------------------------- #
def test_large_positive_D_is_J_CONFIRMED(tmp_path, capsys):
    # per-deck diff alternates 2 / 4 -> D = 3.0, sd = 1.0, z = 3/(1/sqrt(320)) ~ 53.7
    a, b, s, v = healthy(tmp_path, lambda i: (0, 2 + 2 * (i % 2)))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert out["branch"] == "J-CONFIRMED"
    assert out["D"] == pytest.approx(3.0)
    assert out["z_D"] > 2.0
    assert out["n_common"] == N_DECKS


def test_zero_D_is_J_NULL_BOUNDED(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, lambda i: (0, 1 if i % 2 else -1))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert out["D"] == pytest.approx(0.0)
    assert out["branch"] == "J-NULL-BOUNDED"


def test_large_negative_D_is_J_REVERSED(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, lambda i: (0, -2 - 2 * (i % 2)))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert out["branch"] == "J-REVERSED"
    assert out["D"] == pytest.approx(-3.0)
    assert out["z_D"] <= -2.0


def test_J_SIGN_fires_between_1_and_2_sigma(tmp_path, capsys):
    """A `z_D` in `[+1.0, +2.0)` must select `J-SIGN`, not `J-CONFIRMED`."""
    # spread chosen so mean stays +1 while sd is large enough to hold z under 2.
    a, b, s, v = healthy(tmp_path, lambda i: (0, 13 if i % 2 else -11))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert 1.0 <= out["z_D"] < 2.0, out["z_D"]
    assert out["branch"] == "J-SIGN"


# --------------------------------------------------------------------------- #
# 5 — the arithmetic, hand-checked                                              #
# --------------------------------------------------------------------------- #
def test_D_and_z_D_are_hand_checkable(tmp_path, capsys):
    """4 decks, per-deck diffs 1/2/3/4.

        D    = 2.5
        var  = ((1.5)^2+(0.5)^2+(0.5)^2+(1.5)^2)/3 = 5/3
        se   = sqrt((5/3)/4) = 0.6454972243679028
        z_D  = 2.5 / 0.6454972243679028 = 3.872983346207417
    """
    a, b = write_cells(tmp_path, diffs=lambda i: (0, i + 1), n_decks=4)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["n_common"] == 4
    assert out["D"] == pytest.approx(2.5)
    assert out["se_D"] == pytest.approx(math.sqrt((5.0 / 3.0) / 4.0))
    assert out["z_D"] == pytest.approx(3.872983346207417)
    # the §1 recomputation witness must agree, and G-WITNESS must therefore pass
    assert out["preconditions"]["G-WITNESS"] is True
    assert out["z_D_witness"]["recomputed"]["z_D"] == pytest.approx(out["z_D"])
    # n that would resolve D to 2 sigma at the realized dispersion: 4*(2/3.873)^2 -> 2
    assert out["D_block"]["n_to_resolve_D_2sigma_decks"] == 2
    # ...and this run is SHORT, so it is U-UNREADABLE via G-N, not adjudicated
    assert out["branch"] == "U-UNREADABLE"
    assert "G-N" in out["failed_preconditions"]


def test_naive_difference_is_reported_as_a_diagnostic(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, lambda i: (0, 2 + 2 * (i % 2)))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["D_block"]["naive_summary_difference_DIAGNOSTIC"] == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# 4 — each gate failing INDIVIDUALLY                                            #
# --------------------------------------------------------------------------- #
def _flat(i):
    """The healthy per-deck margins: CELL A flat at 0, CELL B alternating 2/4 —
    `D` = +3.0 with sd 1.0, which convicts comfortably at n = 320 decks."""
    return (0, 2 + 2 * (i % 2))


def test_healthy_fixture_passes_every_gate(tmp_path, capsys):
    """The control for every negative test below: if this ever fails, the gate
    tests are not isolating anything."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"] == {g: True for g in adj.ALL_GATES}, \
        out["failed_preconditions"]


def test_G_BAND_fails_on_a_wrong_band(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, band=BAND)
    s, v = write_support(tmp_path, band=BAND + 5_000_000_000)   # sentinel disagrees
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["branch"] == "U-UNREADABLE"
    assert out["failed_preconditions"] == ["G-BAND"]
    assert out["precondition_detail"]["G-BAND"]["record_deck_sets_agree_with_band"] \
        is False


def test_G_BAND_fails_when_the_sentinel_postdates_game_1(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, _flat)
    import os
    os.utime(s, (FUTURE + 10_000, FUTURE + 10_000))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-BAND"]
    assert out["precondition_detail"]["G-BAND"]["claimed_before_game_1"] is False


def test_G_LEAF_fails_on_a_wrong_leaf_hash(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"leaf": "deadbeefdeadbeef"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-LEAF"]
    obs = out["precondition_detail"]["G-LEAF"]["observed"][out["cell_b"]]
    assert obs["cand_leaf_hash"] == "deadbeefdeadbeef"
    assert obs["resolved_at"] == "cand_leaf_hash"       # the address is REPORTED


def test_G_LEAF_resolves_the_harness_native_address(tmp_path, capsys):
    """With no top-level `cand_leaf_hash`, the gate must resolve the hash where
    `match.py` actually writes it — and say so in `resolved_at`."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        lines = []
        for line in p.read_text().splitlines():
            r = json.loads(line)
            r["manifest"].pop("cand_leaf_hash")
            lines.append(json.dumps(r))
        p.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-LEAF"] is True
    assert (out["precondition_detail"]["G-LEAF"]["observed"][out["cell_a"]]
            ["resolved_at"] == "champion_manifest.leaf_hashes.harness_leaf_hash")


def test_G_ARB_fails_when_CELL_A_carries_a_champ_tiearb_key(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, a_kw={"tiearb_on_a": True})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-ARB"]
    assert out["precondition_detail"]["G-ARB"]["cell_a"][
        "champ_tiearb_addresses_found"] == ["manifest.champ_tiearb"]


def test_G_ARB_fails_on_an_unauthorized_rung(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = []
    for line in b.read_text().splitlines():
        r = json.loads(line)
        r["manifest"]["champ_tiearb"]["B"] = 32        # ⛔ B may not be expanded
        r["champ_tiearb"]["B"] = 32
        lines.append(json.dumps(r))
    b.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-ARB"]
    assert out["precondition_detail"]["G-ARB"]["cell_b"]["checks"]["B"]["ok"] is False


def test_G_ARB_resolves_the_rung_from_the_champion_manifest_cand_tiearb(tmp_path,
                                                                        capsys):
    """⭐ §0.F.2 PRECEDENT (the FIX-2 defect): with NO top-level `champ_tiearb`, all
    six fields must resolve from the address the harness stamps the RESOLVED CONFIG
    at — `manifest.champion_manifest.cand_tiearb` — and say so in `resolved_at`.

    Resolving only from `record.champ_tiearb` (the firing TELEMETRY) leaves
    `enabled` / `salt` / `eps` null, because that block does not carry them: it is a
    DIFFERENT OBJECT, not a second spelling."""
    a, b = write_cells(tmp_path, diffs=_flat)
    use_champion_manifest_cand_tiearb(b)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-ARB"] is True, out["precondition_detail"]["G-ARB"]
    cb = out["precondition_detail"]["G-ARB"]["cell_b"]
    assert cb["conflicts"] == []
    for k in ("enabled", "B", "J", "mode", "salt", "eps"):
        assert cb["checks"][k]["ok"] is True, k
        assert cb["resolved_at"][k] == "champion_manifest.cand_tiearb", k
    # the telemetry address is still READ — it is simply not the only source
    assert "record.champ_tiearb" in cb["addresses_found"]


def test_G_ARB_is_indifferent_to_the_post_R5_phase_gate_key(tmp_path, capsys):
    """⭐ DECISION (merge review R5), locked here: `champion_manifest.cand_tiearb`
    gained a `phase_gate` key AFTER this round's rung was frozen. `G-ARB` must be
    indifferent to it in BOTH directions —

      * a POST-R5 archive carrying `phase_gate` must NOT fail (an unexpected key is
        not a rung drift: the merge is key-wise over `ARB_RUNG_KEYS`), and
      * a PRE-R5 archive whose `phase_gate` is ABSENT must NOT become a retroactive
        FAIL — which is exactly what adding it to `ARB_RUNG_KEYS` would have done to
        every archive this adjudicator exists to read.

    The pre-R5 (absent) leg is what every other `G-ARB` test in this file already
    fixtures; this one pins the post-R5 (present) leg beside it, and pins the two to
    the SAME verdict."""
    assert "phase_gate" not in adj.ARB_RUNG_KEYS

    a, b = write_cells(tmp_path, diffs=_flat)
    use_champion_manifest_cand_tiearb(b, over={"phase_gate": "all"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-ARB"] is True, out["precondition_detail"]["G-ARB"]
    cb = out["precondition_detail"]["G-ARB"]["cell_b"]
    assert cb["conflicts"] == []
    assert "phase_gate" not in cb["checks"]
    # ...and a GATED stamp is equally not a rung drift here (this round's cells are
    # ungated; a round that VARIES the gate pre-registers it in its OWN read rule)
    (tmp_path / "gated").mkdir()
    a2, b2 = write_cells(tmp_path / "gated", diffs=_flat)
    use_champion_manifest_cand_tiearb(b2, over={"phase_gate": "early"})
    s2, v2 = write_support(tmp_path / "gated")
    out2, _ = run(tmp_path / "gated", a2, b2, s2, v2, capsys)
    assert out2["preconditions"]["G-ARB"] is True


def test_G_ARB_fails_on_a_wrong_salt_at_the_manifest_address(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    use_champion_manifest_cand_tiearb(b, over={"salt": "tiearb2-SOMETHING-ELSE"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-ARB"]
    chk = out["precondition_detail"]["G-ARB"]["cell_b"]["checks"]["salt"]
    assert chk["ok"] is False and chk["observed"] == "tiearb2-SOMETHING-ELSE"


def test_G_ARB_fails_when_enabled_is_absent_at_EVERY_address(tmp_path, capsys):
    """ABSENT AT EVERY ADDRESS STILL FAILS: `enabled` exists nowhere but the resolved
    config, so dropping it there leaves it unwitnessed — and unwitnessed VOIDS."""
    a, b = write_cells(tmp_path, diffs=_flat)
    use_champion_manifest_cand_tiearb(b, drop=("enabled",))
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-ARB"]
    chk = out["precondition_detail"]["G-ARB"]["cell_b"]["checks"]["enabled"]
    assert chk["observed"] is None and chk["ok"] is False
    assert chk["resolved_at"] is None


def test_G_ARB_fails_when_two_addresses_DISAGREE(tmp_path, capsys):
    """The config says `B: 16`, the telemetry says the champion actually ran `B: 32`.
    Either could be the truth, so the merge refuses to pick: CONFLICT, VOIDS."""
    a, b = write_cells(tmp_path, diffs=_flat)
    use_champion_manifest_cand_tiearb(b)
    rewrite(b, lambda r, i: r["champ_tiearb"].__setitem__("B", 32))
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-ARB"]
    cb = out["precondition_detail"]["G-ARB"]["cell_b"]
    assert cb["ok"] is False
    assert [c["field"] for c in cb["conflicts"]] == ["B"]
    assert set(cb["conflicts"][0]["addresses"]) == {"champion_manifest.cand_tiearb",
                                                    "record.champ_tiearb"}


def test_G_ARB_cell_A_clause_is_unchanged_by_the_manifest_address(tmp_path, capsys):
    """The CELL A clause still fires on ANY `champ_tiearb` key — and the neighbouring
    spelling `cand_tiearb` on CELL A stays ADVISORY, never a branch input."""
    a, b = write_cells(tmp_path, diffs=_flat)
    use_champion_manifest_cand_tiearb(b)
    rewrite(a, lambda r, i: r["manifest"]["champion_manifest"].__setitem__(
        "cand_tiearb", {"enabled": False}))
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    ca = out["precondition_detail"]["G-ARB"]["cell_a"]
    assert ca["champ_tiearb_addresses_found"] == []
    assert ca["advisory_neighbour_keys_found"] == [
        "manifest.champion_manifest.cand_tiearb"]
    assert out["preconditions"]["G-ARB"] is True


def test_G_FIRE_fails_below_the_phi_effective_floor(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_rec={"fired": 0})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-FIRE"]
    assert out["precondition_detail"]["G-FIRE"]["phi_effective"] == 0.0


def test_G_FIRE_binds_on_phi_effective_not_raw_phi(tmp_path, capsys):
    """The inert surface §0.B describes: fires every ply, errors on every one."""
    a, b = write_cells(tmp_path, diffs=_flat, b_rec={"fired": 5, "errors": 5})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    det = out["precondition_detail"]["G-FIRE"]
    assert det["phi"] == pytest.approx(5.0)             # raw phi clears the floor
    assert det["phi_effective"] == pytest.approx(0.0)   # ...the effective rate does not
    assert "G-FIRE" in out["failed_preconditions"]


def test_G_J13_fails_when_the_positive_control_is_one_sided(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    s, v = write_support(tmp_path, pick_changed=False)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-J13"]


def test_G_J13_fails_when_absent(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    s, v = write_support(tmp_path)
    for f in v.glob("PREFLIGHT_*"):
        f.unlink()
    out, _ = run(tmp_path, a, b, s, v, capsys)
    # the pre-flight also supplies G-TOOL's commit-range witness, so both fail:
    # ABSENT IS FAIL, in both gates, which is the fail-closed posture.
    assert "G-J13" in out["failed_preconditions"]
    assert out["branch"] == "U-UNREADABLE"


def test_G_RULES_fails_with_r9_off(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"r9": "0"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-RULES"]


def test_G_DIVERGE_fails_on_one_REAL_divergence(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat,
                       b_rec={"real": {"SCORE_MISMATCH": 1}, "_first_only": True})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-DIVERGE"]
    assert out["divergence_ledger"][out["cell_b"]]["REAL"] == {"SCORE_MISMATCH": 1}


def test_G_DIVERGE_tolerates_the_two_classified_benign_classes(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat,
                       b_rec={"counts": {"WALL_LEGALITY": 1,
                                         "UNPLACEABLE_REDRAW": 3}})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-DIVERGE"] is True
    assert out["branch"] == "J-CONFIRMED"


def test_G_JCZ_passes_when_the_revs_are_EQUAL(tmp_path, capsys):
    """⭐ REGRESSION (the FIX-1 defect): two byte-identical 40-char revs compared
    EQUAL and the gate still reported `ok: false`, because the per-record witness
    conjoined FULL COVERAGE into the same flag as value equality. Equal revs, fully
    stamped, must read `ok: true` — with the observed value echoed."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-JCZ"] is True
    for cell in (out["cell_a"], out["cell_b"]):
        chk = out["precondition_detail"]["G-JCZ"]["observed"][cell]["checks"][
            "jcz_git_rev"]
        assert chk["observed"] == chk["expected"] == adj.WORKERS_CONF_FALLBACK[
            "JCZ_REV"]
        assert chk["ok"] is True and chk["matches_pin"] is True
        assert chk["records_agree"] is True
        assert chk["stamped_on_every_record"] is True
        assert chk["records_with_witness"] == chk["n_records"] == N_DECKS * 2


def test_G_JCZ_fails_on_a_different_jcz_revision(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"jcz_rev": "f" * 40})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-JCZ"]
    assert out["precondition_detail"]["G-JCZ"]["identical_across_cells"] is False
    chk = out["precondition_detail"]["G-JCZ"]["observed"][out["cell_b"]]["checks"][
        "jcz_git_rev"]
    assert chk["ok"] is False and chk["matches_pin"] is False
    assert chk["observed"] == "f" * 40           # the realized value is REPORTED


def _unstamp_rev_on_the_laptop(path: Path):
    """What `match.py` really does on a box where `git -C <jcz_repo> rev-parse HEAD`
    cannot answer: `_git_rev` returns None, so EVERY game that box played carries
    `jcz_git_rev: null` while running the correctly pinned checkout."""
    rewrite(path, lambda r, i: r["manifest"].__setitem__("jcz_git_rev", None)
            if host_of(r) == HOST_LAPTOP else None)


def test_G_JCZ_passes_when_one_box_could_not_stamp_the_rev(tmp_path, capsys):
    """⭐ §3.1 STRUCTURAL: a NULL is an UNSTAMPED record, not a DIFFERENT one. The
    laptop's `_git_rev` returned None on every game it played; the pinned rev is
    still witnessed on EVERY host at the per-host address the read-rule names, so the
    gate must pass — a coverage conjunct here would void every healthy run that used
    such a box."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        _unstamp_rev_on_the_laptop(p)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-JCZ"] is True, out["precondition_detail"]["G-JCZ"]
    det = out["precondition_detail"]["G-JCZ"]
    chk = det["observed"][out["cell_b"]]["checks"]["jcz_git_rev"]
    assert chk["ok"] is True
    assert chk["stamped_on_every_record"] is False           # the gap is REPORTED
    assert chk["coverage_gap_corroborated_on_every_host"] is True
    assert chk["records_with_witness"] == (N_DECKS * 3) // 5 * 2
    cov = det["record_witness_coverage"]["jcz_git_rev"][out["cell_a"]]
    assert cov["n_records"] == N_DECKS * 2


def test_G_JCZ_fails_when_an_unstamped_rev_has_no_per_host_witness(tmp_path, capsys):
    """FAIL-CLOSED, the other half: the same coverage gap with NOTHING corroborating
    it on the hosts VOIDS. Absence is only ever excused by the pinned value being
    PRESENT AND EQUAL on every host that played."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        _unstamp_rev_on_the_laptop(p)
    s, v = write_support(tmp_path, env_overrides={
        HOST_LOCAL: {"jcz_rev": None}, HOST_LAPTOP: {"jcz_rev": None}})
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-JCZ"]
    chk = out["precondition_detail"]["G-JCZ"]["observed"][out["cell_b"]]["checks"][
        "jcz_git_rev"]
    assert chk["matches_pin"] is True             # the value it DID stamp is right…
    assert chk["coverage_gap_corroborated_on_every_host"] is False   # …but unwitnessed
    assert chk["ok"] is False


def test_G_JCZ_fails_when_the_records_DISAGREE_on_the_rev(tmp_path, capsys):
    """A mixed-provenance cell VOIDS even though every record agrees with SOME rev —
    and even though the per-host ENV witnesses are healthy."""
    a, b = write_cells(tmp_path, diffs=_flat)
    rewrite(b, lambda r, i: r["manifest"].__setitem__("jcz_git_rev", "f" * 40)
            if i % 2 else None)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-JCZ"]
    chk = out["precondition_detail"]["G-JCZ"]["observed"][out["cell_b"]]["checks"][
        "jcz_git_rev"]
    assert chk["records_agree"] is False
    assert len(chk["values_seen"]) == 2
    assert chk["ok"] is False


def test_G_JCZ_fails_when_the_rev_is_absent_from_EVERY_record(tmp_path, capsys):
    """ABSENT AT EVERY ADDRESS STILL FAILS — a corroborating per-host witness excuses
    a GAP, never a witness that no record carries at all."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        rewrite(p, lambda r, i: r["manifest"].__setitem__("jcz_git_rev", None))
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-JCZ"]
    chk = out["precondition_detail"]["G-JCZ"]["observed"][out["cell_a"]]["checks"][
        "jcz_git_rev"]
    assert chk["observed"] is None and chk["ok"] is False
    assert chk["records_with_witness"] == 0


def test_G_TOOL_fails_when_the_binary_sha_differs_across_cells(tmp_path, capsys):
    """The manifest `carc_rs_binary_sha` BINDS WHEN PRESENT (§0.F.2b) — and it is
    compared WITHIN a host across the two cells, never across boxes."""
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"binsha": "ffffffffffffffff"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]["manifest_binary_sha_when_present"]
    assert det["ok"] is False
    assert all(h["equal_across_cells"] is False for h in det["per_host"].values())


def test_G_TOOL_passes_on_a_degenerate_commit_range(tmp_path, capsys):
    """READ_RULE §3.1: a healthy run of this launcher produces a DEGENERATE range
    (pre-flight and manifest at the same commit) and MUST pass. Stage 2 lost an
    adjudication to a version of this conjunct that fired on every healthy run."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    cr = out["precondition_detail"]["G-TOOL"]["commit_range"]
    assert cr["empty"] is True and cr["resolved"] is True
    assert "DEGENERATE" in cr["reason"]
    assert out["preconditions"]["G-TOOL"] is True


def test_G_TOOL_voids_on_an_unresolved_commit_range(tmp_path, capsys):
    """A manifest commit that does not parse is UNRESOLVED, and unresolved VOIDS —
    it is not treated as 'nothing changed'."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        lines = []
        for line in p.read_text().splitlines():
            r = json.loads(line)
            r["manifest"]["our_git_rev"] = "not-a-commit"
            r["manifest"]["champion_manifest"]["code_commit"] = "not-a-commit"
            lines.append(json.dumps(r))
        p.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert "G-TOOL" in out["failed_preconditions"]
    assert out["precondition_detail"]["G-TOOL"]["commit_range"]["resolved"] is False


def test_G_N_fails_below_the_deck_floor(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, n_decks=N_DECKS - 1)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-N"]
    assert out["precondition_detail"]["G-N"]["n_common"] == N_DECKS - 1
    assert out["precondition_detail"]["G-N"]["n_common_floor"] == 320


def test_G_PLY_fails_when_the_ply_witness_is_absent(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = []
    for line in b.read_text().splitlines():
        r = json.loads(line)
        r["champ_tiearb"].pop("partial_argmax")   # absent is unknown-not-zero
        lines.append(json.dumps(r))
    b.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-PLY"]


def test_G_PLY_fails_on_a_nonzero_partial_argmax(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = []
    for i, line in enumerate(b.read_text().splitlines()):
        r = json.loads(line)
        if i == 0:
            r["champ_tiearb"]["partial_argmax"] = 1   # CRN pairing broken in play
        lines.append(json.dumps(r))
    b.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-PLY"]


def test_missing_archive_is_U_UNREADABLE_and_still_exits_zero(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, _flat)
    out, stdout = run(tmp_path, a, tmp_path / "does_not_exist.jsonl", s, v, capsys)
    assert out["branch"] == "U-UNREADABLE"
    assert "CELL A" in stdout


# --------------------------------------------------------------------------- #
# TWO BOXES (READ_RULE §0.F.1) — G-SPLIT, G-COVER, and the per-host gates        #
# --------------------------------------------------------------------------- #
def test_two_box_healthy_fixture_passes_every_gate(tmp_path, capsys):
    """⭐ The §3.1 structural control for the two-box amendment: both cells carry
    the SAME hostmap across TWO hosts, each host has its own pre-flight, and the
    two hosts run DIFFERENT JVM packaging — and every gate passes."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"] == {g: True for g in adj.ALL_GATES}, \
        out["failed_preconditions"]
    assert out["branch"] == "J-CONFIRMED"
    # both boxes are visible in the read-out, with their own game counts
    tb = out["two_box"]
    assert tb["hosts_played"] == sorted([HOST_LOCAL, HOST_LAPTOP])
    for cell in tb["per_cell"].values():
        per_host = cell["per_host"]
        assert set(per_host) == {HOST_LOCAL, HOST_LAPTOP}
        assert sum(h["n_games"] for h in per_host.values()) == N_DECKS * 2
        assert per_host[HOST_LOCAL]["n_decks"] == (N_DECKS * 3) // 5
    # the split is identical across the cells — which is the whole point
    split = out["precondition_detail"]["G-SPLIT"]
    assert split["mismatched_decks"]["n_total"] == 0
    assert split["decks_with_no_host_in_either_cell"]["n_total"] == 0
    assert "TWO-BOX block" in stdout and HOST_LAPTOP in stdout


def test_G_SPLIT_fails_when_one_deck_changed_hosts_between_cells(tmp_path, capsys):
    """DESIGN §0.1.2: a deck that ran on a different box in the two cells puts every
    per-box difference INSIDE the paired difference. The offending seed is NAMED."""
    moved = 3

    def b_split(i, n):
        return HOST_LAPTOP if i == moved else default_split(i, n)

    a, b = write_cells(tmp_path, diffs=_flat, b_split=b_split)
    s, v = write_support(tmp_path)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-SPLIT"]
    det = out["precondition_detail"]["G-SPLIT"]
    assert det["mismatched_decks"]["n_total"] == 1
    assert det["mismatched_decks"]["listed"][0]["deck_seed"] == BAND + moved
    assert det["mismatched_decks"]["listed"][0]["cell_a_host"] == HOST_LOCAL
    assert det["mismatched_decks"]["listed"][0]["cell_b_host"] == HOST_LAPTOP
    assert str(BAND + moved) in stdout          # the seed is named in the read-out


def test_G_SPLIT_fails_closed_when_the_hostmap_is_absent(tmp_path, capsys):
    """ABSENT AT EVERY SOURCE FAILS: no sidecar and no record host stamp means the
    split is UNVERIFIABLE, which is exactly the confound the gate exists to catch."""
    a, b = write_cells(tmp_path, diffs=_flat, hostmap=False)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-SPLIT"]
    det = out["precondition_detail"]["G-SPLIT"]
    assert det["per_cell"][out["cell_a"]]["host_source_resolved"] is None
    assert det["decks_with_no_host_in_either_cell"]["n_total"] == N_DECKS


def test_G_SPLIT_accepts_the_record_host_stamp_as_a_source(tmp_path, capsys):
    """The second accepted source, and `host_source_resolved` must say so."""
    a, b = write_cells(tmp_path, diffs=_flat, hostmap=False, n_decks=N_DECKS,
                       a_rec={"host": HOST_LOCAL}, b_rec={"host": HOST_LOCAL})
    s, v = write_support(tmp_path, hosts=(HOST_LOCAL,))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-SPLIT"] is True
    assert (out["precondition_detail"]["G-SPLIT"]["per_cell"][out["cell_a"]]
            ["host_source_resolved"] == "records")


def test_G_SPLIT_fails_on_an_unparseable_hostmap(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    a.with_suffix(".hostmap.json").write_text("{not json")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert "G-SPLIT" in out["failed_preconditions"]
    assert out["precondition_detail"]["G-SPLIT"]["unparseable_hostmap"]


def test_G_COVER_fails_on_a_duplicate_deck_seat_replicate(tmp_path, capsys):
    """A cell that played the same `(deck_seed, champ_seat, replicate)` twice would
    double-count it."""
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = a.read_text().splitlines()
    a.write_text("\n".join(lines + [lines[0]]) + "\n")     # the SAME game, twice
    s, v = write_support(tmp_path)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-COVER"]
    dups = (out["precondition_detail"]["G-COVER"]["per_cell"][out["cell_a"]]
            ["duplicate_deck_seat_replicate"])
    assert dups["n_total"] == 1
    assert dups["listed"][0]["deck_seed"] == BAND and dups["listed"][0]["n"] == 2
    assert "G-COVER" in stdout


def test_G_COVER_fails_on_an_out_of_band_seed(tmp_path, capsys):
    """A seed outside `[band, band + DECKS − 1]` is not in any per-box range."""
    stray = 5_000

    def seed_of(i):
        return BAND + (stray if i == 7 else i)

    a, b = write_cells(tmp_path, diffs=_flat, deck_seed_of=seed_of)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert "G-COVER" in out["failed_preconditions"]
    oob = (out["precondition_detail"]["G-COVER"]["per_cell"][out["cell_a"]]
           ["out_of_band_deck_seeds"])
    assert oob["n_total"] == 1 and oob["listed"] == [BAND + stray]


def test_G_COVER_fails_when_a_deck_has_only_one_seating(tmp_path, capsys):
    """321 decks so that dropping one seating still leaves `n_common` = 320: the run
    is BIG ENOUGH (`G-N` passes) and fails purely on COVERAGE SHAPE."""
    a, b = write_cells(tmp_path, diffs=_flat, n_decks=N_DECKS + 1)
    lines = a.read_text().splitlines()
    a.write_text("\n".join(lines[:-1]) + "\n")             # drop one seating
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-COVER"]
    det = (out["precondition_detail"]["G-COVER"]["per_cell"][out["cell_a"]]
           ["decks_without_both_seatings"])
    assert det["n_total"] == 1
    assert det["listed"][0]["deck_seed"] == BAND + N_DECKS
    assert det["listed"][0]["seatings_present"] == [0]


def test_G_COVER_passes_on_a_SHORT_but_well_shaped_run(tmp_path, capsys):
    """⭐ THE `G-N` RECONCILIATION, asserted: a run that is merely SHORT fails `G-N`
    on VOLUME and PASSES `G-COVER`, which owns SHAPE. The alternative reading —
    'covers all DECKS decks' literally — would repeal `G-N`'s committed 80% floor
    and void every healthy-but-short run."""
    a, b = write_cells(tmp_path, diffs=_flat, n_decks=8)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-COVER"] is True
    assert out["failed_preconditions"] == ["G-N"]


def test_G_J13_fails_when_a_host_that_played_has_no_preflight(tmp_path, capsys):
    """PER-HOST (§0.F.1): the roster is DERIVED from the hostmap, so a laptop that
    played without a control voids even though the local box's control passed."""
    a, b, s, v = healthy(tmp_path, _flat)
    (v / f"PREFLIGHT_{HOST_LAPTOP}_FIRST.json").unlink()
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-J13"]
    det = out["precondition_detail"]["G-J13"]
    assert det["hosts_that_played_with_NO_preflight"] == [HOST_LAPTOP]
    assert det["hosts_that_played"] == sorted([HOST_LOCAL, HOST_LAPTOP])
    assert det["hosts_expected"] == [HOST_LOCAL, HOST_LAPTOP]


def test_G_JCZ_passes_with_differing_JVM_packaging_but_one_jar_sha(tmp_path, capsys):
    """⭐ The disclosed per-host difference: SAME OpenJDK 17.0.19, different distro
    base. It is REPORTED and it fails NOTHING — the pinned artifacts are the jar and
    the classes, and `G-SPLIT` is what makes the runtime difference incapable of
    touching `D`."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-JCZ"] is True
    det = out["precondition_detail"]["G-JCZ"]
    assert det["jvm_packaging_differs_across_hosts"] is True
    assert det["jar_sha_identical_across_hosts"] is True
    assert det["jvm_version_by_host_REPORTED"][HOST_LOCAL] == JAVA_LOCAL
    assert det["jvm_version_by_host_REPORTED"][HOST_LAPTOP] == JAVA_LAPTOP
    # ...and the difference is REPORTED in the printed read-out, with the reason
    assert "24.04.2" in stdout and "26.04.2" in stdout
    assert "NEVER a branch input" in stdout or "NEVER A BRANCH INPUT" in stdout
    assert "G-SPLIT" in stdout


def test_G_JCZ_fails_on_a_per_host_jar_sha_mismatch(tmp_path, capsys):
    """The jar is verified ON EACH HOST — a swapped jar on the laptop voids."""
    a, b = write_cells(tmp_path, diffs=_flat)
    s, v = write_support(tmp_path, env_overrides={
        HOST_LAPTOP: {"jcz_jar_sha256": "f" * 64, "jcz_jar_sha256_match": False}})
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-JCZ"]
    det = out["precondition_detail"]["G-JCZ"]
    assert det["per_host"][HOST_LAPTOP]["ok"] is False
    assert det["per_host"][HOST_LOCAL]["ok"] is True
    assert det["jar_sha_identical_across_hosts"] is False


def test_G_TOOL_fails_on_mixed_carc_rs_builds_across_boxes(tmp_path, capsys):
    """§0.F.2b conjunct 1: pre-flights compared with PRE-FLIGHTS. Two boxes that
    built different wheels void the run."""
    a, b = write_cells(tmp_path, diffs=_flat)
    s, v = write_support(tmp_path, env_overrides={
        HOST_LAPTOP: {"carc_rs_build_id": f"carc_rs-0.1.0+{COMMIT[:12]}+rustc1.95.0"}})
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]["cross_host_build_identity"]
    assert det["build_id_equal_across_hosts"] is False
    assert det["ok"] is False
    assert set(det["preflight_build_id_by_host"]) == {HOST_LOCAL, HOST_LAPTOP}
    # the two boxes' SHAS are identical in this fixture — the void is the BUILD ID,
    # which is the only cross-host witness that binds (§0.F.2c)
    assert det["binary_sha_equal_across_hosts"] is True


def test_G_TOOL_PASSES_on_differing_binary_shas_across_boxes(tmp_path, capsys):
    """⭐ READ_RULE §0.F.2c — THE CASE THAT VOIDED A HEALTHY RUN (the FIX-3 defect).

    The `.so` is NOT machine-reproducible: the two boxes produce different
    `carc_rs_binary_sha` values at the SAME `carc_rs_build`, measured on this very
    pair. Conjunct 1 therefore binds on the BUILD ID ALONE. The sha inequality is
    still COMPUTED and REPORTED — explicitly labelled NON-BINDING — and it may never
    touch `ok`.

    (This test asserted the OPPOSITE before the fix; that assertion was the forbidden
    cross-host comparison written into the suite.)"""
    a, b = write_cells(tmp_path, diffs=_flat)
    s, v = write_support(tmp_path,
                         env_overrides={HOST_LAPTOP: {"carc_rs_binary_sha": "f" * 16}})
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert out["preconditions"]["G-TOOL"] is True
    det = out["precondition_detail"]["G-TOOL"]["cross_host_build_identity"]
    assert det["binary_sha_equal_across_hosts"] is False     # differing, and REPORTED
    assert det["binary_sha_equal_across_hosts_IS_NON_BINDING"] is True
    assert det["build_id_equal_across_hosts"] is True        # ...the build id is equal
    assert det["ok"] is True
    assert det["binds_on"] == "carc_rs_build (the build id) ONLY"


def test_G_TOOL_1b_fails_when_the_binary_sha_MOVED_within_one_host(tmp_path, capsys):
    """CONJUNCT 1b (§0.F.2c): within a host, across the two cells, the sha DOES bind —
    that is the rebuilt-here / stale-wheel witness. The laptop rebuilt its wheel
    between the cells; the local box did not. The gate voids, 1b names the host that
    moved, and conjunct 1 (build ids) is untouched."""
    a, b = write_cells(tmp_path, diffs=_flat)
    rewrite(b, lambda r, i: r["manifest"].__setitem__(
        "carc_rs_binary_sha", "f" * 16) if host_of(r) == HOST_LAPTOP else None)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]["manifest_binary_sha_when_present"]
    assert sorted(det["hosts_evaluated"]) == sorted([HOST_LOCAL, HOST_LAPTOP])
    assert det["per_host"][HOST_LAPTOP]["equal_across_cells"] is False
    assert det["per_host"][HOST_LAPTOP]["ok"] is False
    assert det["per_host"][HOST_LOCAL]["ok"] is True          # 1b is per HOST
    assert det["ok"] is False
    # ...and the CROSS-HOST conjunct is unaffected: it never looks at the sha
    assert (out["precondition_detail"]["G-TOOL"]["cross_host_build_identity"]["ok"]
            is True)


def test_G_TOOL_1b_passes_when_each_host_kept_its_own_sha(tmp_path, capsys):
    """The REAL two-box shape: each box has its own sha (the .so is not reproducible)
    and neither moved between the cells. 1b passes for BOTH hosts."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        rewrite(p, lambda r, i: r["manifest"].__setitem__(
            "carc_rs_binary_sha", "8ae0b98427debb2e")
            if host_of(r) == HOST_LAPTOP else None)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-TOOL"] is True, out["precondition_detail"]["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]["manifest_binary_sha_when_present"]
    assert det["per_host"][HOST_LOCAL]["per_cell"][out["cell_a"]] == [f'"{BINSHA}"']
    assert all(h["ok"] is True for h in det["per_host"].values())
    assert set(det["per_host"]) == {HOST_LOCAL, HOST_LAPTOP}


def test_G_TOOL_passes_when_the_manifest_has_NO_binary_sha(tmp_path, capsys):
    """⭐ READ_RULE §0.F.2b, the third unsatisfiable conjunct: `match.py` NEVER
    stamps `carc_rs_binary_sha`, so a gate requiring it from the manifest would fail
    on EVERY healthy run. With both pre-flights agreeing, this MUST pass."""
    a, b = write_cells(tmp_path, diffs=_flat,
                       a_kw={"binsha": None}, b_kw={"binsha": None})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-TOOL"] is True, out["precondition_detail"]["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]
    assert det["manifest_binary_sha_when_present"]["present"] is False
    assert det["cross_host_build_identity"]["witness_present"] is True
    assert det["any_build_witness_present"] is True
    assert out["branch"] == "J-CONFIRMED"


def test_G_TOOL_fails_when_no_build_witness_exists_anywhere(tmp_path, capsys):
    """ABSENT AT EVERY SOURCE INCLUDING THE PRE-FLIGHTS STILL FAILS."""
    a, b = write_cells(tmp_path, diffs=_flat,
                       a_kw={"binsha": None}, b_kw={"binsha": None})
    s, v = write_support(tmp_path, build_id=None,
                         env_overrides={h: {"carc_rs_binary_sha": None,
                                            "carc_rs_build_id": None}
                                        for h in (HOST_LOCAL, HOST_LAPTOP)},
                         first_overrides={h: {"carc_rs_binary_sha": None}
                                          for h in (HOST_LOCAL, HOST_LAPTOP)})
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]
    assert det["any_build_witness_present"] is False
    # both sub-conjuncts fail closed on absence: no build id anywhere (conjunct 1),
    # no sha anywhere (conjunct 1b)
    assert det["cross_host_build_identity"]["build_id_witness_present"] is False
    assert det["cross_host_build_identity"]["ok"] is False
    assert det["manifest_binary_sha_when_present"]["present"] is False


def test_G_TOOL_fails_when_our_git_rev_differs_across_cells(tmp_path, capsys):
    """§0.F.2b conjunct 2: cross-CELL code identity."""
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"commit": OTHER_COMMIT})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]["cross_cell_code_identity"]
    assert det["equal_across_cells"] is False
    assert det["observed"][out["cell_b"]]["value"] == OTHER_COMMIT


def test_G_TOOL_fails_on_a_mixed_rev_cell(tmp_path, capsys):
    """Half of CELL B's records at a different rev — a mixed-rev cell VOIDS even
    though every record agrees with SOME rev."""
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = []
    for i, line in enumerate(b.read_text().splitlines()):
        r = json.loads(line)
        if i % 2:
            r["manifest"]["our_git_rev"] = OTHER_COMMIT
            r["manifest"]["champion_manifest"]["code_commit"] = OTHER_COMMIT
        lines.append(json.dumps(r))
    b.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]["cross_cell_code_identity"]
    assert det["observed"][out["cell_b"]]["consistent_across_records"] is False


def test_hostmap_shapes_all_parse_to_the_same_map():
    """The launcher merges per-box shards; every accepted shape must land on the
    SAME `{deck_seed: host}` map, and an unrecognised one must ERROR, not guess."""
    want = {10: "Doctor", 11: "Doctor", 12: "laptop-wsl"}
    for doc in ({"10": "Doctor", "11": "Doctor", "12": "laptop-wsl"},
                {"hostmap": {"10": "Doctor", "11": "Doctor", "12": "laptop-wsl"}},
                {"Doctor": [10, 11], "laptop-wsl": [12]},
                {"shards": [{"host": "Doctor", "decks": [10, 11]},
                            {"host": "laptop-wsl", "decks": [12]}]}):
        got, meta = adj.parse_hostmap_doc(doc)
        assert got == want, doc
        assert meta["error"] is None and meta["shape"]
    bad, meta = adj.parse_hostmap_doc({"decks": 4})
    assert bad == {} and meta["error"]
    dup, meta = adj.parse_hostmap_doc({"Doctor": [10], "laptop-wsl": [10]})
    assert meta["conflicts"] and meta["conflicts"][0]["deck_seed"] == 10
    # `merge_cells.sh`'s CONFLICT sentinel is NOT a host — it is the merge step
    # saying the deck's host is undetermined, and it must fail closed.
    got, meta = adj.parse_hostmap_doc(
        {"hostmap": {"10": "Doctor", "11": "CONFLICT:Doctor|laptop-wsl"}})
    assert got == {10: "Doctor"}
    assert meta["conflicts"] and meta["conflicts"][0]["deck_seed"] == 11


def test_G_SPLIT_fails_on_a_merge_step_CONFLICT_sentinel(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    side = a.with_suffix(".hostmap.json")
    doc = json.loads(side.read_text())
    doc[str(BAND + 2)] = f"CONFLICT:{HOST_LOCAL}|{HOST_LAPTOP}"
    side.write_text(json.dumps({"witness": "G-SPLIT input", "hostmap": doc}))
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-SPLIT"]
    assert out["precondition_detail"]["G-SPLIT"]["intra_cell_host_conflicts"]


# --------------------------------------------------------------------------- #
# 6 — §4.3's companion table is printed on U-UNREADABLE too                      #
# --------------------------------------------------------------------------- #
def test_companion_table_is_printed_on_U_UNREADABLE(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"leaf": "deadbeefdeadbeef"})
    s, v = write_support(tmp_path)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["branch"] == "U-UNREADABLE"
    # ⭐ item 7 — CELL A's absolute result, and the 2026-08-09 reading beside it
    assert "CELL A's ABSOLUTE RESULT vs JCZ" in stdout
    assert "+111.4" in stdout and "0.655" in stdout
    assert "1.8-2.2" in stdout and "REGRESSION TRIPWIRE" in stdout
    # the other seven items
    for item in ("item 1", "item 2", "item 3", "item 4", "item 5", "item 6",
                 "item 8"):
        assert f"§4.3 {item}" in stdout, item
    # item 4 — the §0.C field-name trap, named, with the fields printed
    assert "FIELD-NAME TRAP" in stdout
    assert "ms_per_move_champ" in stdout and "ms_per_move_jcz" in stdout
    assert "2.71" in stdout and "266" in stdout        # DESIGN §6.2's prediction
    # item 8 — the two classified-benign classes named
    assert "WALL_LEGALITY" in stdout and "UNPLACEABLE_REDRAW" in stdout
    # the failed gate is named with its realized value
    assert "G-LEAF" in stdout and "deadbeefdeadbeef" in stdout


def test_dilution_statement_is_verbatim_when_errors_are_nonzero(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_rec={"fired": 20, "errors": 1})
    s, v = write_support(tmp_path)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["dilution"]["statement_required"] is True
    assert "The bias runs toward the champion, so a" in stdout
    assert "lower bound" in stdout


def test_readout_json_carries_the_re_adjudication_keys(tmp_path, capsys):
    """The orchestrating session re-adjudicates BLIND by reading `branch` and
    `failed_preconditions` out of READOUT.json without rendering the statistics —
    so those keys, and every gate's {PASS, realized}, must be there."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    for k in ("branch", "failed_preconditions", "D", "se_D", "z_D", "n_common",
              "cells", "preconditions", "precondition_detail"):
        assert k in out, k
    assert set(out["preconditions"]) == set(adj.ALL_GATES)
    assert out["D_block"]["n_to_resolve_D_2sigma_decks"] is not None
    for cell in out["cells"].values():
        for k in ("elo", "win_rate", "paired_margin_mean", "paired_margin_sem",
                  "paired_margin_z", "ms_ratio", "worker_s_per_game"):
            assert k in cell, k


# --------------------------------------------------------------------------- #
# Unit-level checks on the pieces                                               #
# --------------------------------------------------------------------------- #
def test_deck_pairing_matches_the_jcz_analyzer(tmp_path):
    """`per_deck_balanced` must reproduce `scripts/jcz_match/analyze.py`'s own
    `paired_margin_mean` / `n_paired_decks` — the deck pairing is never a variant."""
    a, _ = write_cells(tmp_path, diffs=lambda i: (i % 7 - 3, 0), n_decks=20)
    mod, prov = adj._import_jcz_analyze(REPO)
    assert prov["imported"] is True, prov
    recs = mod.load(a)
    summary = mod.analyze(recs)
    mine = adj.per_deck_balanced([r for r in recs if not r.get("void")])
    assert len(mine) == summary["n_paired_decks"]
    assert (sum(mine.values()) / len(mine)) == pytest.approx(
        summary["paired_margin_mean"])


def test_half_pair_decks_are_dropped(tmp_path, capsys):
    """A deck with only one seating is not seat-balanced and must not enter `D`."""
    a, b = write_cells(tmp_path, diffs=_flat, n_decks=10)
    lines = b.read_text().splitlines()
    b.write_text("\n".join(lines[:-1]) + "\n")     # drop one seating of the last deck
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["n_common"] == 9


def test_paired_stats_is_the_eval_fair_puct_convention():
    mean, se, z, n = adj.paired_stats([1.0, 2.0, 3.0, 4.0])
    assert (mean, n) == (2.5, 4)
    assert se == pytest.approx(math.sqrt((5.0 / 3.0) / 4.0))
    assert z == pytest.approx(2.5 / se)
    assert adj.paired_stats([1.0]) == (None, None, None, 1)


def test_n_to_reach_uses_absolute_z_and_refuses_zero():
    assert adj.n_to_reach(400, 4.0) == 100
    assert adj.n_to_reach(400, -4.0) == 100      # a negative D is resolved by J-REVERSED
    assert adj.n_to_reach(400, 0.0) is None
    assert adj.n_to_reach(400, float("nan")) is None
    assert adj.n_to_reach(0, 4.0) is None


def test_workers_conf_is_parsed_not_hard_coded():
    conf, meta = adj.parse_workers_conf(
        REPO / "measurement/jcz_tiearb_20260817/WORKERS.conf")
    assert meta["parsed"] is True
    assert conf["CHAMP_LEAF_HASH"] == LEAF
    assert conf["CELL_A"] == "jcz_CHAMP_deploy11008"
    assert conf["CELL_B"] == "jcz_ARB_B16J4_deploy11008"
    assert conf["TIEARB_B"] == "16" and conf["TIEARB_J"] == "4"
    assert conf["RUN_DIR"].endswith("measurement/jcz_tiearb_20260817")   # $VAR expanded


def test_workers_conf_fallback_is_flagged(tmp_path):
    conf, meta = adj.parse_workers_conf(tmp_path / "nope.conf")
    assert meta["parsed"] is False and "error" in meta
    assert conf["CHAMP_LEAF_HASH"] == LEAF        # the documented literal


def test_branch_order_puts_U_UNREADABLE_first():
    gates = {g: {"PASS": True} for g in adj.ALL_GATES}
    assert adj.decide_branch(gates, 5.0, 9.0)["branch"] == "J-CONFIRMED"
    bad = dict(gates, **{"G-BAND": {"PASS": False}})
    got = adj.decide_branch(bad, 5.0, 9.0)
    assert got["branch"] == "U-UNREADABLE" and got["failed_preconditions"] == ["G-BAND"]


def test_no_branch_matched_is_explicit_not_silent():
    gates = {g: {"PASS": True} for g in adj.ALL_GATES}
    got = adj.decide_branch(gates, None, float("nan"))
    assert got["branch"] == "U-UNREADABLE"
    assert got["no_branch_matched"] is True
    assert "no_branch_matched" in got or got["failed_preconditions"] == ["NO-BRANCH"]


def test_z_witness_disagreement_voids():
    ok, realized = adj.gate_witness({"D": 1.0, "se_D": 0.5, "z_D": 2.0, "n_common": 10},
                                    {"D": 1.0, "se_D": 0.5, "z_D": 2.5, "n_common": 10})
    assert ok is False
    assert realized["fields"]["z_D"]["agree"] is False
    ok2, _ = adj.gate_witness({"D": 1.0, "se_D": 0.5, "z_D": 2.0, "n_common": 10},
                              {"D": 1.0, "se_D": 0.5, "z_D": 2.0 + 1e-15,
                               "n_common": 10})
    assert ok2 is True
