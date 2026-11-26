@echo off
chcp 936 >nul
setlocal EnableExtensions
title DownloadStack 控制台
set "APP=%~dp0"
set "LOG=%APP%logs\launcher.log"
if not exist "%APP%logs" mkdir "%APP%logs" >nul 2>&1
echo. >> "%LOG%"
echo ===== %date% %time% ===== >> "%LOG%"
set "TEMP=%APP%cache\temp"
set "TMP=%APP%cache\temp"
set "FLET_APP_STORAGE_DATA=%APP%cache\flet"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "http_proxy="
set "https_proxy="
set "all_proxy="
if not exist "%TEMP%" mkdir "%TEMP%" >nul 2>&1
if not exist "%FLET_APP_STORAGE_DATA%" mkdir "%FLET_APP_STORAGE_DATA%" >nul 2>&1
color 0B

echo ============================================================
echo    DownloadStack 控制台
echo ============================================================
echo.
echo [1/3] 环境自检

rem ---------- 安装根 ----------
set "FOUND_ROOT="
if defined DOWNLOADSTACK_ROOT if exist "%DOWNLOADSTACK_ROOT%\aria2\aria2c.exe" set "FOUND_ROOT=%DOWNLOADSTACK_ROOT%"
if not defined FOUND_ROOT if exist "%APP%..\aria2\aria2c.exe" for %%I in ("%APP%..") do set "FOUND_ROOT=%%~fI"
if not defined FOUND_ROOT if exist "%APP%aria2\aria2c.exe" set "FOUND_ROOT=%APP%"
if not defined FOUND_ROOT for %%D in (C D E F G H) do if not defined FOUND_ROOT if exist "%%D:\Tools\DownloadStack\aria2\aria2c.exe" set "FOUND_ROOT=%%D:\Tools\DownloadStack"
if defined FOUND_ROOT set "DOWNLOADSTACK_ROOT=%FOUND_ROOT%"

rem ---------- Python ----------
set "PYRUN="
set "PYVER="
if defined PYTHON_EXE if exist "%PYTHON_EXE%" set "PYRUN=%PYTHON_EXE%"
if not defined PYRUN (
  where python >nul 2>&1
  if not errorlevel 1 set "PYRUN=python"
)
if not defined PYRUN (
  where py >nul 2>&1
  if not errorlevel 1 set "PYRUN=py -3"
)

set "MISS="
set "NOTE="
if defined PYRUN (
  for /f "delims=" %%V in ('%PYRUN% -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%V"
)
if not defined PYRUN (
  set "MISS=%MISS% Python"
  echo   [缺] Python 3.10+
) else (
  echo   [OK] Python %PYVER%
)

rem ---------- 面板依赖 ----------
if defined PYRUN (
  %PYRUN% -c "import flet" >nul 2>&1
  if errorlevel 1 (set "MISS=%MISS% flet"& echo   [缺] 依赖 flet) else (echo   [OK] 依赖 flet)
  %PYRUN% -c "import requests" >nul 2>&1
  if errorlevel 1 (set "MISS=%MISS% requests"& echo   [缺] 依赖 requests) else (echo   [OK] 依赖 requests)
)

rem ---------- 组件 ----------
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
if exist "%APP%..\Downloads\ytdlp\yt-dlp.exe" set "HASYT=1"
if defined FOUND_ROOT if exist "%FOUND_ROOT%\..\Downloads\ytdlp\yt-dlp.exe" set "HASYT=1"
if defined FOUND_ROOT if exist "%FOUND_ROOT%\Downloads\ytdlp\yt-dlp.exe" set "HASYT=1"
if defined DOWNLOADSTACK_DOWNLOADS if exist "%DOWNLOADSTACK_DOWNLOADS%\ytdlp\yt-dlp.exe" set "HASYT=1"
if not defined HASYT (
  for /f "delims=" %%P in ('where yt-dlp 2^>nul') do set "HASYT=1"
)
if defined HASYT (echo   [OK] yt-dlp) else (set "MISS=%MISS% yt-dlp"& echo   [缺] yt-dlp)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  if exist "%APP%..\tools\ffmpeg\bin\ffmpeg.exe" (echo   [OK] ffmpeg^(自带^)) else (set "MISS=%MISS% ffmpeg"& echo   [缺] ffmpeg)
) else (
  echo   [OK] ffmpeg
)

where qbittorrent >nul 2>&1
if errorlevel 1 (
  if exist "%FOUND_ROOT%\qBittorrent\qbittorrent.exe" (echo   [OK] qBittorrent) else (echo   [可选] 没装 qBittorrent^(BT/PT 需要^))
) else (
  echo   [OK] qBittorrent
)

if exist "%APP%panel.py" (echo   [OK] panel.py) else (set "MISS=%MISS% panel.py"& echo   [缺] 面板文件 panel.py)
if exist "%APP%panel_ui.html" (echo   [OK] panel_ui.html) else (set "MISS=%MISS% panel_ui.html"& echo   [缺] 3D 界面文件 panel_ui.html)

echo.
echo [2/3] 结论
if "%MISS%"=="" goto :launch

color 0E
echo   缺少这些：%MISS%
color 0B
echo.
echo   可以直接让安装向导自动补齐（会逐个问你要不要装）。
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
call "%APP%install.bat"
if errorlevel 1 (
  color 0C
  echo [失败] 安装向导异常退出，日志: %LOG%
  color 0B
  pause
  exit /b 1
)

rem 装完重扫
if not exist "%APP%panel.py" (
  color 0C
  echo [失败] 装完仍找不到 panel.py，请把仓库文件解压到同一目录再试
  color 0B
  pause
  exit /b 1
)

:launch
if not exist "%APP%panel.py" (
  color 0C
  echo [失败] 当前目录没有 panel.py（%APP%）
  color 0B
  pause
  exit /b 1
)
echo.
echo [启动] %PYRUN% -B "%APP%panel.py"
echo [launcher] run %PYRUN% >> "%LOG%"
%PYRUN% -B "%APP%panel.py" 2>> "%LOG%"
set "RC=%errorlevel%"
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

:manual
echo.
echo   你可以手动处理：
echo     - Python: https://www.python.org/downloads/ ^(勾选 Add to PATH^)
echo     - 依赖:   python -m pip install -r "%APP%requirements.txt"
echo     - 组件:   运行同目录 install.bat 走一遍向导
echo.
pause
exit /b 1
