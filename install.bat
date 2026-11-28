@echo off
setlocal EnableExtensions
chcp 936 >nul
title DownloadStack 安装向导
color 0B
set "DRYRUN=0"
set "FAILED=0"
set "NEED_PY=0"
set "NEED_PIP=0"
set "NEED_FFMPEG=0"
if /I "%~1"=="--dry-run" set "DRYRUN=1"
if /I "%~1"=="--selftest" goto :selftest
if /I "%~1"=="--detect" goto :detect
if /I "%~1"=="--envcheck" goto :envcheck

echo.
echo ============================================================
echo    DownloadStack 下载调度栈 · 安装向导
echo    装到哪个盘、下载到哪，都由你决定
echo ============================================================
echo.

rem ================= 0. 环境体检 =================
echo [0/9] 环境体检
echo       Windows:
ver
for %%C in (powershell tar certutil curl winget) do call :ec_one %%C

set "PYEXE="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE goto :env_no_py
set "PYMAJ="
set "PYMIN="
set "PYVF=%TEMP%\ds_pyver.txt"
if exist "%PYVF%" del "%PYVF%" >nul 2>&1
"%PYEXE%" -c "import sys;open(r'%PYVF%','w').write(str(sys.version_info[0])+' '+str(sys.version_info[1]))" >nul 2>&1
for /f "tokens=1,2" %%A in ('type "%PYVF%" 2^>nul') do (set "PYMAJ=%%A"& set "PYMIN=%%B")
set "PYOK=0"
if defined PYMIN if "%PYMAJ%"=="3" if not "%PYMIN%"=="0" if not "%PYMIN%"=="1" if not "%PYMIN%"=="2" if not "%PYMIN%"=="3" if not "%PYMIN%"=="4" if not "%PYMIN%"=="5" if not "%PYMIN%"=="6" if not "%PYMIN%"=="7" if not "%PYMIN%"=="8" if not "%PYMIN%"=="9" set "PYOK=1"
if "%PYOK%"=="1" (echo   [OK] Python %PYMAJ%.%PYMIN%  %PYEXE%) else (echo   [缺] Python 版本过低（需 3.10+）: %PYEXE%& set "NEED_PY=1")
if "%PYOK%"=="1" goto :env_pip
goto :env_ff
:env_no_py
echo   [缺] Python（3.10+）
set "NEED_PY=1"
goto :env_ff

:env_pip
"%PYEXE%" -c "import importlib.util as u;raise SystemExit(0 if (u.find_spec('flet') and u.find_spec('requests')) else 1)" >nul 2>&1
if errorlevel 1 (echo   [缺] pip 包 flet / requests& set "NEED_PIP=1") else (echo   [OK] pip 包 flet + requests)

:env_ff
where ffmpeg >nul 2>&1
if errorlevel 1 (echo   [缺] ffmpeg（yt-dlp 合并音视频用）& set "NEED_FFMPEG=1") else (echo   [OK] ffmpeg)
echo.
set "MISSENV="
if "%NEED_PY%"=="1" set "MISSENV=%MISSENV% Python"
if "%NEED_PIP%"=="1" set "MISSENV=%MISSENV% flet+requests"
if "%NEED_FFMPEG%"=="1" set "MISSENV=%MISSENV% ffmpeg"
if defined MISSENV (
  echo   缺少依赖:%MISSENV%
  echo   下面确定目录后会逐项询问安装
) else (
  echo   依赖齐全，无需安装
)
echo.

rem ================= 1. 复用检测 =================
set "EXIST_ROOT="
for /f "usebackq delims=" %%R in (`powershell -NoProfile -Command "$c=@(); if($env:DOWNLOADSTACK_ROOT){$c+=$env:DOWNLOADSTACK_ROOT}; $c+='D:\Tools\DownloadStack','C:\Tools\DownloadStack','E:\Tools\DownloadStack'; foreach($d in 'C','D','E','F'){ $c+=($d + ':\Tools\DownloadStack') }; $seen=@{}; foreach($p in $c){ if($p -and -not $seen[$p]){ $seen[$p]=1; if(Test-Path (Join-Path $p 'aria2\aria2c.exe')){ Write-Output $p; exit 0 } } }; exit 1"`) do set "EXIST_ROOT=%%R"
if not defined EXIST_ROOT goto :ask_drive
echo [1/9] 检测到本机已安装: %EXIST_ROOT%
echo       直接复用它（不重复下载）；回车继续，或输入 N 装到别处。
set "REUSE="
if not "%DS_AUTO%"=="1" set /p "REUSE=      复用已有安装？回车=复用，N=另装: "
if /I not "%REUSE%"=="N" goto :use_existing

