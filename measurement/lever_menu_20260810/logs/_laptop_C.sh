cd /home/doctor/projects/carcassone || exit 1
mkdir -p /mnt/carc-shared/capscurve_resweep
setsid nohup env CC_OUT_ROOT=/mnt/carc-shared/capscurve_resweep nice -n 19 bash \
  scripts/classical_search/capscurve_resweep_launcher.sh 22 laptop \
    --cells "cap5 cap12 curve150 curve175" --n 800 --band 120000000000 \
    --out-sub-prefix cc800_ --exp-suffix _n800_b120e9 \
  > /mnt/carc-shared/capscurve_resweep/laptop_menu_C.log 2>&1 < /dev/null & disown
echo "laptop C launched pid $!"
