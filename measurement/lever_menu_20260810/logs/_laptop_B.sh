cd /home/doctor/projects/carcassone || exit 1
mkdir -p /mnt/carc-shared/lever_menu_20260810/b_farmgrowthoff_n1600_b118e9
setsid nohup env MENU_OUT_ROOT=/mnt/carc-shared/lever_menu_20260810 nice -n 19 bash \
  scripts/classical_search/menu_fair_cell.sh 22 laptop \
    --sub b_farmgrowthoff_n1600_b118e9 --n 1600 --band 118000000000 \
    --cand-leaf-json /home/doctor/projects/carcassone/measurement/lever_menu_20260810/cells/menu_farmgrowthoff_fixed_v1_vs_fairchamp11008.json --drift \
    --k-dets 8 --sims 1376 \
  > /mnt/carc-shared/lever_menu_20260810/b_farmgrowthoff_n1600_b118e9/laptop.log 2>&1 < /dev/null & disown
echo "laptop B launched pid $!"