:ask_drive
echo.
echo [2/9] 选择安装盘符（下面这些可用）
for %%d in (C D E F G H I J) do if exist "%%d:\" echo        %%d:
echo.
set "DRV="
if /I "%DS_AUTO%"=="1" set "DRV=D"
if not defined DRV set /p "DRV=      请输入盘符（回车 = D）: "
if "%DRV%"=="" set "DRV=D"
for /f "tokens=1 delims= " %%A in ("%DRV%") do set "DRV=%%A"
set "DRIVE=%DRV%:"
if not exist "%DRIVE%\" goto :bad_drive
set "BASE=%DRIVE%\Tools\DownloadStack"
set "DL=%DRIVE%\Downloads"
goto :path_confirm

:use_existing
set "BASE=%EXIST_ROOT%"
for %%d in ("%BASE%") do set "DL=%%~dd\Downloads"
echo       复用路径: %BASE%

:path_confirm
if defined DS_BASE set "BASE=%DS_BASE%"
if defined DS_DL set "DL=%DS_DL%"
echo.
echo [3/9] 安装位置确认
echo       程序目录: %BASE%
echo       下载目录: %DL%
echo.
if "%DS_AUTO%"=="1" goto :dir_ok

:ask_confirm
set "ANS="
set /p "ANS=      确认？回车=可以，输入 N 自己改: "
if "%ANS%"=="" goto :dir_ok
if /I "%ANS%"=="N" goto :ask_paths
echo       只认回车或 N，其他输入无效，请重输。
goto :ask_confirm

:ask_paths
set "BASE="
set /p "BASE=      程序目录（必须像 D:\Tools\DownloadStack 这种绝对路径）: "
call :check_abs "%BASE%"
if errorlevel 1 goto :bad_base
set "DL="
set /p "DL=      下载目录（必须像 D:\Downloads 这种绝对路径）: "
call :check_abs "%DL%"
if errorlevel 1 goto :bad_dl
if /I "%BASE%\"=="%DL%\" goto :same_dir
goto :dir_ok
:bad_base
echo       [不行] 程序目录要写成 盘符:\路径，不能只写一个字母或相对路径。
goto :ask_paths
:bad_dl
echo       [不行] 下载目录要写成 盘符:\路径，且盘符要真实存在。
goto :ask_paths
:same_dir
echo       [不行] 程序目录和下载目录不能是同一个。
goto :ask_paths

:dir_ok
set "TMPD=%BASE%\cache\_dl"

