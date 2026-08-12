cd /home/doctor/projects/carcassone || exit 1
mkdir -p /mnt/carc-shared/night_chain_20260812
setsid nohup nice -n 19 bash \
  scripts/classical_search/denial_cell_launcher.sh 22 laptop \
    --cells-file /mnt/carc-shared/night_chain_20260812/d1_cells.tsv --n 200 --band 121000000000 --out-root /mnt/carc-shared/night_chain_20260812 --sims 2750 \
  > /mnt/carc-shared/night_chain_20260812/laptop_D1.log 2>&1 < /dev/null & disown
echo "laptop D1 launched pid $!"
