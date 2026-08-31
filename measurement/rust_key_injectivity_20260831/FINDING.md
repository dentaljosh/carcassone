# Does the rust search's node key collide DISTINCT states on 180°-symmetric tile rotations?

**Status: ANSWERED 2026-08-31. Verdict = COLLISION-REACHABLE, SAME-POSITION — no
production correctness defect found.** Read-only audit; **no production code was
changed**, no banked number edited, no governance row flipped, no claim id.

Docket item from the 2026-08-31 MirrorDesync finding, following
[`measurement/legal_cache_key_20260830/FINDING.md`](../legal_cache_key_20260830/FINDING.md)
(the python `_legal_cache` key fix) and
[`measurement/omd2_chain_values_20260830/`](../omd2_chain_values_20260830/) (OM-D2).

---

## 0. Answer in four lines

1. **The rust key IS non-injective over rotation, exactly like python's.**
   `carc_core::repr_key::string_representation` writes each placed tile as
   `(row, col, description, rot_sig_repr)` and `rot_sig_repr` is
   `((4 outer edge types), shield, chapel, flowers)` — **the rotation index is
   not in the key.** 9 base tiles have rotations that tie on it.
2. **The collision IS reachable inside one deployed search tree** — proved, not
   argued: the two banked OM-D2 tile actions descend to the *same node digest*
   in one `search_single`, and a 30-root whole-tree audit found **725 merged
   nodes / 972 merged prefix-pairs**.
3. **But every colliding pair is the SAME POSITION.** The rotations that tie on
   the key are physically identical placements; what differs is the *label* of
   the farmer corner the engine offers. Measured: `geometry_identical` on
   **13/13** colliding rotation classes × both R9 states; 0 failures on
   ~21.6k sibling pairs and 972 in-tree pairs; 1,440 full greedy playouts to
   terminal end on identical margins.
4. So `Tree::intern` folding them is a **correct transposition merge**, not a
   state confusion. The one rust structure that *is* wrong under the collision —
   `tier1::LegalMaskCache` — is a deliberate bug-reproduction and the **deployed
   arbiter passes it `None`**.

⚠️ **Correction to the earlier audit's wording.** `legal_cache_key_20260830`
§3 says the rust `LegalMaskCache` "carries its own key in rust and never reads
this env var". True — and it must not be read as *injective*. It carries the
**same legacy, non-injective key**, on purpose
(`tier1.rs:279`: *"Collisions are REPRODUCED, not repaired"*). Task item 2's
premise ("verify that key IS injective where python's wasn't") resolves **NO**.

---

## 1. The key, and why it loses rotation

| what | where |
|---|---|
| the key writer | `rust/carc/carc-core/src/repr_key.rs:61-152` |
| the per-tile component | `repr_key.rs:81` — `out.push_str(&tile.rot_sig_repr)` |
| what `rot_sig_repr` contains | `rust/carc/carc-core/src/tiles/mod.rs:422-431` — `((edge(Top), edge(Right), edge(Bottom), edge(Left)), shield, chapel, flowers)` |
| the accessor | `rust/carc/carc-core/src/game.rs:428` — `Game::string_repr` |

`state.get_tile` returns a rotation-bearing tile id, but only `description` and
`rot_sig_repr` are emitted. Two rotations whose four outer edges tie are
therefore **byte-identical in the key**, while the tile's farm slots rotate.
This is byte-exact to the python `string_representation` (a G1 gate), so the
python defect is inherited verbatim.

### Measured tile-level census — [`probe1_registry.py`](probe1_registry.py) → [`REGISTRY_COLLISIONS.json`](REGISTRY_COLLISIONS.json)

13 colliding rotation classes over 9 base tiles (identical under R9 off and on):

| tile | colliding rotations | physical geometry identical? | offered farmer corner identical? |
|---|---|---|---|
| `chapel` | 0,1,2,3 | ✅ | ❌ TL / TR / BR / BL |
| `crossroads` | 0,1,2,3 | ✅ | ✅ |
| `full_city_with_shield` | 0,1,2,3 | ✅ | ✅ (no farm slot) |
| `city_left_right` | 0,2 and 1,3 | ✅ | ❌ |
| `city_narrow` | 0,2 and 1,3 | ✅ | ❌ |
| `city_narrow_shield` | 0,2 and 1,3 | ✅ | ❌ |
| `city_top_bottom_flowers` | 0,2 and 1,3 | ✅ | ❌ |
| `straight_road` | 0,2 and 1,3 | ✅ | ❌ |
| `straight_road_flowers` | 0,2 and 1,3 | ✅ | ❌ |