rem ---- 端口自动避让 ----
set "ARIA_PORT="
set "ARIANG_PORT="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$u=(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue).LocalPort; $f=6800; foreach($p in 6800,6801,6802,6803,6804,6805){ if($u -notcontains $p){ $f=$p; break } }; $f"`) do set "ARIA_PORT=%%P"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$u=(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue).LocalPort; $f=16800; foreach($p in 16800,16801,16802,16803){ if($u -notcontains $p){ $f=$p; break } }; $f"`) do set "ARIANG_PORT=%%P"
if "%ARIA_PORT%"=="" set "ARIA_PORT=6800"
if "%ARIANG_PORT%"=="" set "ARIANG_PORT=16800"
echo       端口: aria2=%ARIA_PORT%  AriaNg=%ARIANG_PORT%（占用会自动换）

rem ================= 4. 建目录 =================
echo.
echo [4/9] 创建目录
if "%DRYRUN%"=="1" goto :dirs_done
for %%P in (
  "%BASE%\aria2"
  "%BASE%\ariaNg"
  "%BASE%\qBittorrent"
  "%BASE%\ControlPanel"
  "%BASE%\logs"
  "%BASE%\cache\flet"
  "%BASE%\backups"
  "%BASE%\tools"
  "%TMPD%"
  "%DL%\aria2"
  "%DL%\qBittorrent"
  "%DL%\ytdlp"
) do if not exist "%%~P" mkdir "%%~P" >nul 2>&1
if not exist "%BASE%\aria2\session.txt" type nul > "%BASE%\aria2\session.txt"
:dirs_done
echo [OK] 目录就绪

rem ---- 按需安装缺失依赖（此时 BASE 已确定）----
if "%DRYRUN%"=="1" goto :after_install
if "%DS_AUTO%"=="1" goto :auto_install
if "%NEED_PY%"=="1" (
  choice /c YN /n /m "      Python 缺失，现在自动安装吗？(Y/N): "
  if not errorlevel 2 call :install_python
)
if "%NEED_PIP%"=="1" (
  choice /c YN /n /m "      pip 依赖缺失，现在装 flet + requests 吗？(Y/N): "
  if not errorlevel 2 call :install_pip
)
if "%NEED_FFMPEG%"=="1" if not exist "%BASE%\tools\ffmpeg\bin\ffmpeg.exe" (
  choice /c YN /n /m "      ffmpeg 缺失，现在装吗（约 120MB）？(Y/N): "
  if not errorlevel 2 call :install_ffmpeg
)
goto :after_install
:auto_install
if "%NEED_PY%"=="1" call :install_python
if "%NEED_PIP%"=="1" call :install_pip
if "%NEED_FFMPEG%"=="1" if not exist "%BASE%\tools\ffmpeg\bin\ffmpeg.exe" call :install_ffmpeg
:after_install
echo.

rem ================= 5. aria2 =================
echo.
echo [5/9] aria2c
if exist "%BASE%\aria2\aria2c.exe" goto :a2_ok
if "%DRYRUN%"=="1" goto :a2_ok
set "A2URL=https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"
call :download "%A2URL%" "%TMPD%\aria2.zip"
if errorlevel 1 goto :a2_bad
call :verify "%TMPD%\aria2.zip" 67d015301eef0b612191212d564c5bb0a14b5b9c4796b76454276a4d28d9b288
if errorlevel 1 goto :a2_bad
call :unzip "%TMPD%\aria2.zip" "%TMPD%\aria2x"
if errorlevel 1 goto :a2_bad
for /r "%TMPD%\aria2x" %%F in (aria2c.exe) do call :take "%%F" "%BASE%\aria2"
if not exist "%BASE%\aria2\aria2c.exe" goto :a2_bad
:a2_ok
echo [OK] aria2c.exe 就位
goto :step6
:a2_bad
color 0E
echo [警告] aria2 没拉下来，可稍后手动放进 %BASE%\aria2\
set "FAILED=1"
color 0B

rem ================= 6. AriaNg =================
:step6
echo.
echo [6/9] AriaNg
if exist "%BASE%\ariaNg\index.html" goto :an_ok
if "%DRYRUN%"=="1" goto :an_ok
set "ANURL=https://github.com/mayswind/AriaNg/releases/download/1.3.15/AriaNg-1.3.15-AllInOne.zip"
call :download "%ANURL%" "%TMPD%\ariang.zip"
if errorlevel 1 goto :an_bad
call :verify "%TMPD%\ariang.zip" 9918932af1ab0ae3924b938b1c5195b6491dacf15908ac0dc440fdba660ac280
if errorlevel 1 goto :an_bad
call :unzip "%TMPD%\ariang.zip" "%TMPD%\ariangx"
if errorlevel 1 goto :an_bad
xcopy /e /i /y /q "%TMPD%\ariangx\*" "%BASE%\ariaNg\" >nul 2>&1
if not exist "%BASE%\ariaNg\index.html" for /d %%D in ("%TMPD%\ariangx\*") do if exist "%%D\index.html" xcopy /e /i /y /q "%%D\*" "%BASE%\ariaNg\" >nul 2>&1
if not exist "%BASE%\ariaNg\index.html" goto :an_bad
:an_ok
echo [OK] AriaNg 就位
goto :step7
:an_bad
color 0E
echo [警告] AriaNg 没拉下来，可手动解压到 %BASE%\ariaNg\
set "FAILED=1"
color 0B

rem ================= 7. yt-dlp =================
:step7
echo.
echo [7/9] yt-dlp.exe
if exist "%DL%\ytdlp\yt-dlp.exe" goto :yt_ok
if "%DRYRUN%"=="1" goto :yt_ok
call :download "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" "%DL%\ytdlp\yt-dlp.exe"
if errorlevel 1 goto :yt_fallback
if not exist "%DL%\ytdlp\yt-dlp.exe" goto :yt_fallback
:yt_ok
echo [OK] yt-dlp.exe 就位
goto :step8
:yt_fallback
echo       直接下载失败，改用 pip 装 yt-dlp 模块 + 包装脚本 ...
if "%NEED_PY%"=="1" goto :yt_bad
if not defined PYEXE goto :yt_bad
"%PYEXE%" -m pip install -U yt-dlp >nul 2>&1
if errorlevel 1 goto :yt_bad
> "%DL%\ytdlp\yt-dlp.cmd" echo @echo off
>> "%DL%\ytdlp\yt-dlp.cmd" echo "%PYEXE%" -m yt_dlp %%*
echo [OK] 已生成 %DL%\ytdlp\yt-dlp.cmd（等价于 yt-dlp.exe）
goto :step8
:yt_bad
color 0E
echo [警告] yt-dlp 没装成（网络原因），可手动放进 %DL%\ytdlp
set "FAILED=1"
color 0B

rem ================= 7.5 qBittorrent（可选）=================
echo.
echo [7.5/9] qBittorrent
if "%DS_NO_QB%"=="1" (echo       已按参数跳过 qBittorrent^（DS_NO_QB=1^）& goto :qb_ok)
if exist "%BASE%\qBittorrent\qbittorrent.exe" goto :qb_ok
if "%DRYRUN%"=="1" goto :qb_ok
where winget >nul 2>&1
if errorlevel 1 goto :qb_manual
if "%DS_AUTO%"=="1" goto :qb_install
choice /c YN /n /m "      没检测到 qBittorrent，现在用 winget 装吗？(Y/N): "
if errorlevel 2 goto :qb_skip
:qb_install
winget install --id qBittorrent.qBittorrent -e --silent --accept-package-agreements --accept-source-agreements
if exist "%BASE%\qBittorrent\qbittorrent.exe" (echo [OK] qBittorrent 就位) else (echo [提示] winget 装好了但不在本目录，面板可用系统里的 qB)
goto :qb_ok
:qb_manual
echo [提示] 没有 winget，请自己装 qBittorrent（目标目录: %BASE%\qBittorrent）
goto :qb_ok
:qb_skip
echo       已跳过 qBittorrent（BT/PT 功能需要它）
:qb_ok
echo.

rem ================= 8. 配置 / 脚本 / 面板 / 快捷方式 =================
:step8
echo.
echo [8/9] 写配置与启停脚本
if "%DRYRUN%"=="1" goto :cfg_done

set "SECRET="
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [BitConverter]::ToString($b).Replace('-','').ToLower()"`) do set "SECRET=%%S"
if "%SECRET%"=="" set "SECRET=0000000000000000000000000000000000000000000000000000000000000000"
if exist "%BASE%\aria2\rpc-secret.txt" if not "%DS_FORCE%"=="1" goto :skip_conf
> "%BASE%\aria2\rpc-secret.txt" echo %SECRET%

