#!/usr/bin/env bash
# Headless Android emulator driver for playtesting the Carcassonne app from WSL2.
#
# Prereqs: sdkmanager packages "emulator" + "system-images;android-35;google_apis;x86_64",
# and rw access to /dev/kvm (user in the kvm group; we launch via `sg kvm` so a fresh
# login isn't needed after usermod -aG kvm).
#
# Usage:
#   emulator.sh create           # one-time AVD creation (carc35)
#   emulator.sh boot             # detached headless boot, waits for sys.boot_completed
#   emulator.sh install          # gradle-built debug APK -> emulator
#   emulator.sh launch           # start the app's MainActivity
#   emulator.sh shot NAME        # screencap -> scratchpad PNG (prints path)
#   emulator.sh tap X Y | swipe X1 Y1 X2 Y2 [ms] | key KEYCODE | text STR
#   emulator.sh kill             # stop the emulator

set -euo pipefail
SDK="${ANDROID_HOME:-$HOME/Android/Sdk}"
ADB="$SDK/platform-tools/adb"
AVD_NAME=carc35
APK="$(dirname "$0")/../app/build/outputs/apk/debug/app-debug.apk"
SHOT_DIR="${CARC_SHOT_DIR:-/tmp/carc_shots}"

case "${1:-}" in
  create)
    echo no | "$SDK/cmdline-tools/latest/bin/avdmanager" create avd \
      -n "$AVD_NAME" -k "system-images;android-35;google_apis;x86_64" -d pixel_7 --force
    # More RAM helps Chaquopy+numpy start faster
    sed -i 's/^hw.ramSize.*/hw.ramSize=4096/' "$HOME/.android/avd/$AVD_NAME.avd/config.ini" || true
    echo "AVD $AVD_NAME created"
    ;;
  boot)
    # Detached (Mac-sleep/WSL-teardown rule): setsid + nohup, log to /tmp.
    sg kvm -c "setsid nohup '$SDK/emulator/emulator' -avd $AVD_NAME \
      -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect \
      -no-snapshot -port 5554 > /tmp/carc_emulator.log 2>&1 < /dev/null &"
    echo "booting (log: /tmp/carc_emulator.log)..."
    "$ADB" wait-for-device
    until [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
      sleep 2
    done
    echo "boot completed"
    ;;
  install)
    "$ADB" install -r "$APK"
    ;;
  launch)
    "$ADB" shell am start -n com.jishal.carcassonne/.MainActivity
    ;;
  shot)
    mkdir -p "$SHOT_DIR"
    out="$SHOT_DIR/${2:-shot}_$(date +%H%M%S).png"
    "$ADB" exec-out screencap -p > "$out"
    echo "$out"
    ;;
  tap)    "$ADB" shell input tap "$2" "$3" ;;
  swipe)  "$ADB" shell input swipe "$2" "$3" "$4" "$5" "${6:-300}" ;;
  key)    "$ADB" shell input keyevent "$2" ;;
  text)   "$ADB" shell input text "$2" ;;
  kill)   "$ADB" emu kill ;;
  *) grep '^#   emulator.sh' "$0" | sed 's/^#   //'; exit 1 ;;
esac