**`classes_with_DIFFERENT_physical_geometry: 0`.** Region-for-region the farm
decomposition — `tile_connections`, `city_sides`, and the full
`farmer_positions` **set** — is equal across every colliding rotation. What
moves is `farmer_positions[0]`, and `__possible_farmer_position` emits only that
first element, so the engine offers a **different corner of the same field**.
That is the whole observable, and it is the exact thing the python memo bug rode.

---

## 2. Every consumer of the key, and whether two DIFFERENT states can reach it

`carc-core` has exactly **three** structures keyed on the repr string, plus two
sha256 transposition tables that hash it. That is the complete set
(`grep 'HashMap<String\|HashMap<Rc<str>\|BTreeMap<String'` over the crate).

| # | consumer | file:line | keyed value | collision reachable? | consequence |
|---|---|---|---|---|---|
| 1 | **`Tree::index`** — MCTS node interning | `search/mod.rs:477`, `intern` 497-506, `create_or_get` 1010-1018 | `NodeId` | **YES, measured** | merges two rotations onto one node — but they are the same position ⇒ a correct transposition |
| 2 | **`tier1::LegalMaskCache`** | `tier1.rs:284-288`, `legal_actions_checked` 716-733 (key at 722) | **`Vec<i32>` — an ACTION LIST** | YES *by design* | **serves the other rotation's farmer ids.** Deliberate: reproduces the BURNED Stage-1b bank (`tier1.rs:42-77`). **Not on the deployed path** |
| 3 | **`tiearb::build_arms`** dedup | `tiearb.rs:405-424` (key at 413), champ-pick key at 470 | arm groups | YES | collapses two rotations into one arm — **correct**, that is what the transposition dedup is for |
| 4 | endgame solver TT | `endgame/mod.rs:254-278`, `tt` 202 / `tt_ab` 206 | `f64` / `(f64,u8)` — **values only** | YES | same-position ⇒ correct value; children are re-enumerated live from `g.legal_actions()`, never TT-cached |
| 5 | fair (marginalized) solver TT | `fair/solver.rs:328-349`, `tt` / `tt_win` 277-281 | `f64` / `(f64,f64)` | YES | same |
| 6 | trace / window-diag node identity | `search/trace.rs:20`, `search/window_diag.rs:95` | diagnostic only | YES | diagnostic aliasing only |

Two structural facts that bound the collision class:

* **Fresh tree per determinization.** `fair::search_worlds` builds
  `search::Searcher::new(cfg)` per world (`fair/mod.rs:851`), so a deployed
  PIMC decision never carries a tree between worlds and never mixes decks.
* **Within one tree the deck is determined.** The key omits deck *contents*, but
  a determinized tree has a fixed draw sequence, so `(board, deck_len)` fixes
  which tiles were drawn and which discarded. The solver TTs additionally hash
  the deck descriptions explicitly. **Rotation is therefore the only live
  collision class**, and the tree audit in §4 confirms that empirically.

### The safety net that already exists

`SearchSession::reroot_to` (`search/session.rs:296-318`) refuses to reuse a
retained node whose `valid_actions` differ from the freshly computed legal mask,
returning `Reroot::Collide` and wiping the tree (`session.rs:315`). Its own
doc-comment names this case: *"Wrong-rotation transposition sibling (same
`string_representation`, a different legal action set)"* (`session.rs:81`). So
the one path that could serve a stale action list across a real-game advance
already detects and refuses it. (`PersistentSearcher` is used by
`oracle_score_pilot` / the rustport gates, not by the fair-agent champion.)

### Why the merge cannot serve a wrong action list *inside* a search

`simulate` (`search/mod.rs:1119-1171`) advances the true state `g` by the
selected action, then `create_or_get(&g)` interns. On a collision `intern`
returns the **existing** node and the fresh node is dropped, so the child holds
the *canonical* rotation's `valid_actions`. Three things then keep that
consistent:

* the descent `break`s immediately after linking a newly-reached child, so no
  action from the canon's list is ever applied to the alias's state
  (`search/mod.rs:1146-1153`);
* `link_child` marks the second action as an alias
  (`search/mod.rs:1082-1113`), and `select_child_puct` **skips aliased actions**
  (`search/mod.rs:1033-1035`), so the alias is never descended again;
* `root_stats` / `deduped_children` / `final_action`
  (`search/mod.rs:1278-1345`) dedup by `NodeId` and keep the **lowest** action,
  so exactly one member of an alias group can ever be chosen, deterministically.

---

## 3. Witness — [`probe2_witness.py`](probe2_witness.py) → [`WITNESS_walled.json`](WITNESS_walled.json) / [`WITNESS_fixed_v1.json`](WITNESS_fixed_v1.json)