if exist "%BASE%\aria2\aria2.conf" if not "%DS_FORCE%"=="1" (echo       [保留] 已有 aria2.conf，不覆盖& goto :after_conf)
> "%BASE%\aria2\aria2.conf" echo continue=true
>> "%BASE%\aria2\aria2.conf" echo dir=%DL%\aria2
>> "%BASE%\aria2\aria2.conf" echo input-file=%BASE%\aria2\session.txt
>> "%BASE%\aria2\aria2.conf" echo save-session=%BASE%\aria2\session.txt
>> "%BASE%\aria2\aria2.conf" echo save-session-interval=30
>> "%BASE%\aria2\aria2.conf" echo max-concurrent-downloads=3
>> "%BASE%\aria2\aria2.conf" echo split=4
>> "%BASE%\aria2\aria2.conf" echo max-connection-per-server=4
>> "%BASE%\aria2\aria2.conf" echo min-split-size=1M
>> "%BASE%\aria2\aria2.conf" echo file-allocation=none
>> "%BASE%\aria2\aria2.conf" echo log=%BASE%\logs\aria2.log
>> "%BASE%\aria2\aria2.conf" echo log-level=warn
>> "%BASE%\aria2\aria2.conf" echo enable-rpc=true
>> "%BASE%\aria2\aria2.conf" echo rpc-listen-all=false
>> "%BASE%\aria2\aria2.conf" echo rpc-listen-port=%ARIA_PORT%
>> "%BASE%\aria2\aria2.conf" echo rpc-allow-origin-all=true
>> "%BASE%\aria2\aria2.conf" echo rpc-secret=%SECRET%
>> "%BASE%\aria2\aria2.conf" echo dht-file-path=%BASE%\aria2\dht.dat
>> "%BASE%\aria2\aria2.conf" echo dht-file-path6=%BASE%\aria2\dht6.dat
:after_conf
:skip_conf

