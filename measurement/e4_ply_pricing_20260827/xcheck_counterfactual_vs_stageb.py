"""Cross-check my counterfactual against Stage B's independently-computed one.

`ev_loss.grade_archive` re-ran the SAME production champion at EVERY ply of these
same games on 2026-08-25 and recorded `agent_action` next to `action_played`. If
my `counterfactual_action` is a real search result it must reproduce those, and the
OWNER-seat agreement rate must be well below 1.0 (a champion that agreed with the
human everywhere would contradict the whole corpus).
"""
import json, glob, collections
G = "/home/doctor/projects/carcassone/measurement/e4_exploit_grading_20260825/graded/fixed_v1/"

by_seat = collections.Counter()
tot = collections.Counter()
per_game = {}
for f in sorted(glob.glob(G + "EV_LOSS_*.json")):
    d = json.load(open(f))
    plies = d.get("plies") or d.get("ply_records") or []
    if not plies:
        print("no ply array in", f, "keys:", list(d)[:20]); break
    stem = f.split("EV_LOSS_")[-1].replace(".json", ".json")
    per_game[stem] = {p["ply"]: p for p in plies}
    for p in plies:
        if p.get("forced"):
            continue
        s = p["actor"]
        tot[s] += 1
        if p.get("agent_action") == p.get("action_played"):
            by_seat[s] += 1

for s in (0, 1):
    n = tot[s]
    print(f"seat {s} ({'OWNER' if s == 0 else 'champion'}): "
          f"agent_action == action_played on {by_seat[s]}/{n} unforced plies "
          f"= {by_seat[s]/n:.3f}" if n else f"seat {s}: none")

# the exact plies my smoke touched
probe = [("1786045035_338139.json", 136), ("1786417055_68387.json", 136),
         ("1786417055_68387.json", 138), ("1786417055_68387.json", 140),
         ("1786591802_1104719504.json", 136), ("1786904828_407067.json", 136),
         ("1786904828_407067.json", 84), ("1786454767_166575.json", 106),
         ("1786337185_638286.json", 54), ("1786511848_634689.json", 34)]
print("\n-- Stage B's own record at the 10 smoke plies --")
for stem, ply in probe:
    rec = per_game.get(stem, {}).get(ply)
    if rec is None:
        print(f"  {stem} ply {ply}: NOT IN STAGE B RECORD")
        continue
    print(f"  {stem} ply {ply}: actor={rec['actor']} played={rec['action_played']} "
          f"stageB_agent={rec.get('agent_action')} "
          f"agree={rec.get('agent_action') == rec['action_played']} "
          f"forced={rec.get('forced')} exact={rec.get('exact')}")
