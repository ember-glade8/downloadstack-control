#!/usr/bin/env bash
# DownloadStack Control · Linux / macOS 安装向导
# 用法：
#   chmod +x install.sh && ./install.sh
#   ./install.sh --dry-run           # 只体检不安装
#   ./install.sh --root ~/DownloadStack --downloads ~/Downloads --yes
set -u

OS="$(uname -s)"
case "$OS" in
  Linux)  PLAT="linux" ;;
  Darwin) PLAT="macos" ;;
  *) echo "只支持 Linux / macOS（Windows 请用 install.bat）"; exit 1 ;;
esac

ROOT="${HOME}/DownloadStack"
DL="${HOME}/Downloads"
DRY=0
YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --yes|-y)  YES=1; shift ;;
    --root)    ROOT="$2"; shift 2 ;;
    --downloads) DL="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
ok()   { printf '  [OK] %s\n' "$*"; }
miss() { printf '  [缺] %s\n' "$*"; }
warn() { printf '  [警告] %s\n' "$*"; }

ask() {  # ask "问题" -> 0=同意 1=拒绝
  q="$1"
  if [ "$YES" = "1" ]; then return 0; fi
  if [ "$DRY" = "1" ]; then return 1; fi
  printf '      %s [Y/n]: ' "$q"
  read -r a
  case "$a" in n|N|no|NO) return 1 ;; *) return 0 ;; esac
}

have() { command -v "$1" >/dev/null 2>&1; }

SU_PREFIX=""
ensure_sudo() {
  have sudo || return 1
  if sudo -n true >/dev/null 2>&1; then SU_PREFIX="sudo -n"; return 0; fi
  if [ -t 0 ]; then
    echo "      需要管理员权限安装系统包（只问这一次）"
    echo "      提示：输入密码时屏幕不显示任何字符是正常的，输完按回车即可"
    if sudo -v; then SU_PREFIX="sudo -n"; return 0; fi
  fi
  return 1
}

pm_install() {  # pm_install 包名：优先非交互 sudo，避免卡在密码
  pkg="$1"
  S="$SU_PREFIX"
  if [ -z "$S" ]; then ensure_sudo && S="$SU_PREFIX"; fi
  if have apt-get; then
    if [ -n "$S" ]; then $S apt-get update -qq && $S apt-get install -y "$pkg"; else
      warn "需要管理员权限装 $pkg，请手动执行： sudo apt install -y $pkg"; return 1; fi
  elif have dnf; then
    if [ -n "$S" ]; then $S dnf install -y "$pkg"; else warn "请手动: sudo dnf install $pkg"; return 1; fi
  elif have pacman; then
    if [ -n "$S" ]; then $S pacman -S --noconfirm "$pkg"; else warn "请手动: sudo pacman -S $pkg"; return 1; fi
  elif have zypper; then
    if [ -n "$S" ]; then $S zypper install -y "$pkg"; else warn "请手动: sudo zypper install $pkg"; return 1; fi
  elif have brew; then brew install "$pkg"
  else return 1
  fi
}

say ""
say "============================================================"
say "   DownloadStack · 安装向导（$PLAT）"
say "   程序目录: $ROOT"
say "   下载目录: $DL"
say "============================================================"
say ""

say "[0/8] 环境体检"
ok "$(uname -srm)"
for c in python3 pip3 curl unzip tar; do
  if have "$c"; then ok "$c"; else miss "$c"; fi
done

PY=""
for c in python3 python; do
  if have "$c"; then
    v="$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"
    maj="${v%%.*}"; min="${v##*.}"
    if [ "$maj" -ge 3 ] && [ "$min" -ge 10 ] 2>/dev/null; then PY="$c"; ok "Python $v ($c)"; break; fi
    miss "Python 版本过低: $v"
  fi
done
if [ -z "$PY" ]; then
  if ask "Python 缺失，现在安装吗？"; then
    pm_install python3 || warn "自动安装失败，请手动装 Python 3.10+"
    PY="$(command -v python3 || true)"
  fi
fi

# GUI 向导需要 tkinter；没有就提示装 python3-tk
if [ -n "$PY" ] && ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
  miss "python3-tk（图形向导需要）"
  if ask "现在安装 python3-tk 吗？"; then pm_install python3-tk || warn "安装失败，之后可用 --text 文本引导"; fi
fi