> "%BASE%\start_aria2.cmd" echo @echo off
>> "%BASE%\start_aria2.cmd" echo set "http_proxy="
>> "%BASE%\start_aria2.cmd" echo set "https_proxy="
>> "%BASE%\start_aria2.cmd" echo set "all_proxy="
>> "%BASE%\start_aria2.cmd" echo set "HTTP_PROXY="
>> "%BASE%\start_aria2.cmd" echo set "HTTPS_PROXY="
>> "%BASE%\start_aria2.cmd" echo set "ALL_PROXY="
>> "%BASE%\start_aria2.cmd" echo cd /d "%%~dp0"
>> "%BASE%\start_aria2.cmd" echo start "" /min "%%~dp0aria2\aria2c.exe" --conf-path="%%~dp0aria2\aria2.conf"
>> "%BASE%\start_aria2.cmd" echo exit /b 0

> "%BASE%\stop_aria2.cmd" echo @echo off
>> "%BASE%\stop_aria2.cmd" echo powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='aria2c.exe'\" ^| Where-Object { $_.CommandLine -like '*aria2.conf*' } ^| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
>> "%BASE%\stop_aria2.cmd" echo exit /b 0

> "%BASE%\start_ariang.cmd" echo @echo off
>> "%BASE%\start_ariang.cmd" echo cd /d "%%~dp0ariaNg"
>> "%BASE%\start_ariang.cmd" echo start "" /min python -m http.server %ARIANG_PORT% --bind 127.0.0.1
>> "%BASE%\start_ariang.cmd" echo exit /b 0

> "%BASE%\start_qbit.cmd" echo @echo off
>> "%BASE%\start_qbit.cmd" echo if exist "%%~dp0qBittorrent\qbittorrent.exe" start "" "%%~dp0qBittorrent\qbittorrent.exe" --profile="%%~dp0qBittorrent\profile"
>> "%BASE%\start_qbit.cmd" echo if not exist "%%~dp0qBittorrent\qbittorrent.exe" echo 没装 qBittorrent，请装到 %%~dp0qBittorrent
>> "%BASE%\start_qbit.cmd" echo exit /b 0

rem ---- 视频下载小工具（没有额外外壳也能用）----
> "%BASE%\ControlPanel\yt-download.cmd" echo @echo off
>> "%BASE%\ControlPanel\yt-download.cmd" echo chcp 936 ^>nul
>> "%BASE%\ControlPanel\yt-download.cmd" echo set "DOWNLOADSTACK_ROOT=%BASE%"
>> "%BASE%\ControlPanel\yt-download.cmd" echo set "DOWNLOADSTACK_DOWNLOADS=%DL%"
>> "%BASE%\ControlPanel\yt-download.cmd" echo set "YTDLP_PATH=%DL%\ytdlp\yt-dlp.exe"
>> "%BASE%\ControlPanel\yt-download.cmd" echo if exist "%BASE%\tools\video2x\video2x.exe" set "VIDEO2X_PATH=%BASE%\tools\video2x\video2x.exe"
>> "%BASE%\ControlPanel\yt-download.cmd" echo start "" "%PYEXE%" -B "%BASE%\ControlPanel\ytdl_gui.py"
>> "%BASE%\ControlPanel\yt-download.cmd" echo exit /b 0
set "CS=%BASE%\ControlPanel\config.json"
if exist "%CS%" if not "%DS_FORCE%"=="1" (echo       [保留] 已有 config.json，不覆盖& goto :after_cfg)
> "%CS%" echo {
>> "%CS%" echo   "aria2": {
>> "%CS%" echo     "host": "127.0.0.1", "port": %ARIA_PORT%,
>> "%CS%" echo     "exe": "%BASE:\=\\%\\aria2\\aria2c.exe",
>> "%CS%" echo     "conf": "%BASE:\=\\%\\aria2\\aria2.conf",
>> "%CS%" echo     "secret": "%BASE:\=\\%\\aria2\\rpc-secret.txt",
>> "%CS%" echo     "logdir": "%BASE:\=\\%\\logs"
>> "%CS%" echo   },
>> "%CS%" echo   "qbit": {
>> "%CS%" echo     "host": "127.0.0.1", "port": 8080,
>> "%CS%" echo     "user": "admin", "pass": "",
>> "%CS%" echo     "config_dir": "%BASE:\=\\%\\qBittorrent\\profile\\qBittorrent\\config",
>> "%CS%" echo     "save_dir": "%DL:\=\\%\\qBittorrent",
>> "%CS%" echo     "exe_dir": "%BASE:\=\\%\\qBittorrent"
>> "%CS%" echo   },
>> "%CS%" echo   "yt": { "bat": "%BASE:\=\\%\\ControlPanel\\yt-download.cmd", "bat2": "", "ini": "" },
>> "%CS%" echo   "ariang": { "port": %ARIANG_PORT%, "dir": "%BASE:\=\\%\\ariaNg", "script": "%BASE:\=\\%\\start_ariang.cmd" },
>> "%CS%" echo   "scripts": {
>> "%CS%" echo     "start": "%BASE:\=\\%\\start_aria2.cmd",
>> "%CS%" echo     "stop": "%BASE:\=\\%\\stop_aria2.cmd",
>> "%CS%" echo     "qbit": "%BASE:\=\\%\\start_qbit.cmd"
>> "%CS%" echo   },
>> "%CS%" echo   "paths": { "downloads": "%DL:\=\\%" },
>> "%CS%" echo   "ui": { "theme": "dark", "upscale": false }
>> "%CS%" echo }

