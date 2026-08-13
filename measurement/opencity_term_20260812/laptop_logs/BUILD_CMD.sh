#!/usr/bin/env bash
set -euo pipefail
cd /home/doctor/projects/carcassone
OUT=/home/doctor/projects/carcassone/measurement/opencity_term_20260812/laptop_logs
export CARGO_HOME=/home/doctor/.cargo
export RUSTUP_HOME=/home/doctor/.rustup
export PATH="$CARGO_HOME/bin:$PATH"

if ! command -v cargo >/dev/null 2>&1; then
  echo "=== installing rust toolchain (minimal profile) ==="
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --profile minimal --default-toolchain stable --no-modify-path
fi
cargo --version
rustc --version

if ! /home/doctor/projects/carcassone/.venv/bin/maturin --version >/dev/null 2>&1; then
  echo "=== installing maturin into the venv ==="
  /home/doctor/projects/carcassone/.venv/bin/pip install --no-input maturin
fi
/home/doctor/projects/carcassone/.venv/bin/maturin --version

echo "=== maturin build --release ==="
rm -rf /home/doctor/carc_wheels
mkdir -p /home/doctor/carc_wheels
nice -n 19 /home/doctor/projects/carcassone/.venv/bin/maturin build --release \
  -m /home/doctor/projects/carcassone/rust/carc/carc-py/Cargo.toml \
  -i /home/doctor/projects/carcassone/.venv/bin/python \
  --out /home/doctor/carc_wheels -j 6

WHL=$(ls /home/doctor/carc_wheels/*.whl | head -1)
echo "=== built wheel: $WHL ==="
sha256sum "$WHL" | tee "$OUT/WHEEL_SHA256.txt"

/home/doctor/projects/carcassone/.venv/bin/pip install --no-input --force-reinstall "$WHL"

echo "=== verify import + opencity knobs ==="
/home/doctor/projects/carcassone/.venv/bin/python - <<'PY'
import carc_rs, os, hashlib
print("carc_rs:", carc_rs.__file__)
d = os.path.dirname(carc_rs.__file__)
for f in sorted(os.listdir(d)):
    if f.endswith(".so"):
        p = os.path.join(d, f)
        print("so:", p, "sha256", hashlib.sha256(open(p,"rb").read()).hexdigest())
cfg = carc_rs.LeafConfigRs([(1,0.5)],8.,8.,
        opencity_dose=1.0, opencity_size_min=4.0, opencity_edge_min=2,
        opencity_symmetric=True)
print("OPENCITY KWARGS ACCEPTED")
st = carc_rs.MirrorState.from_seed("880011")
terms = st.leaf_terms(0, carc_rs.LeafConfigRs([(1,0.5)],8.,8.))
assert "opencity_term" in terms, sorted(terms)
print("leaf_terms carries opencity_term; keys:", sorted(terms))
PY

echo "=== pytest tests/test_opencity_term.py ==="
nice -n 19 /home/doctor/projects/carcassone/.venv/bin/python -m pytest \
  tests/test_opencity_term.py -q -rs 2>&1 | tail -30

echo "=== pytest neighbours (denial + frozen substrates) ==="
nice -n 19 /home/doctor/projects/carcassone/.venv/bin/python -m pytest \
  tests/test_denial_term.py tests/test_frozen_substrates.py -q 2>&1 | tail -10
