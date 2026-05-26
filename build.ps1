param(
    [switch]$SkipInstall,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if (-not $SkipInstall) {
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
}

if ($Clean) {
    Remove-Item -LiteralPath "build" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "dist" -Recurse -Force -ErrorAction SilentlyContinue
}

python -m compileall launcher.py quickshot build_config.py

$pyinstallerArgs = @("QuickShot.spec")
if ($Clean) {
    $pyinstallerArgs = @("--clean") + $pyinstallerArgs
}
python -m PyInstaller @pyinstallerArgs

$exe = Get-Item -LiteralPath "dist\QuickShot.exe"
$sizeMb = [Math]::Round($exe.Length / 1MB, 2)
Write-Host "Built $($exe.FullName) ($sizeMb MB)"
