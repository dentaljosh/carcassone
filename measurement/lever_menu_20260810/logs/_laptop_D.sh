cd /home/doctor/projects/carcassone || exit 1
mkdir -p /mnt/carc-shared/lever_menu_20260810/d_width_k4x2752_vs_champ_n800_b119e9
setsid nohup env MENU_OUT_ROOT=/mnt/carc-shared/lever_menu_20260810 nice -n 19 bash \
  scripts/classical_search/menu_fair_cell.sh 22 laptop \
    --sub d_width_k4x2752_vs_champ_n800_b119e9 --n 800 --band 119000000000 \
    --k-dets 4 --sims 2752 --opp-k-dets 8 --opp-sims 1376 \
  > /mnt/carc-shared/lever_menu_20260810/d_width_k4x2752_vs_champ_n800_b119e9/laptop.log 2>&1 < /dev/null & disown
echo "laptop D launched pid $!"