The banked OM-D2 pair `(deck_seed 28000000011, ply 24, actions 949 / 951)`,
replayed through `carc_rs` under the PRODUCTION champion search config
(`rust_agent.search_config_rs(production_prior_cfg(...))`, sims reduced to 256).
Both rules profiles agree exactly.

| gate | result |
|---|---|
| **K1** rust `string_repr` collides | ✅ `true` (key len 1418) |
| **K2** honest legal actions differ | ✅ `a\b = [2507, 2509]`, `b\a = [2506, 2508]` |
| **K3** same position | placed tiles differ ONLY at `(3,13)`: `straight_road` rot **1** vs rot **3**; `leaf_value` −12 = −12; successor leaf multiset identical |
| **K4** reachable in ONE deployed tree | ✅ both root actions descend to node digest `2f6c95caaca4030e` — **SAME NODE** |
| **K5** blast radius | `root_children[949] == root_children[951] == (N=20, W bits 13846793761073668187)`; `949 ∈ deduped`, `951 ∉ deduped`; 22 root children → **11 distinct nodes** |

The A/B the docket asked for ("does it move any deployed search's chosen
action?") is answered structurally *and* by K3/K5: only the canonical member can
be chosen, and the members are the same position, so the choice is
label-arbitrary, not value-arbitrary.

---

## 4. Scale — is it rare, and does it ever separate two states?

### 4a. Sibling census over banked champion games — [`probe3_sweep.py`](probe3_sweep.py) → [`SWEEP_walled.json`](SWEEP_walled.json) / [`SWEEP_fixed_v1.json`](SWEEP_fixed_v1.json)

60 games, 4,320 TILES plies, **120,823 legal tile actions**. Identical under both
rules profiles (the collision is a tile-registry property; R9 moves farm scoring,
not the edge signature).

| | |
|---|---|
| key-collision groups | **15,395** (12,269 of size 2, 3,126 of size 4) |
| tile actions inside a collision group | **37,042 = 30.66%** |
| colliding tiles | `chapel` 7,662 · `straight_road` 6,680 · `city_left_right` 1,577 · `city_narrow_shield` 1,570 · `crossroads` 1,077 · `straight_road_flowers` 899 · `city_narrow` 806 · `city_top_bottom_flowers` 737 · `full_city_with_shield` 639 |

**This is not an exotic corner. Roughly a third of every tile ply's branching
sits in a key-collision group.**

Same-position gates over every pair in every group (~21.6k pairs):

| gate | failures |
|---|---|
| **S1** diff is a rotation label on ONE tile | **0** |
| **S2** `leaf_value` bit-identical | **0** |
| **S4** full `tier1-greedy` playout to TERMINAL (honest mask, same world + playout seed) ends on the same `(margin, plies)` | **0** / 1,440 comparisons (3,414 playouts) |

S3 (informational): 9,096 pairs had **no** observable action-list difference at
all — `crossroads`, `full_city_with_shield`, and any pair where the farmer slot
was vetoed anyway.

### 4b. Whole-tree audit — [`probe5_treeaudit.py`](probe5_treeaudit.py) → [`TREE_AUDIT_fixed_v1.json`](TREE_AUDIT_fixed_v1.json)

§4a only covers *siblings*. This closes the cross-depth gap by auditing real
trees: 30 roots × 400 sims, trace every `sim` record, and for every node digest
reached by ≥2 distinct action prefixes, replay both prefixes and compare.

| | |
|---|---|
| nodes seen | 11,028 |
| **nodes reached by ≥2 distinct prefixes** | **725** (972 prefix pairs) |
| pairs that were NOT rotation-label-only | **0** |
| pairs with mismatched scores / meeples / deck_len / phase / mover | **0** |
| pairs with mismatched `leaf_value` at either seat | **0** |

**Verdict line from the artifact:** *"every multi-prefix node in every audited
tree is a SAME-POSITION merge."*

### 4c. The rust `LegalMaskCache`, priced

Same probe, re-running each playout with `legal_mask_cache=True`
(`carc_rs.tier1_playout_trace`): **0 / 3,414 playouts moved.**

⚠️ **Do not read that as a refutation of the banked 0.371%.** The exposure shape
differs: `tier1_playout_trace` builds ONE memo per playout, whereas the banked
Stage-1b defect came from ONE `Game` whose memo spanned the record's root query
*and* all `2 × m` playouts (`tier1.rs:44-48`). This measures the deployed-shaped
exposure, and the deployed arbiter does not even take it — see §5.

---

## 5. Is the buggy consumer on a deployed path? No.

`tiearb` — the tiearb2 Stage-2 arbiter that is live on this branch — passes
`cache = None` at **both** call sites: `tiearb.rs:563` (`arbitrate`) and
`tiearb.rs:912-919` (the refuter leg). The module says why
(`tiearb.rs:56-70`): the memo is *"a defect of the python REPLAY HARNESS, not
part of the `tier1-greedy` policy"*, and enabling it would additionally create an
**arm-order side channel** (arm *k* seeing arms `< k` through a shared memo)
with the incumbent privileged at arm 0.

`legal_mask_cache=true` is the default only on `carc_rs.tier1_leg`
(`carc-py/src/lib.rs:1087-1123`) — the Stage-1b **bank-reproduction judge**,
which must keep reproducing the burned corpus bit-for-bit. That is measurement
tooling, not play.

---

## 6. ⚠️ Load-bearing warning for the proposed joint py+rust key change

The python fix is currently flag-gated pending "a joint py+rust key change".
**Porting the python signature to the rust key is not a free correctness win —
it would REMOVE a correct transposition merge.**

Measured at real roots ([`probe4_fixcost.py`](probe4_fixcost.py) →
[`FIXCOST_fixed_v1.json`](FIXCOST_fixed_v1.json), 24 roots, production config,
sims=256):

| | |
|---|---|
| legal tile actions | 686 |
| **distinct successor afterstates** | **569** |
| **redundant duplicates the key currently folds** | **17.06%** |
| visited root children | 603 → 486 distinct nodes = **19.4% aliases** |

If the two rotations get different keys, `Tree::intern` stops merging them,
`link_child`'s alias path never fires, and PUCT **splits visits and prior mass
across physically identical siblings** — on ~17% of root branching, growing with
`chapel` / `straight_road` density. The same change would un-dedup
`tiearb::build_arms`, so a CRN arm set could spend its `J` budget on duplicate
positions and `all_transposition` would stop firing.

The defensible shape of a fix, if one is wanted, is therefore **not** "append
the farm-slot signature to the rust key". It is either:

* **(A) leave the rust key alone** — it is a *canonicalising* key over an
  equivalence class that is genuinely an equivalence class, and the only wrong
  consumer (`LegalMaskCache`) is already `None` on the deployed path; or
* **(B) fix the offered corner instead** — make `farmer_positions[0]` rotation
  stable so the *action label* stops moving, which removes the observable
  without touching the merge. That is an engine-semantics change and owes a
  full rules-epoch declaration.

**Neither is proposed here.** This audit changes nothing.

---

## 7. Verdict

**COLLISION-REACHABLE / SAME-POSITION.** Split by consumer:

| consumer | verdict |
|---|---|
| deployed MCTS `Tree::intern` | **COLLISION-REACHABLE** (witness + 725 in-tree merges) — and **benign**: every merge is a same-position transposition. No deployed search's chosen action is at risk; only the canonical (lowest-id) member is selectable, and the members are the same board. |
| `SearchSession::reroot_to` | reachable, **already guarded** (`Reroot::Collide`, `session.rs:315`) |
| `tiearb::build_arms` | reachable, **correct** (that is what the dedup is for) |
| endgame / fair solver TTs | reachable, **correct** (value-only TT over an equivalence class) |
| `tier1::LegalMaskCache` | **NON-INJECTIVE, serves the wrong rotation's action list — by design**, and **`None` on the deployed arbiter path**. Measurement-only. |

**No production correctness change is owed.** The open item this leaves is
governance, not code: §6's warning must be attached to the parked
"joint py+rust key change" row before anyone acts on it.

## 8. What was deliberately NOT done

* No production code changed, no flag added, no default moved.
* No banked artifact edited, no `results.csv` row, no claim id, no
  `governance/PRODUCTION.yaml` field.
* No strength game played; no A/B of a *modified* key (that would require the
  production-code change this audit is forbidden to make — §6 prices it
  structurally instead).
* The two `*_trace.jsonl` intermediates were deleted after analysis; re-running
  `probe2` / `probe5` regenerates them.

## 9. Reproduce

All probes are read-only, single-core, and run in seconds to a few minutes.
The local box was hosting a live `eval_fair_puct` SMOKE at the time, so
everything was run `nice -n 19`, single-threaded.

```bash
V=.venv/bin/python
$V measurement/rust_key_injectivity_20260831/probe1_registry.py
$V measurement/rust_key_injectivity_20260831/probe2_witness.py  --profile fixed_v1 --sims 256
$V measurement/rust_key_injectivity_20260831/probe3_sweep.py    --profile fixed_v1 --games 60 --groups-per-game 8 --worlds 3
$V measurement/rust_key_injectivity_20260831/probe4_fixcost.py  --profile fixed_v1 --roots 24 --sims 256
$V measurement/rust_key_injectivity_20260831/probe5_treeaudit.py --profile fixed_v1 --roots 30 --sims 400
```