if exist "%~dp0panel.py" copy /y "%~dp0panel.py" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0panel_ui.html" copy /y "%~dp0panel_ui.html" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0magnet_tools.py" copy /y "%~dp0magnet_tools.py" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0media_studio.py" copy /y "%~dp0media_studio.py" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0prompt_engine.py" copy /y "%~dp0prompt_engine.py" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0reader_hub.py" copy /y "%~dp0reader_hub.py" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0reader_catalog.py" copy /y "%~dp0reader_catalog.py" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0ytdl_gui.py" copy /y "%~dp0ytdl_gui.py" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0启动面板.bat" copy /y "%~dp0启动面板.bat" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0requirements.txt" copy /y "%~dp0requirements.txt" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0DownloadStackControl.exe" copy /y "%~dp0DownloadStackControl.exe" "%BASE%\ControlPanel\" >nul 2>&1
if exist "%~dp0ControlPanel\DownloadStackControl.exe" copy /y "%~dp0ControlPanel\DownloadStackControl.exe" "%BASE%\ControlPanel\" >nul 2>&1
if not exist "%BASE%\ControlPanel\DownloadStackControl.exe" goto :cfg_done

set "LNKNAME=%TMPD%\lnkname.txt"
> "%LNKNAME%" echo DownloadStack 下载控制台
powershell -NoProfile -ExecutionPolicy Bypass -Command "$n=[IO.File]::ReadAllText('%LNKNAME%',[Text.Encoding]::GetEncoding(936)).Trim(); $d=[Environment]::GetFolderPath('Desktop'); $p=Join-Path $d ($n+'.lnk'); $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($p); $s.TargetPath='%BASE%\ControlPanel\DownloadStackControl.exe'; $s.WorkingDirectory='%BASE%\ControlPanel'; $s.IconLocation='%BASE%\ControlPanel\DownloadStackControl.exe,0'; $s.Description=$n; $s.Save()"
echo [OK] 桌面快捷方式已创建
:after_cfg
:cfg_done
echo [OK] aria2.conf / config.json / 启停脚本 / 随机密钥 已处理（已有的不会覆盖）

rem ================= 9. 自检 =================
echo.
echo [9/9] 自检
set "MISS=0"
if exist "%BASE%\aria2\aria2c.exe" (echo   [OK] aria2c.exe) else (echo   [缺失] aria2c.exe& set "MISS=1")
if exist "%BASE%\ariaNg\index.html" (echo   [OK] ariaNg\index.html) else (echo   [缺失] ariaNg& set "MISS=1")
if exist "%DL%\ytdlp\yt-dlp.exe" (echo   [OK] yt-dlp.exe) else (if exist "%DL%\ytdlp\yt-dlp.cmd" (echo   [OK] yt-dlp.cmd^(pip 版^)) else (echo   [缺失] yt-dlp& set "MISS=1"))
if exist "%BASE%\ControlPanel\panel.py" (echo   [OK] 面板源码) else (echo   [提示] 面板未就位)
if exist "%BASE%\qBittorrent\qbittorrent.exe" (echo   [OK] qBittorrent) else (echo   [提示] qBittorrent 请自己装到 %BASE%\qBittorrent)
echo       服务端口: aria2=%ARIA_PORT%  AriaNg=%ARIANG_PORT%

