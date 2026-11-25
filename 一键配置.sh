#!/bin/sh
# DownloadStack 一键配置（Linux / macOS）
# 作用：装系统依赖 -> 装 Python 依赖 -> 打开图形向导（无桌面则文本引导）
set -u
APP="$(cd "$(dirname "$0")" && pwd)"
cd "$APP" || exit 1
MODE="${1:-}"

say()  { printf '%s\n' "$*"; }
ok()   { printf '  [OK] %s\n' "$*"; }
warn() { printf '  [注意] %s\n' "$*"; }

say "============================================================"
say "   DownloadStack 一键配置（Linux / macOS）"
say "============================================================"
say ""

# ---------- 1. Python ----------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  say "[1/4] 没找到 python3，尝试用包管理器安装 ..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-tk
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip python3-tkinter
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --noconfirm python python-pip tk
  elif command -v brew >/dev/null 2>&1; then
    brew install python
  else
    say "[失败] 没有可用的包管理器，请手动安装 python3"
    exit 1
  fi
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
  done
fi
if [ -z "$PY" ]; then say "[失败] python3 仍不可用"; exit 1; fi
ok "Python: $("$PY" -c 'import sys;print(sys.version.split()[0])')"

# 只扫描 / 全自动：不装系统包、直接交给向导
case "$MODE" in
  --scan|/scan|-s) exec "$PY" -B "$APP/setup_wizard.py" --scan ;;
  --auto|/auto|-a) exec "$PY" -B "$APP/setup_wizard.py" --auto ;;
  --text|/text|-t) exec "$PY" -B "$APP/setup_wizard.py" --text ;;
esac

# ---------- 2. 系统依赖（apt/brew）----------
say ""
say "[2/4] 检查系统依赖（ffmpeg / aria2）"
NEED_PKGS=""
command -v ffmpeg  >/dev/null 2>&1 || NEED_PKGS="$NEED_PKGS ffmpeg"
command -v aria2c  >/dev/null 2>&1 || NEED_PKGS="$NEED_PKGS aria2"
if "$PY" -c "import tkinter" >/dev/null 2>&1; then ok "tkinter"; else
  NEED_PKGS="$NEED_PKGS python3-tk"; warn "缺 tkinter（图形向导需要）"
fi

if [ -n "$NEED_PKGS" ]; then
  say "  需要安装:$NEED_PKGS"
  printf '  现在安装吗？[Y/n]: '
  read -r a
  case "$a" in
    n|N|no|NO) warn "已跳过系统依赖（之后可手动装）";;
    *)
      if command -v apt-get >/dev/null 2>&1; then
        say ""
        say "  >>> 接下来会要求输入 sudo 密码"
        say "  >>> 注意：输入密码时屏幕上不会显示任何字符（连星号都没有），这是正常的"
        say "  >>> 输完直接按回车即可继续"
        say ""
        sudo apt-get update -qq && sudo apt-get install -y $NEED_PKGS
      elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y $NEED_PKGS
      elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm $NEED_PKGS
      elif command -v brew >/dev/null 2>&1; then
        for p in $NEED_PKGS; do case "$p" in python3-tk) brew install python-tk;; *) brew install "$p";; esac; done
      else
        warn "没有包管理器，请手动安装:$NEED_PKGS"
      fi
      ;;
  esac
else
  ok "系统依赖齐全"
fi

# ---------- 3. Python 依赖 ----------
say ""
say "[3/4] 检查 Python 依赖（flet / requests）"
PIPFLAGS="--user"
if "$PY" -m pip --version >/dev/null 2>&1; then
  :
else
  warn "python3 没有 pip，先装 pip"
  if command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y python3-pip; fi
fi
if "$PY" -c "import flet,requests" >/dev/null 2>&1; then
  ok "flet + requests 已安装"
else
  printf '  现在用 pip 安装 flet + requests 吗？[Y/n]: '
  read -r b
  case "$b" in
    n|N|no|NO) warn "已跳过";;
    *)
      # Ubuntu 24.04 起 pip 默认要 --break-system-packages
      "$PY" -m pip install $PIPFLAGS "flet==1.1.3" "requests>=2.31" 2>/dev/null \
        || "$PY" -m pip install $PIPFLAGS --break-system-packages "flet==1.1.3" "requests>=2.31" \
        || "$PY" -m pip install $PIPFLAGS --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple "flet==1.1.3" "requests>=2.31"
      ;;
  esac
fi

# ---------- 4. 打开向导 ----------
say ""
say "[4/4] 打开配置向导"
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && "$PY" -c "import tkinter" >/dev/null 2>&1; then
  say "  打开图形窗口 ..."
  exec "$PY" -B "$APP/setup_wizard.py"
fi
say "  当前没有图形环境（SSH / 无桌面），用文本引导："
say "  （想用图形窗口：在虚拟机桌面里双击本文件，或运行 python3 setup_wizard.py）"
say ""
exec "$PY" -B "$APP/setup_wizard.py" --text
