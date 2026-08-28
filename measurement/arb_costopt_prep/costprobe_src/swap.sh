cd /home/doctor/costprobe || exit 1
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_NET_OFFLINE=true
rm -f out/DONE_SWAP
{
  echo "=== build ==="
  cargo build --release --bin swap 2>&1 | tail -25
  echo "=== census ==="; uptime; ps -eo pid,etime,%cpu,args --sort=-%cpu | head -4
  echo "=== run ==="
  ./target/release/swap 6 6,22,40,60,86,100 3 > out/swap.json 2>out/swap.err
  echo "rc=$?"; cat out/swap.err
  echo "=== census after ==="; uptime
} > out/swap.log 2>&1
touch out/DONE_SWAP
