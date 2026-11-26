#!/bin/sh
# DownloadStack 诊断（Linux / macOS）
set -u
APP="$(cd "$(dirname "$0")" && pwd)"
R="$APP/diag-report.txt"
{
  echo "===== DownloadStack diag ====="
  echo "time: $(date)"
  echo "app dir: $APP"
  echo
  echo "[system]"
  uname -a
  echo
  echo "[python]"
  PY=""
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
  done
  if [ -n "$PY" ]; then
    echo "interp: $PY"
    "$PY" -c 'import sys;print("version",sys.version)'
    "$PY" -c 'import flet;print("flet OK")' 2>&1
    "$PY" -c 'import requests;print("requests OK")' 2>&1
  else
    echo "NOT FOUND python3"
  fi
  echo
  echo "[components]"
  for f in aria2/aria2c ariang/index.html ariaNg/index.html ControlPanel/panel.py ControlPanel/panel_ui.html ControlPanel/magnet_tools.py ControlPanel/config.json ControlPanel/ytdl_gui.py tools/yt-dlp; do
    if [ -e "$APP/../$f" ]; then echo "  YES $f"; else echo "  NO  $f"; fi
  done
  command -v aria2c >/dev/null 2>&1 && echo "  [system] aria2c $(command -v aria2c)" || echo "  [system] no aria2c"
  command -v qbittorrent >/dev/null 2>&1 && echo "  [system] qbittorrent yes" || echo "  [system] no qbittorrent"
  echo
  echo "[ports]"
  (ss -ltnp 2>/dev/null || netstat -an 2>/dev/null) | grep -E ':(18550|6800|8080)' || echo "  none listening"
  echo
  echo "[launcher log tail]"
  if [ -f "$APP/logs/launcher.log" ]; then tail -25 "$APP/logs/launcher.log"; else echo "  none"; fi
  echo
  echo "[config.json]"
  if [ -f "$APP/config.json" ]; then cat "$APP/config.json"; else echo "  none"; fi
} > "$R" 2>&1

echo "done. report = $R"
echo
cat "$R"
