pids=""
while IFS= read -r p; do
  [ -z "$p" ] && continue
  pids="$pids $(pgrep -f "$p" 2>/dev/null || true)"
done <<PATS
/home/doctor/projects/carcassone/.venv/bin/python
/home/doctor/projects/carcassone/rust/.*/target/release
PATS
echo "$pids" | tr " " "\n" | sed "/^$/d" | sort -u | wc -l
