# champ_env.sh — the production champion leaf env block for the distill-flywheel.
# COPIED VERBATIM from governance/PRODUCTION.yaml (env_knobs + leaf_config) as of
# 2026-07-16 (champion puct_priors_v29_bmild_cap8, fair_deploy k4x688). Sourced by
# EVERY gen/train invocation on BOTH boxes (env is read at import time; spawned
# workers re-read it), so the fair champion distils the ACTUAL production leaf.
#
# ⚠️ CRITICAL — curve125, NOT curve100: the fair scripts' hardcoded _CANON_ENV
# defaults to the WRONG curve100 (-8,-4,-1,0,2,3,4,5). This block sets the
# production curve125 (x1.25, CL-051). Under this env the resolved leaf CONFIG is:
#   v29_meeple_curve = (-10.0,-5.0,-1.25,0.0,2.5,3.75,5.0,6.25)   # curve125
#   bonus_cap = 8.0 · opp_bonus_cap = 8.0 · closure_p = {1:0.5,2:0.2,3:0.05}
# and the runtime frozen-config-hash is 6dfffd57051690f2. (The PRODUCTION.yaml
# fingerprint 158f17ff is STALE — computed against an older LeafConfig dataclass
# shape; the LeafConfig gained default-off v28_*/v29_* fields since. The leaf
# VALUES above are the champion leaf and are what matter — verify VALUES, not the
# hash string. CARCASSONNE_V25_MEEPLE_K is deliberately NOT exported: it is inert
# under a non-null curve, so it does not change the leaf value.)

# --- leaf config (from PRODUCTION.yaml leaf_config) ---
export CARCASSONNE_V29_MEEPLE_CURVE="-10,-5,-1.25,0,2.5,3.75,5,6.25"
export CARCASSONNE_V25_CAP=8
export CARCASSONNE_V25_OPP_CAP=8

# --- leaf engine (from PRODUCTION.yaml env_knobs) ---
export CARCASSONNE_USE_FLAT_LEAF=1
export CARCASSONNE_USE_CY_LEAF=1
export CARCASSONNE_USE_CY_REPR=1

# --- net-free CPU champ gen: hide CUDA, single-thread BLAS ---
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
