@echo off
chcp 936 >nul
setlocal EnableExtensions
set "APP=%~dp0"
set "REPORT=%APP%diag-report.txt"
title DownloadStack Diag
> "%REPORT%" echo ===== DownloadStack diag =====
>> "%REPORT%" echo time: %date% %time%
>> "%REPORT%" echo app dir: %APP%

echo [1/6] system
>> "%REPORT%" echo.
>> "%REPORT%" echo [system]
ver >> "%REPORT%" 2>&1

echo [2/6] python
set "PY="
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
>> "%REPORT%" echo.
>> "%REPORT%" echo [python]
if not defined PY (
  >> "%REPORT%" echo NOT FOUND python
) else (
  >> "%REPORT%" echo interp: %PY%
  %PY% -c "import sys;print('version',sys.version)" >> "%REPORT%" 2>&1
  %PY% -c "import flet;print('flet OK')" >> "%REPORT%" 2>&1
  %PY% -c "import requests;print('requests OK')" >> "%REPORT%" 2>&1
)

echo [3/6] components
>> "%REPORT%" echo.
>> "%REPORT%" echo [components]
if exist "%APP%..\aria2\aria2c.exe" (>> "%REPORT%" echo   YES aria2c) else (>> "%REPORT%" echo   NO  aria2c)
if exist "%APP%..\ariaNg\index.html" (>> "%REPORT%" echo   YES ariaNg) else (>> "%REPORT%" echo   NO  ariaNg)
if exist "%APP%panel.py" (>> "%REPORT%" echo   YES panel.py) else (>> "%REPORT%" echo   NO  panel.py)
if exist "%APP%config.json" (>> "%REPORT%" echo   YES config.json) else (>> "%REPORT%" echo   NO  config.json)
if exist "%APP%ytdl_gui.py" (>> "%REPORT%" echo   YES ytdl_gui.py) else (>> "%REPORT%" echo   NO  ytdl_gui.py)

echo [4/6] ports
>> "%REPORT%" echo.
>> "%REPORT%" echo [ports]
netstat -ano | findstr ":6800" >> "%REPORT%" 2>&1
netstat -ano | findstr ":16800" >> "%REPORT%" 2>&1
netstat -ano | findstr ":8080" >> "%REPORT%" 2>&1

echo [5/6] launcher log
>> "%REPORT%" echo.
>> "%REPORT%" echo [launcher.log tail]
if exist "%APP%logs\launcher.log" (
  type "%APP%logs\launcher.log" >> "%REPORT%" 2>&1
) else (
  >> "%REPORT%" echo none
)

echo [6/6] config
>> "%REPORT%" echo.
>> "%REPORT%" echo [config.json]
if exist "%APP%config.json" (type "%APP%config.json" >> "%REPORT%" 2>&1) else (>> "%REPORT%" echo none)

echo.
echo ============================================================
echo  done. report = %REPORT%
echo ============================================================
echo.
type "%REPORT%"
echo.
pause
endlocal
