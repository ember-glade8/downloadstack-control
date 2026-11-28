@echo off
chcp 65001 >nul
setlocal EnableExtensions
title DownloadStack 控制台
set "APP=%~dp0"
color 0B

echo ============================================================
echo    DownloadStack 控制台
echo ============================================================
echo.
echo [1/3] 环境自检

rem ---------- 1. 定位安装根与面板目录（支持将本脚本放在任意快捷目录） ----------
set "FOUND_ROOT="
if defined DOWNLOADSTACK_ROOT if exist "%DOWNLOADSTACK_ROOT%\aria2\aria2c.exe" set "FOUND_ROOT=%DOWNLOADSTACK_ROOT%"
if not defined FOUND_ROOT if exist "%APP%..\aria2\aria2c.exe" for %%I in ("%APP%..") do set "FOUND_ROOT=%%~fI"
if not defined FOUND_ROOT if exist "%APP%aria2\aria2c.exe" set "FOUND_ROOT=%APP:~0,-1%"
if not defined FOUND_ROOT for %%D in (C D E F G H) do if not defined FOUND_ROOT if exist "%%D:\Tools\DownloadStack\aria2\aria2c.exe" set "FOUND_ROOT=%%D:\Tools\DownloadStack"
if defined FOUND_ROOT set "DOWNLOADSTACK_ROOT=%FOUND_ROOT%"

set "PANEL_DIR=%APP%"
if not exist "%PANEL_DIR%panel.py" if defined FOUND_ROOT if exist "%FOUND_ROOT%\ControlPanel\panel.py" set "PANEL_DIR=%FOUND_ROOT%\ControlPanel\"

set "LOG=%PANEL_DIR%logs\launcher.log"
if not exist "%PANEL_DIR%logs" mkdir "%PANEL_DIR%logs" >nul 2>&1
echo. >> "%LOG%"
echo ===== %date% %time% ===== >> "%LOG%"
set "TEMP=%PANEL_DIR%cache\temp"
set "TMP=%PANEL_DIR%cache\temp"
set "FLET_APP_STORAGE_DATA=%PANEL_DIR%cache\flet"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "http_proxy="
set "https_proxy="
set "all_proxy="
if not exist "%TEMP%" mkdir "%TEMP%" >nul 2>&1
if not exist "%FLET_APP_STORAGE_DATA%" mkdir "%FLET_APP_STORAGE_DATA%" >nul 2>&1

rem ---------- 2. 单实例保护 ----------
set "RUNNING=0"
for /f %%i in ('powershell -NoProfile -Command "(@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -match 'panel\.py' }).Count)"') do set "RUNNING=%%i"
if not "%RUNNING%"=="0" (
  echo   [提示] 控制台已在运行中，无需重复打开。
  timeout /t 2 >nul
  endlocal
  exit /b 0
)

rem ---------- 3. 查找带 flet 依赖的 Python ----------
set "PYRUN="
set "PYVER="
if defined PYTHON_EXE if exist "%PYTHON_EXE%" call :try_py "%PYTHON_EXE%"
if not defined PYRUN if defined FOUND_ROOT if exist "%FOUND_ROOT%\.venv\Scripts\python.exe" call :try_py "%FOUND_ROOT%\.venv\Scripts\python.exe"
if not defined PYRUN if exist "%PANEL_DIR%.venv\Scripts\python.exe" call :try_py "%PANEL_DIR%.venv\Scripts\python.exe"
if not defined PYRUN for %%D in (C D E F) do if not defined PYRUN for /d %%P in ("%%D:\python3*") do if not defined PYRUN if exist "%%~fP\python.exe" call :try_py "%%~fP\python.exe"
if not defined PYRUN for /d %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if not defined PYRUN if exist "%%~fP\python.exe" call :try_py "%%~fP\python.exe"
if not defined PYRUN (
  for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYRUN call :try_py "%%~fP"
)
if not defined PYRUN (
  where python >nul 2>&1
  if not errorlevel 1 set "PYRUN=python"
)

