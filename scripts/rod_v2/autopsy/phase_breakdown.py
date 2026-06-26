#!/usr/bin/env python3
"""Per-phase breakdown of the Stage A-lite disagreement lean (reads saved rows.json,
NO recompute). Mirrors the v2.8 autopsy band-split: is the (non)movement uniform, or
endgame-localized? Appends a section to POLICY_ROOT_AUDIT.md."""
import json, math, sys
from pathlib import Path
from collections import defaultdict

OUT = Path("/home/doctor/projects/carcassone/measurement/rod_v2_flywheel/autopsy")
rows = json.load(open(OUT / "stage_a_lite_rows.json"))
valid = [r for r in rows if "_error" not in r
         and r.get("h3200_choice") is not None and r.get("h6400_choice") is not None]

PHASE_ORDER = ["opening", "early_mid", "mid", "late_mid", "pre_endgame", "endgame"]
by_phase = defaultdict(list)
for r in valid:
    by_phase[r.get("phase", "?")].append(r)

NETS = ["rod1", "iter04", "iter06"]
lines = ["\n## Per-phase disagreement lean (prior; lean = P(h6400) − P(h3200))\n"]
lines.append("| phase | n_dis | rod1 | iter04 | iter06 | rod1 Pneither | iter06 Pneither |")
lines.append("|---|--:|--:|--:|--:|--:|--:|")

def lean(sub, net):
    if not sub:
        return float("nan"), float("nan")
    p6 = sum(1 for r in sub if r.get(net + "_prior") == r["h6400_choice"]) / len(sub)
    p3 = sum(1 for r in sub if r.get(net + "_prior") == r["h3200_choice"]) / len(sub)
    pn = sum(1 for r in sub if r.get(net + "_prior") not in (r["h6400_choice"], r["h3200_choice"])) / len(sub)
    return p6 - p3, pn

phases_present = [p for p in PHASE_ORDER if p in by_phase] + \
                 [p for p in by_phase if p not in PHASE_ORDER]
for ph in phases_present:
    sub = [r for r in by_phase[ph] if r["h3200_choice"] != r["h6400_choice"]]
    if not sub:
        continue
    l_r1, pn_r1 = lean(sub, "rod1")
    l_04, _ = lean(sub, "iter04")
    l_06, pn_06 = lean(sub, "iter06")
    lines.append(f"| {ph} | {len(sub)} | {l_r1:+.3f} | {l_04:+.3f} | {l_06:+.3f} | {pn_r1:.3f} | {pn_06:.3f} |")

# also: agreement with EACH ruler by phase (are nets shallow-aligned and is it phase-dependent?)
lines.append("\n## Per-phase top-1 prior agreement with each ruler (all positions, not just disagreements)\n")
lines.append("| phase | n | rod1≡h3200 | rod1≡h6400 | iter06≡h3200 | iter06≡h6400 |")
lines.append("|---|--:|--:|--:|--:|--:|")
def agree(sub, net, ruler):
    return sum(1 for r in sub if r.get(net + "_prior") == r[ruler + "_choice"]) / len(sub) if sub else float("nan")
for ph in phases_present:
    sub = by_phase[ph]
    if not sub:
        continue
    lines.append(f"| {ph} | {len(sub)} | {agree(sub,'rod1','h3200'):.3f} | {agree(sub,'rod1','h6400'):.3f} "
                 f"| {agree(sub,'iter06','h3200'):.3f} | {agree(sub,'iter06','h6400'):.3f} |")

txt = "\n".join(lines) + "\n"
print(txt)
with open(OUT / "POLICY_ROOT_AUDIT.md", "a") as fh:
    fh.write(txt)
print(f"[phase-breakdown] appended to {OUT/'POLICY_ROOT_AUDIT.md'}")
