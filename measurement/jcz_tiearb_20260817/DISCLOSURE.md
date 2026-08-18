# §0.J — DISCLOSURE: the first adjudication, the analyser fixes, and the VOID

> Written **before** the re-adjudication, by a session that has **never read D, `z_D`, elo, any
> margin, any win rate, or any cell summary**. Every disposition below rests on outcome-independent
> facts. This is READ_RULE §0.F.3, and the commit order is the proof.
>
> **⛔ BOTTOM LINE: `G-TOOL` conjunct 2 fails as committed, and I am NOT bending it. The run is
> `U-UNREADABLE` and must be re-run.** Three *other* gate failures were analyser infidelities and
> are fixed; they are reported here so the record separates instrument defects from the one real
> governance failure.

---

## 1. What the first adjudication reported

`branch: U-UNREADABLE`, `failed_preconditions: ["G-ARB", "G-JCZ", "G-TOOL"]`.

Of those four failing conjuncts, **three were the analyser failing to implement the committed
text, and one is real.**

---

## 2. FIXED — three analyser infidelities (no gate relaxed)

### 2.1 `G-JCZ` — a FIFTH unsatisfiable-by-construction conjunct, and it is MY defect

The analyser required `jcz_git_rev` to be stamped on **every record**. Measured distribution,
identical in both cells:

| host | `jcz_git_rev` | records |
|---|---|---|
| Doctor (215 decks × 2) | `29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a` | **430** |
| laptop-wsl (185 decks × 2) | `null` | **370** |

**Zero records carry a *different* rev.** The counts match the 215/185 split exactly.

**Root cause, and it traces to my own design decision.** `scripts/jcz_match/match.py:352` stamps
`_git_rev(jcz_repo)`, and `_git_rev` returns `None` on any subprocess failure. DESIGN §0.1 staged
the **jar + shim classes** to the laptop via the share and deliberately did **not** clone the JCZ
repository — recorded at the time as *stronger* provenance, because copying gives byte-identical
bytecode instead of a second unverified build. The consequence, unforeseen then and verified now:

```
$ ssh laptop-wsl 'git -C /home/doctor/jcz_spike/JCloisterZone rev-parse HEAD'
fatal: not a git repository (or any of the parent directories): .git
```

So **every laptop record will stamp `null` forever, on every healthy run of this two-box
configuration.** §3.1's structural test — *"would this gate fail on EVERY healthy run of this
launcher?"* — answers **YES**. That is precisely the §0.F.2 / §0.F.2b / §0.F.2c class.

**The committed text's own address is per-host**, not per-record: §3 requires the pinned artifacts
*"verified **ON EACH HOST**"* and voids on *"any difference in the pinned artifacts on any host"*.
Both hosts' `PREFLIGHT_<host>_ENV.json` carry `jcz_rev = 29a1561…` **and**
`jcz_jar_sha256 = 4dc5439dbf228b13` — and the **jar sha256 is the stronger witness**, since it
hashes the artifact that actually ran, whereas a git rev only names a checkout.

**AMENDED READING (implements the committed sentence; fail-closed preserved).** Records that
*disagree* VOID. A value *differing from the pin* VOIDS. *Absent from every record* VOIDS. Absent
from *some* records VOIDS **unless** the pinned value is present-and-equal on **every host that
played**, at the per-host ENV address the read-rule itself names — and it is **fail-closed** if any
played host has no ENV witness, or an absent or differing field. Coverage is reported per field.

⚠️ **Also a separate, genuine analyser bug in the same gate:** `ok` conjoined value-agreement with
full record coverage, so a byte-identical witness could read `ok:false` purely on coverage.

📌 **Parked for the re-run:** either clone the JCZ repo to the laptop, or have `match.py` fall back
to the jar sha256 when `_git_rev` returns `None`. The second is better — the jar is the artifact.

### 2.2 `G-ARB` — the analyser read the telemetry block, not the config

`record.champ_tiearb` is the **firing TELEMETRY** (`tile_plies`, `fires`, `pickchanges`, …). It
carries `mode`/`B`/`J` but has **no `enabled`, `salt`, or `eps`**, so those three resolved `null`.

The **resolved config** is stamped at `record.manifest.champion_manifest.cand_tiearb`:

```json
{"enabled": true, "B": 16, "J": 4, "mode": "argmax", "salt": "tiearb2-deploy-v1", "eps": 0.0}
```

— present on all 800 CELL B records, and exactly the funded rung. This is the **same class as
§0.F.2's `G-LEAF` fix**: the gate named `eval_fair_puct`'s spelling while this harness writes the
quantity elsewhere. Resolution order is now manifest top level → `config.*` →
`champion_manifest.cand_tiearb` → `record.champ_tiearb`, **reporting which address resolved**.
**Absent at every address still fails; present-but-different still fails; a conflict between
addresses fails.** CELL A's clause is untouched and already passed (no key, 800 records).

⚠️ Naming asymmetry, now commented in the analyser: the record's `champ_tiearb` (telemetry) and the
manifest's `cand_tiearb` (config) are **different objects, not two spellings of one**.

⚠️ Second defect found while testing: the resolver overwrote `resolved_at` on every *agreeing*
address, so it reported the **last** address rather than the first in the committed order. Fixed to
first-address-wins.

### 2.3 `G-TOOL` conjunct 1 — it failed on the comparison §0.F.2c FORBIDS

