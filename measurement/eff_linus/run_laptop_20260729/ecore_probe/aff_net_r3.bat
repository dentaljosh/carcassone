@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONHASHSEED=0"
set "PYTHONDONTWRITEBYTECODE=1"
set "CARCASSONNE_USE_FLAT_LEAF=1"
set "CARCASSONNE_USE_CY_LEAF=0"
set "CARCASSONNE_USE_CY_REPR=0"
set "PYTHONPATH=C:\carc-bench-eff_linus\stage\pysrc"
cd /d C:\carc-bench-eff_linus\stage
start "" /affinity 0xFFFF /wait /b "C:\Users\Doctor\carc-win-bench\.venv\Scripts\python.exe" -u "C:\carc-bench-eff_linus\stage\net_transport_bench.py" --ckpt "C:\carc-bench-eff_linus\ckpt\iter_03.pt" --rows cpu_1t --calls 2000 --warmup 200 --out "C:\carc-bench-eff_linus\aff_net_cpu1t_r3.json"
exit /b %ERRORLEVEL%
