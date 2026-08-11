cd /home/doctor/projects/carcassone || exit 1
setsid nohup env OW=12 nice -n 19 bash \
  scripts/classical_search/menu_item5_ext_laptop.sh \
  > /mnt/carc-shared/teacher_h2h_94e9/logs/ext_laptop_launch.log 2>&1 < /dev/null & disown
echo "laptop E launched pid $!"