```
build_id_equal_across_hosts:  true
binary_sha_equal_across_hosts: false   <-- the conjunct failed on THIS
```

**§0.F.2c commits to never comparing `carc_rs_binary_sha` across hosts** — the `.so` is not
machine-reproducible, measured (Doctor `a4318fd59d9d8349` vs laptop `8ae0b98427debb2e` at the
*same* build id). Conjunct 1 now binds **only** on `carc_rs_build`, which is equal across hosts
(`carc_rs-0.1.0+a8b6cf87000d+rustc1.96.0`). The cross-host sha is still computed and reported,
explicitly flagged **non-binding**. Conjunct **1b** (within-host, across the two cells) **does**
bind on the sha and passes on both hosts.

⚠️ **One pre-existing test was rewritten deliberately**: it asserted that differing cross-host shas
*void* — i.e. it encoded the exact comparison §0.F.2c forbids. It now asserts the opposite. Tests
60 → **72 passed**, 0 failed.

---

## 3. NOT FIXED — `G-TOOL` conjunct 2 fails, and the READ_RULE cannot tolerate it

### 3.1 The facts

`our_git_rev` is stamped per record at record-write time. Measured:

| cell | distinct revs |
|---|---|
| `jcz_CHAMP_deploy11008` | `a8b6cf87` ×481 · `2eab07d5` ×310 · `0efdbefb` ×9 |
| `jcz_ARB_B16J4_deploy11008` | `2eab07d5` ×430 · `a8b6cf87` ×370 |

⇒ `consistent_across_records: false` in **both** cells, and `equal_across_cells: false`.

### 3.2 The coordinator's disclosure, carried verbatim

The two extra revs are the coordinator's commits during the run — `0efdbefb` (widening plans) and
`2eab07d5` (census tracking), both **docs/measurement only**. Verified:
`git log a8b6cf87..2eab07d5` is exactly those two commits, and
`git diff --name-only a8b6cf87..2eab07d5 -- rust/ src/ engine/ scripts/` is **EMPTY**. The wheel
and all imported code are unchanged across the whole run, and the workers had been live since
launch, so nothing was re-imported.

**They were made under a tolerance I stated, and I own that.** My words, verbatim, at launch:
*"docs/`measurement`/`android` commits remain tolerated as before"*, and in the band-claim commit
message: *"HEAD MUST NOT MOVE on any wheel-relevant path (`rust/ src/ engine/ scripts/`) or
G-TOOL's `<preflight>..<manifest>` range conjunct VOIDS the run."* That statement scoped the freeze
to conjunct **3**. It was wrong: **conjunct 2 is violated by *any* commit, wheel-relevant or not**,
because `our_git_rev` moves with HEAD regardless of what changed. The coordinator acted inside the
tolerance I published; the defective tolerance is mine.

### 3.3 Why it cannot be rescued — and why I am not amending it

**The science is almost certainly unaffected** — the empty wheel-relevant diff proves the code that
ran was identical. That is not the question. The question is what the committed text permits.

1. **Conjunct 2 as committed is explicit:** *"`our_git_rev` … is equal across CELL A and CELL B,
   **and consistent within each cell (no mixed-rev cell)**."* Both sub-clauses fail. The §3 VOIDS
   column independently enumerates **"mixed revs across cells"**, and `equal_across_cells` is
   `false` — so even the narrowest enumerated trigger fires.
2. **Conjunct 3 cannot rescue conjunct 2.** `grep -n "dispositive" READ_RULE.md DESIGN.md` returns
   **nothing**. No committed text makes an empty diff dispositive in the *passing* direction;
   conjunct 3 says only that EMPTY-or-degenerate passes **and non-empty VOIDS**. It is a conjunct,
   not an override. (The "DISPOSITIVE IN ONE DIRECTION" phrasing exists in *Stage 2's* readout, not
   in this run's read-rule — and even there it is one-directional.)
3. **It is NOT the unsatisfiable-by-construction class**, and this is the decisive difference from
   §2 above. §3.1's test — *"would this fail on EVERY healthy run?"* — answers **NO**. A run during
   which nobody commits satisfies conjunct 2 perfectly. It is a **satisfiable requirement that was
   violated by operator behaviour**, not a gate that could never pass. Every §0.F.2 fix was
   justified by *impossibility*; that justification is simply unavailable here.
4. **Amending it now would be a bar move made after the numbers exist.** The outcome statistics
   have been computed and another party has seen them. Rewriting a satisfiable gate in that
   context — at the request of the party whose commits tripped it — is exactly the failure mode
   §0.F.3 and §4's rider exist to prevent. Stage 2 paid for this lesson once.

**Determination: `G-TOOL` FAILS. Branch `U-UNREADABLE`. The cells are void and must be re-run.**
No strength statistic from this run may be quoted, cited, or entered in `results.csv` as a verdict.

---

## 4. What the re-run must change (no bar moves; these are operational)

1. **A TOTAL commit freeze** from band claim to the fourth DONE marker — *no* commits, not merely
   no wheel-relevant ones. This satisfies conjunct 2 as written and needs no amendment. It is the
   clean fix and it is available.
2. Give the laptop a real JCZ witness (clone the repo, or fall back to the jar sha256 in
   `match.py`) so §2.1's coverage gap does not recur.
3. A fresh band — `133000000000` is spent and retires from confirmatory use.

⚠️ Any amendment to conjunct 2 must be written by a session that has **not** seen this run's
statistics, and must be argued on the *proposition*, not on the cost of a re-run.
