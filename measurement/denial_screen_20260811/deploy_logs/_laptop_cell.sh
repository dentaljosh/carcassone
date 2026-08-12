cd /home/doctor/projects/carcassone || exit 1
mkdir -p /mnt/carc-shared/denial_deploy_20260812/denial_d1_s5_o3_deploy11008
setsid nohup env MENU_OUT_ROOT=/mnt/carc-shared/denial_deploy_20260812 nice -n 19 bash \
  scripts/classical_search/menu_fair_cell.sh 22 laptop \
    --sub denial_d1_s5_o3_deploy11008 --n 800 --band 124000000000 \
    --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 \
    --cand-leaf-json /home/doctor/projects/carcassone/measurement/denial_screen_20260811/cells/denial_d1_s5_o3_deploy_fixed_v1_vs_fairchamp11008.json --drift \
  > /mnt/carc-shared/denial_deploy_20260812/denial_d1_s5_o3_deploy11008/laptop.log 2>&1 < /dev/null & disown
echo "laptop cell launched pid $!"
