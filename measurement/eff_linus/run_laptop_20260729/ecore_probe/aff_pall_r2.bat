@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONHASHSEED=0"
set "PYTHONDONTWRITEBYTECODE=1"
set "CARCASSONNE_USE_FLAT_LEAF=1"
set "CARCASSONNE_USE_CY_LEAF=0"
set "CARCASSONNE_USE_CY_REPR=0"
cd /d C:\carc-bench-eff_linus\m5_bench_20260728
start "" /affinity 0xFFFF /wait /b "C:\Users\Doctor\carc-win-bench\.venv\Scripts\python.exe" -u "C:\carc-bench-eff_linus\m5_bench_20260728\bench_champion.py" --bundle "C:\carc-bench-eff_linus\m5_bench_20260728\bundle" --budgets k4x172 --limit 12 --warmup 1 --tag "aff_pall_r2" --out "C:\carc-bench-eff_linus\aff_pall_r2.json"
exit /b %ERRORLEVEL%