# 依赖：优先用 venv，避免 Ubuntu 24.04 的 externally-managed-environment
VENV="$ROOT/.venv"
if [ -z "${VENV_READY:-}" ]; then
  if [ -x "$VENV/bin/python" ]; then
    VENV_READY=1
    ok "已有虚拟环境 $VENV"
  elif "$PY" -m venv "$VENV" >/dev/null 2>&1; then
    VENV_READY=1
    ok "已创建虚拟环境 $VENV"
  else
    miss "python3-venv（创建虚拟环境需要）"
    if ask "现在安装 python3-venv 吗？"; then
      pm_install python3-venv || true
      if "$PY" -m venv "$VENV" >/dev/null 2>&1; then VENV_READY=1; ok "已创建虚拟环境"; fi
    fi
  fi
fi
VPY="$PY"
if [ -x "$VENV/bin/python" ]; then
  # venv 里必须同时有 pip 才可用（Ubuntu 缺 python3-venv 时会建出"无 pip"的空壳）
  if "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
    VPY="$VENV/bin/python"
  else
    warn "虚拟环境里没有 pip（缺 python3-venv）"
    if ask "现在安装 python3-venv 并重建虚拟环境吗？"; then
      pm_install python3-venv || true
      rm -rf "$VENV"
      if "$PY" -m venv "$VENV" >/dev/null 2>&1 && "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
        VPY="$VENV/bin/python"
        ok "虚拟环境已重建（带 pip）"
      else
        warn "重建失败，改用系统 Python 安装依赖"
        VPY="$PY"
      fi
    else
      VPY="$PY"
    fi
  fi
fi
if [ "$VPY" = "$PY" ]; then
  PIPEXTRA="--break-system-packages --user"
else
  PIPEXTRA=""
fi

if [ -n "$VPY" ]; then
  if "$VPY" -c "import importlib.util as u,sys;sys.exit(0 if (u.find_spec('flet') and u.find_spec('requests')) else 1)" 2>/dev/null; then
    ok "pip 依赖 flet + requests"
  else
    miss "pip 依赖 flet / flet-desktop / flet-web / requests"
    if ask "现在安装 flet + requests 吗？"; then
      "$VPY" -m pip install -q --upgrade pip >/dev/null 2>&1 || true
      timeout 900 "$VPY" -m pip install $PIPEXTRA "flet==1.1.3" "flet-desktop==1.1.3" "flet-web==1.1.3" "requests>=2.31" || \
        timeout 900 "$VPY" -m pip install $PIPEXTRA -i https://pypi.tuna.tsinghua.edu.cn/simple "flet==1.1.3" "flet-desktop==1.1.3" "flet-web==1.1.3" "requests>=2.31" || \
        warn "依赖安装失败，可稍后重试"
    fi
  fi
fi

have ffmpeg && ok "ffmpeg" || {
  miss "ffmpeg（yt-dlp 合并音视频用）"
  if ask "现在安装 ffmpeg 吗？"; then pm_install ffmpeg || warn "自动安装失败"; fi
}

have aria2c && ok "aria2c" || {
  miss "aria2c"
  if ask "现在安装 aria2 吗？"; then pm_install aria2 || warn "自动安装失败"; fi
}

[ "$DRY" = "1" ] && { say ""; say "[演示模式] 到此为止"; exit 0; }

say ""
say "[1/8] 创建目录"
for d in aria2 ariaNg ControlPanel logs cache backups tools; do
  mkdir -p "$ROOT/$d" || { warn "建目录失败: $ROOT/$d"; exit 1; }
done
for d in aria2 qBittorrent ytdlp; do
  mkdir -p "$DL/$d" || { warn "建目录失败: $DL/$d"; exit 1; }
done
ok "目录就绪"

say ""
say "[2/8] AriaNg"
if [ -f "$ROOT/ariaNg/index.html" ]; then
  ok "已存在，跳过"
