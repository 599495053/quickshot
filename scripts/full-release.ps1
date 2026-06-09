param(
    [switch]$Clean,
    [switch]$SkipBuild,
    [switch]$SkipInstaller,
    [switch]$SkipInstall,
    [switch]$NoSmokeTest,
    [switch]$DesktopWorkflowTest,
    [switch]$Install,
    [string]$InstallDir,
    [int]$LaunchSeconds = 5,
    [string]$InnoSetupCompiler,
    [switch]$Sign,
    [string]$SignToolPath,
    [string]$CertificateThumbprint,
    [string]$CertificateFile,
    [string]$CertificatePasswordEnvVar = "QUICKSHOT_SIGNING_PASSWORD",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Body
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Body
    Write-Host "OK: $Name" -ForegroundColor Green
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath exited with code $LASTEXITCODE"
    }
}

function Get-RegexValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $options = [System.Text.RegularExpressions.RegexOptions]::Multiline
    $match = [System.Text.RegularExpressions.Regex]::Match($text, $Pattern, $options)
    if (-not $match.Success) {
        throw "Could not find $Label in $Path"
    }
    return $match.Groups[1].Value
}

function Get-ManifestValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Key
    )

    $escapedKey = [System.Text.RegularExpressions.Regex]::Escape($Key)
    return Get-RegexValue $Path "(?m)^$escapedKey=([^\r\n]+)\s*$" $Key
}

function Get-ArtifactInfo {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Expected artifact not found: $Path"
    }
    $item = Get-Item -LiteralPath $Path
    $hash = Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256
    [pscustomobject]@{
        Path = $item.FullName
        SizeBytes = $item.Length
        SHA256 = $hash.Hash
    }
}

function Stop-QuickShotProcesses {
    Get-Process -Name QuickShot -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

function Invoke-SilentInstall {
    param(
        [Parameter(Mandatory = $true)][string]$InstallerPath,
        [string]$TargetInstallDir
    )

    $args = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/CURRENTUSER",
        "/LANG=chinesesimp"
    )
    if ($TargetInstallDir) {
        $args += "/DIR=$TargetInstallDir"
    }

    $process = Start-Process -FilePath $InstallerPath -ArgumentList $args -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "Installer exited with code $($process.ExitCode)"
    }
}

function Start-InstalledQuickShot {
    param([Parameter(Mandatory = $true)][string]$ExePath)

    $process = Start-Process -FilePath $ExePath -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds $LaunchSeconds
    if ($process.HasExited) {
        throw "Installed QuickShot exited after launch with code $($process.ExitCode)"
    }
    return $process
}

$version = Get-RegexValue "pyproject.toml" '^\s*version\s*=\s*"([^"]+)"' "project version"
$installerPath = Join-Path "installer_output" "QuickShot-$version-Setup.exe"
$manifestPath = Join-Path "installer_output" "QuickShot-$version-release.txt"

Invoke-Step "Run release pipeline" {
    $releaseArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ".\scripts\release.ps1"
    )
    if ($Clean) { $releaseArgs += "-Clean" }
    if ($SkipBuild) { $releaseArgs += "-SkipBuild" }
    if ($SkipInstaller) { $releaseArgs += "-SkipInstaller" }
    if ($SkipInstall) { $releaseArgs += "-SkipInstall" }
    if (-not $NoSmokeTest) { $releaseArgs += "-SmokeTest" }
    if ($DesktopWorkflowTest) { $releaseArgs += "-DesktopWorkflowTest" }
    if ($InnoSetupCompiler) { $releaseArgs += @("-InnoSetupCompiler", $InnoSetupCompiler) }
    if ($Sign) { $releaseArgs += "-Sign" }
    if ($SignToolPath) { $releaseArgs += @("-SignToolPath", $SignToolPath) }
    if ($CertificateThumbprint) { $releaseArgs += @("-CertificateThumbprint", $CertificateThumbprint) }
    if ($CertificateFile) { $releaseArgs += @("-CertificateFile", $CertificateFile) }
    if ($CertificatePasswordEnvVar) { $releaseArgs += @("-CertificatePasswordEnvVar", $CertificatePasswordEnvVar) }
    if ($TimestampUrl) { $releaseArgs += @("-TimestampUrl", $TimestampUrl) }

    Invoke-Native "powershell" $releaseArgs
}

$exeInfo = Get-ArtifactInfo "dist\QuickShot.exe"
$installerInfo = Get-ArtifactInfo $installerPath
$resolvedManifestPath = (Resolve-Path -LiteralPath $manifestPath).Path
$manifestExeHash = (Get-ManifestValue $resolvedManifestPath "ExecutableSHA256").ToUpperInvariant()
$manifestInstallerHash = (Get-ManifestValue $resolvedManifestPath "InstallerSHA256").ToUpperInvariant()

if ($exeInfo.SHA256.ToUpperInvariant() -ne $manifestExeHash) {
    throw "Executable SHA256 mismatch between dist artifact and release manifest."
}
if ($installerInfo.SHA256.ToUpperInvariant() -ne $manifestInstallerHash) {
    throw "Installer SHA256 mismatch between setup artifact and release manifest."
}

$installedProcess = $null
if ($Install) {
    Invoke-Step "Install release artifact" {
        Stop-QuickShotProcesses
        Invoke-SilentInstall $installerInfo.Path $InstallDir

        $installedExe = if ($InstallDir) {
            Join-Path $InstallDir "QuickShot.exe"
        }
        else {
            Join-Path $env:LOCALAPPDATA "Programs\QuickShot\QuickShot.exe"
        }
        if (-not (Test-Path -LiteralPath $installedExe)) {
            throw "Installed QuickShot.exe not found: $installedExe"
        }

        $installedInfo = Get-ArtifactInfo $installedExe
        if ($installedInfo.SHA256.ToUpperInvariant() -ne $manifestExeHash) {
            throw "Installed QuickShot.exe SHA256 mismatch: expected $manifestExeHash, got $($installedInfo.SHA256)"
        }

        $script:installedProcess = Start-InstalledQuickShot $installedInfo.Path
        Write-Host "Installed EXE: $($installedInfo.Path)"
        Write-Host "Installed PID: $($script:installedProcess.Id)"
    }
}

Write-Host ""
Write-Host "Full release ready: QuickShot $version" -ForegroundColor Green
Write-Host "EXE:       $($exeInfo.Path)"
Write-Host "EXE SHA:   $($exeInfo.SHA256)"
Write-Host "Installer: $($installerInfo.Path)"
Write-Host "Setup SHA: $($installerInfo.SHA256)"
Write-Host "Manifest:  $resolvedManifestPath"
