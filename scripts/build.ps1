param([string]$Out = "dist")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile `
  --name DownloadStackControl --add-data "hud_assets.py;." --distpath $Out panel.py
Write-Host "built: $Out\DownloadStackControl.exe" -ForegroundColor Green
Get-FileHash "$Out\DownloadStackControl.exe" -Algorithm SHA256 | Format-List
