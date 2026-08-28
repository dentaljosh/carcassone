cd /home/doctor/costprobe || exit 1
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_NET_OFFLINE=true
rm -f out/DONE_VARIANT
{
  echo "=== build ==="
  cargo build --release --bin variant 2>&1 | tail -20
  echo "=== census ==="; uptime
  echo "=== run ==="
  ./target/release/variant 5 10,25,40,55,70,85 2 > out/variant.json 2>out/variant.err
  echo "rc=$?"; cat out/variant.err
  echo "=== census after ==="; uptime
} > out/variant.log 2>&1
touch out/DONE_VARIANT
