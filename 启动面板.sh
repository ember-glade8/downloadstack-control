#!/bin/sh
# DownloadStack Control 启动器（Linux / macOS）：先体检，缺什么问你装不装
set -u
APP="$(cd "$(dirname "$0")" && pwd)"
export TEMP="$APP/cache/temp"
export TMP="$APP/cache/temp"
export FLET_APP_STORAGE_DATA="$APP/cache/flet"
mkdir -p "$TEMP" "$FLET_APP_STORAGE_DATA" 2>/dev/null || true

ROOT_DIR="$(cd "$APP/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"
REC_PY="$ROOT_DIR/.venv_python"
if [ -f "$REC_PY" ]; then
  CAND="$(cat "$REC_PY" 2>/dev/null)"
  if [ -n "$CAND" ] && [ -x "$CAND" ]; then PY="$CAND"; fi
fi
if [ -z "${PY:-}" ] && [ -x "$VENV_PY" ] && "$VENV_PY" -c "import flet" >/dev/null 2>&1; then
  PY="$VENV_PY"
fi
for c in python3 python; do
  [ -n "${PY:-}" ] && break
  if command -v "$c" >/dev/null 2>&1; then
    v="$("$c" -c 'import sys;print(sys.version_info[1])' 2>/dev/null || echo 0)"
    if [ "$v" -ge 10 ] 2>/dev/null; then PY="$c"; break; fi
  fi
done

ROOT="$(cd "$APP/.." && pwd)"
MISS=""
echo "==== DownloadStack 环境自检 ===="
if [ -n "$PY" ]; then
  echo "  [OK] $PY $("$PY" -c 'import sys;print(sys.version.split()[0])')"
  "$PY" -c "import flet" >/dev/null 2>&1 && echo "  [OK] flet" || { echo "  [缺] flet"; MISS="$MISS flet"; }
  "$PY" -c "import requests" >/dev/null 2>&1 && echo "  [OK] requests" || { echo "  [缺] requests"; MISS="$MISS requests"; }
else
  echo "  [缺] Python 3.10+"; MISS="$MISS python3"
fi
command -v aria2c >/dev/null 2>&1 && echo "  [OK] aria2c" || { [ -f "$ROOT/aria2/aria2c" ] && echo "  [OK] aria2c(自带)" || { echo "  [缺] aria2c"; MISS="$MISS aria2"; }; }
[ -f "$ROOT/ariaNg/index.html" ] && echo "  [OK] AriaNg" || { echo "  [缺] AriaNg"; MISS="$MISS AriaNg"; }
command -v ffmpeg >/dev/null 2>&1 && echo "  [OK] ffmpeg" || { [ -x "$ROOT/tools/ffmpeg/bin/ffmpeg" ] && echo "  [OK] ffmpeg(自带)" || { echo "  [缺] ffmpeg"; MISS="$MISS ffmpeg"; }; }
[ -f "$APP/panel.py" ] && echo "  [OK] 面板文件" || { echo "  [缺] panel.py"; MISS="$MISS panel.py"; }

if [ -n "$MISS" ]; then
  echo
  echo "缺少:$MISS"
  if [ -f "$ROOT_DIR/install.sh" ]; then
    printf '  现在运行 install.sh 自动补齐吗？[Y/n]: '
    read -r a
    case "$a" in n|N|no|NO) echo "  已跳过，可手动处理";; *)
      sh "$ROOT_DIR/install.sh" --yes || echo "  安装向导返回非 0";;
    esac
  else
    echo "  没有找到 $ROOT_DIR/install.sh，请重新解压仓库后再试"
  fi
fi

if ! "$PY" -c "import flet" >/dev/null 2>&1; then
  echo "  [缺] flet / flet-desktop，正在安装 ..."
  PKGS="flet==1.1.3 flet-desktop==1.1.3 requests>=2.31"
  ok_install=0
  if [ -x "$VENV_PY" ] && "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    "$VENV_PY" -m pip install $PKGS && ok_install=1
  fi
  if [ "$ok_install" = 0 ]; then
    for C in python3 python; do
      command -v "$C" >/dev/null 2>&1 || continue
      "$C" -m pip install --break-system-packages --user $PKGS 2>/dev/null && { PY="$C"; ok_install=1; break; }
      "$C" -m pip install --break-system-packages $PKGS 2>/dev/null && { PY="$C"; ok_install=1; break; }
    done
  fi
  if [ "$ok_install" = 0 ]; then
    echo "  [失败] 依赖装不上。请手动执行其一："
    echo "     sudo apt install -y python3-venv python3-pip"
    echo "     然后重跑： sh $ROOT_DIR/install.sh"
    exit 1
  fi
fi

echo
echo "正在启动面板 ..."
exec "$PY" -B "$APP/panel.py"