if "%DRYRUN%"=="1" goto :final
set "MSGF=%TMPD%\msg.txt"
if "%MISS%"=="0" (
  > "%MSGF%" echo 安装完成
  >> "%MSGF%" echo.
  >> "%MSGF%" echo 程序: %BASE%
  >> "%MSGF%" echo 下载: %DL%
  >> "%MSGF%" echo 端口: aria2 %ARIA_PORT% / AriaNg %ARIANG_PORT%
) else (
  > "%MSGF%" echo 安装完成，但有组件缺失
  >> "%MSGF%" echo.
  >> "%MSGF%" echo 看窗口里的 [缺失]/[提示] 行补齐后重跑
)
call :msgbox "%MSGF%" "DownloadStack 安装结果"

if "%DS_AUTO%"=="1" goto :final
echo.
echo 设置开机自启？（Y/N，默认 N）
choice /c YN /n /m "  "
if errorlevel 2 goto :final
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v DownloadStackControl /t REG_SZ /d "\"%BASE%\ControlPanel\DownloadStackControl.exe\"" /f >nul 2>&1
echo [OK] 已加入开机自启

:final
echo.
echo ============================================================
echo   安装位置
echo     程序: %BASE%
echo     下载: %DL%
echo     端口: aria2 %ARIA_PORT% / AriaNg %ARIANG_PORT%
echo   下一步
echo     1) 双击 "%BASE%\ControlPanel\启动面板.bat"
echo     2) 面板点「启动 Aria2 + AriaNg」
echo ============================================================
if "%FAILED%"=="1" color 0E
if "%FAILED%"=="0" color 0A
echo  完成。
color 0B
echo.
if not "%DS_AUTO%"=="1" if not "%DRYRUN%"=="1" pause
exit /b 0

rem ==================== 子过程 ====================
:envcheck
echo ==== 环境体检 ====
ver
for %%C in (powershell tar certutil curl winget python pip ffmpeg) do call :ec_one %%C
for /f "delims=" %%P in ('where python 2^>nul') do echo   python: %%P
for /f "delims=" %%P in ('where ffmpeg 2^>nul') do echo   ffmpeg: %%P
for /f "delims=" %%P in ('where winget 2^>nul') do echo   winget: %%P
exit /b 0

:ec_one
where %1 >nul 2>&1
if errorlevel 1 (echo   [缺] %1) else (echo   [OK] %1)
goto :eof

:detect
for /f "usebackq delims=" %%R in (`powershell -NoProfile -Command "$c=@(); if($env:DOWNLOADSTACK_ROOT){$c+=$env:DOWNLOADSTACK_ROOT}; $c+='D:\Tools\DownloadStack','C:\Tools\DownloadStack','E:\Tools\DownloadStack'; foreach($d in 'C','D','E','F'){ $c+=($d + ':\Tools\DownloadStack') }; $seen=@{}; foreach($p in $c){ if($p -and -not $seen[$p]){ $seen[$p]=1; if(Test-Path (Join-Path $p 'aria2\aria2c.exe')){ Write-Output $p; exit 0 } } }; exit 1"`) do echo 已安装: %%R
exit /b 0

:selftest
echo [自检] 路径校验
call :st_case "n" FAIL
call :st_case "c" FAIL
call :st_case "abc\def" FAIL
call :st_case "D:\Tools\DownloadStack" PASS
call :st_case "E:\Apps\DS" PASS
call :st_case "D:\a b\c" PASS
call :st_case "D:\bad|name" FAIL
echo [自检] 完毕
exit /b 0

:st_case
call :check_abs "%~1"
set "RC=%errorlevel%"
if "%~2"=="PASS" if "%RC%"=="0" echo   [OK]   "%~1" 接受
if "%~2"=="PASS" if not "%RC%"=="0" echo   [BAD]  "%~1" 应接受却被拒
if "%~2"=="FAIL" if not "%RC%"=="0" echo   [OK]   "%~1" 拒绝
if "%~2"=="FAIL" if "%RC%"=="0" echo   [BAD]  "%~1" 应拒绝却被接受
goto :eof

:check_abs
if "%~1"=="" exit /b 1
set "CHK="
for /f "delims=" %%V in ('powershell -NoProfile -Command "$p='%~1'; if ($p -match '^[A-Za-z]:\\' -and $p -notmatch '[<>|*?]') { 'OK' } else { 'NO' }"') do set "CHK=%%V"
if "%CHK%"=="OK" exit /b 0
exit /b 1

