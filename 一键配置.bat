@echo off
chcp 936 >nul
setlocal EnableExtensions
title DownloadStack 一键配置
color 0B
set "APP=%~dp0"
set "MODE=%~1"

echo ============================================================
echo    DownloadStack 一键配置
echo    图形向导：扫描 - 说明缺什么 - 你同意后自动装 - 启动
echo ============================================================
echo.

rem ---------- 1. 找 Python ----------
echo [1/3] 查找 Python
set "PY="
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if defined PY (
  for /f "delims=" %%V in ('%PY% -c "import sys;print(sys.version.split()[0])" 2^>nul') do echo       找到 Python %%V
  goto :have_py
)
echo       没找到 Python，尝试自动安装 ...
where winget >nul 2>&1
if not errorlevel 1 (
  winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
) else (
  echo       没有 winget，下载官方安装包 ...
  set "PYINS=%TEMP%\python-installer.exe"
  powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%PYINS%' -UseBasicParsing -TimeoutSec 900; exit 0 } catch { exit 1 }"
  if exist "%PYINS%" "%PYINS%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
)
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
)
if not defined PY (
  color 0C
  echo [失败] Python 没装上。请手动装 https://www.python.org/downloads/ 后重跑
  color 0B
  pause
  exit /b 1
)

:have_py
rem ---------- 2. 选模式 ----------
set "HAS_TK="
%PY% -c "import tkinter" >nul 2>&1
if not errorlevel 1 set "HAS_TK=1"

if /I "%MODE%"=="/auto" goto :run_auto
if /I "%MODE%"=="/scan" goto :run_scan
if not defined HAS_TK goto :no_tk

echo.
echo [2/3] 打开图形向导窗口 ...
echo        （窗口里点「一键配置(含环境)」即可全自动；也可先看「使用教程」）
echo.
where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" pythonw -B "%APP%setup_wizard.py"
) else (
  start "" %PY% -B "%APP%setup_wizard.py"
)
echo [3/3] 已启动。窗口关掉后如需再开：双击本文件即可
timeout /t 3 >nul
exit /b 0

:no_tk
color 0E
echo [提示] 当前 Python 没有 tkinter，图形窗口开不了，改用文本引导
color 0B
echo  （想装图形界面：重新安装 Python 时勾选 tcl/tk，或用 winget 装完整版）
echo.
goto :run_text

:run_auto
echo.
echo [2/3] 全自动配置（不弹窗）...
%PY% -B "%APP%setup_wizard.py" --auto
set "RC=%errorlevel%"
goto :done
:run_scan
%PY% -B "%APP%setup_wizard.py" --scan
set "RC=%errorlevel%"
goto :done
:run_text
echo.
echo [2/3] 文本引导 ...
%PY% -B "%APP%setup_wizard.py" --text
set "RC=%errorlevel%"

:done
echo.
echo [3/3] 完成（返回码 %RC%）
echo   下一步：双击 启动面板.bat
echo.
pause
endlocal
