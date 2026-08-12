cd /home/doctor/projects/carcassone || exit 1
mkdir -p /mnt/carc-shared/night_chain_20260812/s1_simsplit
setsid nohup env MENU_OUT_ROOT=/mnt/carc-shared/night_chain_20260812 nice -n 19 bash \
  scripts/classical_search/menu_fair_cell.sh 22 laptop \
    --sub s1_simsplit --n 200 --band 122000000000 \
    --k-dets 8 --sims 1376 \
    --sims-tile 2408 --sims-meeple 344 \
  > /mnt/carc-shared/night_chain_20260812/s1_simsplit/laptop.log 2>&1 < /dev/null & disown
echo "laptop S1 launched pid $!"