else
  tmp="$(mktemp -d)"
  url="https://github.com/mayswind/AriaNg/releases/download/1.3.15/AriaNg-1.3.15-AllInOne.zip"
  say "      下载 AriaNg ..."
  if curl -fsSL --connect-timeout 20 --max-time 900 "$url" -o "$tmp/a.zip"; then
    ( have unzip && unzip -q -o "$tmp/a.zip" -d "$tmp/x" ) || ( cd "$tmp" && python3 -m zipfile -e a.zip x )
    if [ -f "$tmp/x/index.html" ]; then cp -R "$tmp/x/." "$ROOT/ariaNg/"; else cp -R "$tmp/x"/*/. "$ROOT/ariaNg/" 2>/dev/null || true; fi
    [ -f "$ROOT/ariaNg/index.html" ] && ok "AriaNg 就位" || miss "AriaNg 解压异常"
  else
    miss "AriaNg 下载失败"
  fi
  rm -rf "$tmp"
fi

say ""
say "[3/8] yt-dlp"
YT="$ROOT/tools/yt-dlp"
if [ -x "$YT" ]; then
  ok "已存在"
else
  say "      下载 yt-dlp ($PLAT) ..."
  if [ "$PLAT" = "macos" ]; then yu="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"; else yu="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"; fi
  if curl -fsSL --connect-timeout 20 --max-time 1800 "$yu" -o "$YT"; then chmod +x "$YT"; ok "yt-dlp 就位"; else
    miss "直接下载失败"
    if [ -n "$PY" ] && ask "用 pip 安装 yt-dlp 作为后备吗？"; then
      "$PY" -m pip install --user -U yt-dlp && printf '#!/bin/sh\nexec %s -m yt_dlp "$@"\n' "$PY" > "$YT" && chmod +x "$YT" && ok "已用 pip 版 yt-dlp"
    fi
  fi
fi

say ""
say "[4/8] 端口与密钥"
pick_port() {
  base="$1"; max=$((base+5))
  for p in $(seq "$base" "$max"); do
    if have ss; then ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":$p\$" || { echo "$p"; return; }
    elif have lsof; then lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || { echo "$p"; return; }
    else echo "$base"; return
    fi
  done
  echo "$base"
}
ARIA_PORT="$(pick_port 6800)"
ARIANG_PORT="$(pick_port 16800)"
if have openssl; then SECRET="$(openssl rand -hex 32)"; else SECRET="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"; fi
ok "aria2 端口 $ARIA_PORT / AriaNg 端口 $ARIANG_PORT"
printf '%s\n' "$SECRET" > "$ROOT/aria2/rpc-secret.txt"

say ""
say "[5/8] 生成 aria2.conf"
cat > "$ROOT/aria2/aria2.conf" <<EOF
continue=true
dir=$DL/aria2
input-file=$ROOT/aria2/session.txt
save-session=$ROOT/aria2/session.txt
save-session-interval=30
max-concurrent-downloads=3
split=4
max-connection-per-server=4
min-split-size=1M
file-allocation=none
log=$ROOT/logs/aria2.log
log-level=warn
enable-rpc=true
rpc-listen-all=false
rpc-listen-port=$ARIA_PORT
rpc-allow-origin-all=true
rpc-secret=$SECRET
dht-file-path=$ROOT/aria2/dht.dat
dht-file-path6=$ROOT/aria2/dht6.dat
EOF
: > "$ROOT/aria2/session.txt"
ok "aria2.conf 写好"

say ""
say "[6/8] 生成启停脚本"
ARIA_BIN="$(command -v aria2c || echo "$ROOT/aria2/aria2c")"
cat > "$ROOT/start_aria2.sh" <<EOF
#!/bin/sh
cd "\$(dirname "\$0")"
exec "$ARIA_BIN" --conf-path="$ROOT/aria2/aria2.conf"
EOF
cat > "$ROOT/stop_aria2.sh" <<EOF
#!/bin/sh
pkill -f "$ROOT/aria2/aria2.conf" 2>/dev/null || true
EOF
cat > "$ROOT/start_ariang.sh" <<EOF
#!/bin/sh
cd "$ROOT/ariaNg" || exit 1
exec "$VPY" -m http.server $ARIANG_PORT --bind 127.0.0.1
EOF
cat > "$ROOT/start_qbit.sh" <<'EOF'
#!/bin/sh
if command -v qbittorrent >/dev/null 2>&1; then exec qbittorrent; fi
if [ -d /Applications/qbittorrent.app ]; then open -a qbittorrent; exit 0; fi
echo "没装 qBittorrent，请自行安装（apt install qbittorrent / brew install --cask qbittorrent）"
EOF
chmod +x "$ROOT"/*.sh
ok "启停脚本就位"

say ""
say "[7/8] 面板配置与启动器"
cat > "$ROOT/ControlPanel/config.json" <<EOF
{
  "aria2": {
    "host": "127.0.0.1", "port": $ARIA_PORT,
    "exe": "$ARIA_BIN",
    "conf": "$ROOT/aria2/aria2.conf",
    "secret": "$ROOT/aria2/rpc-secret.txt",
    "logdir": "$ROOT/logs"
  },
  "qbit": {
    "host": "127.0.0.1", "port": 8080,
    "user": "admin", "pass": "",
    "config_dir": "$ROOT/qBittorrent/config",
    "save_dir": "$DL/qBittorrent",
    "exe_dir": "$ROOT/qBittorrent"
  },
  "yt": { "bat": "$ROOT/ControlPanel/yt-download.sh", "bat2": "", "ini": "" },
  "ariang": { "port": $ARIANG_PORT, "dir": "$ROOT/ariaNg", "script": "$ROOT/start_ariang.sh" },
  "scripts": {
    "start": "$ROOT/start_aria2.sh",
    "stop": "$ROOT/stop_aria2.sh",
    "qbit": "$ROOT/start_qbit.sh"
  },
  "paths": { "downloads": "$DL" },
  "ui": { "theme": "dark", "upscale": false }
}
EOF
if [ -f "$(dirname "$0")/panel.py" ]; then cp "$(dirname "$0")/panel.py" "$ROOT/ControlPanel/" 2>/dev/null || true; fi
if [ -f "$(dirname "$0")/panel_ui.html" ]; then cp "$(dirname "$0")/panel_ui.html" "$ROOT/ControlPanel/" 2>/dev/null || true; fi
if [ -f "$(dirname "$0")/magnet_tools.py" ]; then cp "$(dirname "$0")/magnet_tools.py" "$ROOT/ControlPanel/" 2>/dev/null || true; fi
if [ -f "$(dirname "$0")/启动面板.sh" ]; then cp "$(dirname "$0")/启动面板.sh" "$ROOT/ControlPanel/" 2>/dev/null || true; fi
if [ -f "$(dirname "$0")/ytdl_gui.py" ]; then cp "$(dirname "$0")/ytdl_gui.py" "$ROOT/ControlPanel/" 2>/dev/null || true; fi
cat > "$ROOT/ControlPanel/yt-download.sh" <<EOF
#!/bin/sh
export DOWNLOADSTACK_ROOT="$ROOT"
export DOWNLOADSTACK_DOWNLOADS="$DL"
export YTDLP_PATH="$YT"
[ -x "$ROOT/tools/video2x/video2x" ] && export VIDEO2X_PATH="$ROOT/tools/video2x/video2x"
[ -x "/Applications/Video2X.app/Contents/MacOS/video2x" ] && export VIDEO2X_PATH="/Applications/Video2X.app/Contents/MacOS/video2x"
exec "$VPY" -B "$ROOT/ControlPanel/ytdl_gui.py"
EOF
chmod +x "$ROOT/ControlPanel/yt-download.sh"
ok "config.json 写好"

if [ "$PLAT" = "linux" ]; then
  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/downloadstack.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=DownloadStack 下载控制台
Exec=/bin/sh "$ROOT/ControlPanel/启动面板.sh"
Terminal=true
Categories=Utility;
EOF
  ok "已加桌面菜单项（DownloadStack 下载控制台）"
else
  cat > "$HOME/Desktop/DownloadStack 下载控制台.command" <<EOF
#!/bin/sh
exec /bin/sh "$ROOT/ControlPanel/启动面板.sh"
EOF
  chmod +x "$HOME/Desktop/DownloadStack 下载控制台.command"
  ok "已放 ~/Desktop/DownloadStack 下载控制台.command"
fi

say ""
# 记录最终可用的解释器，供启动器读取
printf '%s\n' "$VPY" > "$ROOT/.venv_python" 2>/dev/null || true

say ""
say "[8/8] 自检"
missn=0
[ -x "$ARIA_BIN" ] || { [ -f "$ARIA_BIN" ] && ok "aria2c" || { miss "aria2c"; missn=$((missn+1)); }; }
[ -f "$ROOT/ariaNg/index.html" ] && ok "AriaNg" || { miss "AriaNg"; missn=$((missn+1)); }
[ -x "$YT" ] && ok "yt-dlp" || { miss "yt-dlp"; missn=$((missn+1)); }
[ -f "$ROOT/ControlPanel/panel.py" ] && ok "面板源码" || warn "面板源码未复制（把 panel.py 放同目录再跑）"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  ok "虚拟环境 $VENV（带 pip）"
elif [ -x "$VENV/bin/python" ]; then
  warn "虚拟环境存在但没有 pip（需 sudo apt install python3-venv 后重跑）"
else
  warn "没建虚拟环境，面板可能因 PEP668 装不上依赖"
fi
if "$VPY" -c "import flet" >/dev/null 2>&1; then ok "flet 依赖可用（$VPY）"; else warn "flet 还没装上，启动面板前需先装依赖"; fi

say ""
say "============================================================"
say " 安装完成：$ROOT"
say " 下一步：sh \"$ROOT/ControlPanel/启动面板.sh\""
say " 面板里点「启动 Aria2 + AriaNg」即可"
say "============================================================"
[ "$missn" -eq 0 ] && say " 全部就绪" || say " 有 $missn 项缺失，见上面 [缺] 行"
