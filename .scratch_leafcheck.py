import os, sys
CANON = {"CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
         "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
         "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
         "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
         "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
         "CARCASSONNE_USE_CY_REPR": "1", "CUDA_VISIBLE_DEVICES": "",
         "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
         "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
         "VECLIB_MAXIMUM_THREADS": "1"}
for k, v in CANON.items():
    os.environ.setdefault(k, v)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts", "classical_search"))
from c5_leaf_override import _leaf_hash, _load_cand_leaf_cfg, DEFAULT_CONFIG  # noqa: E402
import carcassonne_ai  # noqa: E402
print("carcassonne_ai.__file__ =", carcassonne_ai.__file__)
print("DEFAULT_CONFIG (rung ruler) leaf_hash =", _leaf_hash(DEFAULT_CONFIG))
cfg = _load_cand_leaf_cfg('{"v29_meeple_curve": [-10,-5,-1.25,0,2.5,3.75,5,6.25]}')
print("curve125 override           leaf_hash =", _leaf_hash(cfg))
print("R9 env observed:", os.environ.get("CARCASSONNE_FIX_R9"))
