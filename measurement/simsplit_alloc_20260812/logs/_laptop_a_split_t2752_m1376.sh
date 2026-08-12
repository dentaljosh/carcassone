cd /home/doctor/projects/carcassone || exit 1
mkdir -p /mnt/carc-shared/simsplit_alloc_20260812/a_split_t2752_m1376
setsid nohup env MENU_OUT_ROOT=/mnt/carc-shared/simsplit_alloc_20260812 nice -n 19 bash \
  scripts/classical_search/menu_fair_cell.sh 22 laptop \
    --sub a_split_t2752_m1376 --n 800 --band 123000000000 --k-dets 8 --sims 2064 --sims-tile 2752 --sims-meeple 1376 --opp-k-dets 8 --opp-sims 1376 \
  > /mnt/carc-shared/simsplit_alloc_20260812/a_split_t2752_m1376/laptop.log 2>&1 < /dev/null & disown
echo "laptop a_split_t2752_m1376 launched pid $!"