set "MISS="
if defined PYRUN (
  for /f "delims=" %%V in ('"%PYRUN%" -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%V"
)
if not defined PYRUN (
  set "MISS=%MISS% Python"
  echo   [缺] Python 3.10+
) else (
  echo   [OK] Python %PYVER% ^(%PYRUN%^)
)

rem ---------- 4. 面板依赖 ----------
if defined PYRUN (
  "%PYRUN%" -c "import flet" >nul 2>&1
  if errorlevel 1 (set "MISS=%MISS% flet"& echo   [缺] 依赖 flet) else (echo   [OK] 依赖 flet)
  "%PYRUN%" -c "import requests" >nul 2>&1
  if errorlevel 1 (set "MISS=%MISS% requests"& echo   [缺] 依赖 requests) else (echo   [OK] 依赖 requests)
)

rem ---------- 5. 组件 ----------
if defined FOUND_ROOT (echo   [OK] 安装根 %FOUND_ROOT%) else (echo   [缺] aria2 安装目录)
if defined FOUND_ROOT (
  if exist "%FOUND_ROOT%\aria2\aria2c.exe" (echo   [OK] aria2c) else (set "MISS=%MISS% aria2c"& echo   [缺] aria2c)
) else (
  set "MISS=%MISS% aria2"
)
if defined FOUND_ROOT (
  if exist "%FOUND_ROOT%\ariaNg\index.html" (echo   [OK] AriaNg) else (if exist "%FOUND_ROOT%\ariang\index.html" (echo   [OK] AriaNg) else (set "MISS=%MISS% AriaNg"& echo   [缺] AriaNg))
)
set "HASYT="
if exist "%PANEL_DIR%tools\yt-dlp.exe" set "HASYT=1"
if exist "%PANEL_DIR%YT*.bat" set "HASYT=1"
if defined FOUND_ROOT if exist "%FOUND_ROOT%\tools\yt-dlp.exe" set "HASYT=1"
if defined FOUND_ROOT if exist "%FOUND_ROOT%\..\Downloads\ytdlp\yt-dlp.exe" set "HASYT=1"
if defined FOUND_ROOT if exist "%FOUND_ROOT%\Downloads\ytdlp\yt-dlp.exe" set "HASYT=1"
if defined DOWNLOADSTACK_DOWNLOADS if exist "%DOWNLOADSTACK_DOWNLOADS%\ytdlp\yt-dlp.exe" set "HASYT=1"
if not defined HASYT (
  for /f "delims=" %%P in ('where yt-dlp 2^>nul') do set "HASYT=1"
)
if defined HASYT (echo   [OK] yt-dlp) else (echo   [可选] yt-dlp 未在默认路径检测到)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  if exist "%PANEL_DIR%tools\ffmpeg\bin\ffmpeg.exe" (echo   [OK] ffmpeg^(自带^)) else (if defined FOUND_ROOT if exist "%FOUND_ROOT%\tools\ffmpeg\bin\ffmpeg.exe" (echo   [OK] ffmpeg^(自带^)) else (echo   [可选] ffmpeg 未检测到))
) else (
  echo   [OK] ffmpeg
)

where qbittorrent >nul 2>&1
if errorlevel 1 (
  if defined FOUND_ROOT if exist "%FOUND_ROOT%\qBittorrent\qbittorrent.exe" (echo   [OK] qBittorrent) else (echo   [可选] 没装 qBittorrent^(BT/PT 需要^))
) else (
  echo   [OK] qBittorrent
)

if exist "%PANEL_DIR%panel.py" (echo   [OK] 面板文件 %PANEL_DIR%panel.py) else (set "MISS=%MISS% panel.py"& echo   [缺] 面板文件 panel.py)

echo.
echo [2/3] 结论
if "%MISS%"=="" goto :launch

color 0E
echo   缺少核心项：%MISS%
color 0B
if not exist "%PANEL_DIR%install.bat" if not exist "%APP%install.bat" goto :manual
echo.
choice /c YN /n /m "  现在运行安装向导自动安装吗？(Y/N): "
if errorlevel 2 goto :manual

echo.
echo [3/3] 调用安装向导（自动模式）...
set "DS_AUTO=1"
set "DS_NOMSGBOX=1"
if defined FOUND_ROOT (
  set "DS_BASE=%FOUND_ROOT%"
  for %%d in ("%FOUND_ROOT%") do set "DS_DL=%%~dd\Downloads"
)
if exist "%APP%install.bat" (call "%APP%install.bat") else (call "%PANEL_DIR%install.bat")
if errorlevel 1 (
  color 0C
  echo [失败] 安装向导异常退出，日志: %LOG%
  color 0B
  pause
  exit /b 1
)

:launch
if not exist "%PANEL_DIR%panel.py" (
  color 0C
  echo [失败] 找不到 panel.py（%PANEL_DIR%）
  color 0B
  pause
  exit /b 1
)
echo.
set "PYW="
for %%I in ("%PYRUN%") do if exist "%%~dpIpythonw.exe" set "PYW=%%~dpIpythonw.exe"
if /I "%~1"=="--console" set "PYW="
if defined PYW (
  echo [启动] 正在后台拉起控制台窗口 ...
  echo [launcher] start "%PYW%" -B "%PANEL_DIR%panel.py" >> "%LOG%"
  start "" /d "%PANEL_DIR%" "%PYW%" -B "%PANEL_DIR%panel.py"
  timeout /t 1 >nul
  endlocal
  exit /b 0
)
echo [启动] "%PYRUN%" -B "%PANEL_DIR%panel.py"
echo [launcher] run "%PYRUN%" >> "%LOG%"
pushd "%PANEL_DIR%"
"%PYRUN%" -B "%PANEL_DIR%panel.py" 2>> "%LOG%"
set "RC=%errorlevel%"
popd
if not "%RC%"=="0" (
  color 0C
  echo.
  echo [失败] 面板异常退出，错误码 %RC%
  echo ---- 日志最后 20 行 ----
  powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 20" 2>nul
  echo ---- 完整日志: %LOG%
  color 0B
  pause
)
endlocal
exit /b 0

:try_py
"%~1" -c "import flet, requests" >nul 2>&1
if not errorlevel 1 set "PYRUN=%~1"
goto :eof

:manual
echo.
echo   你可以手动处理：
echo     - Python: https://www.python.org/downloads/ ^(勾选 Add to PATH^)
echo     - 依赖:   python -m pip install -r "%PANEL_DIR%requirements.txt"
echo     - 组件:   运行仓库目录中的 一键配置.bat 或 install.bat
echo.
pause
endlocal
exit /b 1