:install_python
echo       [安装] Python ...
where winget >nul 2>&1
if errorlevel 1 goto :ip_manual
winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :ip_manual
echo       [OK] Python 已安装（重开窗口后生效）
goto :eof
:ip_manual
set "PYINS=%TEMP%\python-installer.exe"
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%PYINS%' -UseBasicParsing -TimeoutSec 900; exit 0 } catch { exit 1 }"
if errorlevel 1 (echo       [失败] 下载失败，请手动装 Python 3.10+) & goto :eof
"%PYINS%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
echo       [OK] Python 已安装（重开窗口后生效）
goto :eof

:install_pip
if not defined PYEXE goto :eof
echo       [安装] pip 依赖 ...
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install "flet==1.1.3" "requests>=2.31"
if errorlevel 1 (
  echo       [重试] 换清华镜像 ...
  "%PYEXE%" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "flet==1.1.3" "requests>=2.31"
)
goto :eof

:install_ffmpeg
echo       [安装] ffmpeg ...
set "FFZIP=%TEMP%\ds_ffmpeg.zip"
set "FFTMP=%TEMP%\ds_ff"
set "FFDST=%BASE%\tools\ffmpeg"
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%FFZIP%' -UseBasicParsing -TimeoutSec 1800; exit 0 } catch { exit 1 }"
if errorlevel 1 (echo       [失败] ffmpeg 下载失败) & goto :eof
if exist "%FFTMP%" rd /s /q "%FFTMP%" >nul 2>&1
mkdir "%FFTMP%" >nul 2>&1
tar -xf "%FFZIP%" -C "%FFTMP%" >nul 2>&1
set "FFSRC="
for /d %%D in ("%FFTMP%\ffmpeg-*") do if exist "%%D\bin\ffmpeg.exe" set "FFSRC=%%D\bin"
if not defined FFSRC goto :ff_bad
if exist "%FFDST%" rd /s /q "%FFDST%" >nul 2>&1
mkdir "%FFDST%" >nul 2>&1
xcopy /e /i /y /q "%FFSRC%" "%FFDST%\bin" >nul 2>&1
if exist "%FFDST%\bin\ffmpeg.exe" (echo       [OK] ffmpeg 已放到 %FFDST%\bin) else (goto :ff_bad)
rd /s /q "%FFTMP%" >nul 2>&1
if exist "%FFZIP%" del "%FFZIP%" >nul 2>&1
goto :eof
:ff_bad
echo       [失败] ffmpeg 解压后没找到 ffmpeg.exe
rd /s /q "%FFTMP%" >nul 2>&1
if exist "%FFZIP%" del "%FFZIP%" >nul 2>&1
goto :eof

:bad_drive
color 0C
echo [失败] 盘符 %DRIVE% 不存在，请重跑并选一个真实存在的盘
color 0B
if not "%DS_AUTO%"=="1" pause
exit /b 1

:msgbox
if /I "%DS_NOMSGBOX%"=="1" goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $t=[IO.File]::ReadAllText('%~1',[Text.Encoding]::GetEncoding(936)); [void][System.Windows.Forms.MessageBox]::Show($t,'%~2','OK','Information')"
goto :eof

:take
copy /y "%~1" "%~2" >nul 2>&1
copy /y "%~dp1*.dll" "%~2" >nul 2>&1
goto :eof

:download
echo       下载 %~nx2 ...
if "%DRYRUN%"=="1" goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing -TimeoutSec 1800; exit 0 } catch { exit 1 }"
if errorlevel 1 exit /b 1
goto :eof

:verify
if "%~2"=="" goto :eof
set "GOT="
for /f "tokens=* delims=" %%H in ('certutil -hashfile "%~1" SHA256 ^| findstr /v ":"') do if not defined GOT set "GOT=%%H"
set "GOT=%GOT: =%"
if /I "%GOT%"=="%~2" echo       [校验] SHA256 一致
if /I not "%GOT%"=="%~2" echo       [校验失败] %GOT%
if /I not "%GOT%"=="%~2" exit /b 1
goto :eof

:unzip
if "%DRYRUN%"=="1" goto :eof
if exist "%~2" rd /s /q "%~2" >nul 2>&1
mkdir "%~2" >nul 2>&1
where tar >nul 2>&1
if errorlevel 1 goto :unzip_ps
tar -xf "%~1" -C "%~2"
if errorlevel 1 goto :unzip_ps
goto :eof
:unzip_ps
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Expand-Archive -LiteralPath '%~1' -DestinationPath '%~2' -ErrorAction Stop; exit 0 } catch { exit 1 }"
if errorlevel 1 exit /b 1
goto :eof
