param(
    [string]$Version,
    [string]$InstallerPath,
    [string]$ManifestPath,
    [string]$InstallDir,
    [int]$LaunchSeconds = 6,
    [switch]$RemoveExisting,
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

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

function Invoke-InstallerProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "$Label failed with exit code $($process.ExitCode)"
    }
}

function Get-QuickShotUninstallEntries {
    $roots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($root in $roots) {
        Get-ItemProperty $root -ErrorAction SilentlyContinue |
            Where-Object {
                $displayName = $_.PSObject.Properties["DisplayName"]
                $displayName -and $displayName.Value -eq "QuickShot"
            } |
            Select-Object DisplayName, DisplayVersion, InstallLocation, UninstallString, PSPath
    }
}

function Stop-QuickShotProcesses {
    Get-Process -Name QuickShot -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

function Get-RunValue {
    try {
        (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name QuickShot -ErrorAction Stop).QuickShot
    }
    catch {
        $null
    }
}

function Read-NewLogText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][int64]$Offset
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite
    )
    try {
        if ($Offset -ge $stream.Length) {
            return ""
        }
        $stream.Seek($Offset, [System.IO.SeekOrigin]::Begin) | Out-Null
        $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true, 4096, $true)
        return $reader.ReadToEnd()
    }
    finally {
        $stream.Dispose()
    }
}

function Get-UninstallerPath {
    param([Parameter(Mandatory = $true)]$Entry)

    $uninstallString = $Entry.PSObject.Properties["UninstallString"]
    if (-not $uninstallString -or -not $uninstallString.Value) {
        return $null
    }
    if ([string]$uninstallString.Value -match '^"([^"]+)"') {
        return $Matches[1]
    }
    return [string]$uninstallString.Value
}

function Test-SameValue {
    param($Before, $After)

    if ($null -eq $Before -and $null -eq $After) {
        return $true
    }
    return [string]$Before -eq [string]$After
}

if (-not $Version) {
    $Version = Get-RegexValue "pyproject.toml" '^\s*version\s*=\s*"([^"]+)"' "project version"
}

if (-not $InstallerPath) {
    $InstallerPath = Join-Path "installer_output" "QuickShot-$Version-Setup.exe"
}
if (-not $ManifestPath) {
    $ManifestPath = Join-Path "installer_output" "QuickShot-$Version-release.txt"
}

if (-not (Test-Path -LiteralPath $InstallerPath)) {
    throw "Local installer not found: $InstallerPath"
}
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Local release manifest not found: $ManifestPath"
}

$setupPath = (Resolve-Path -LiteralPath $InstallerPath).Path
$resolvedManifestPath = (Resolve-Path -LiteralPath $ManifestPath).Path
$manifestText = Get-Content -LiteralPath $resolvedManifestPath -Raw -Encoding UTF8
$manifestMatch = [System.Text.RegularExpressions.Regex]::Match(
    $manifestText,
    '(?m)^InstallerSHA256=([A-Fa-f0-9]{64})\s*$'
)
if (-not $manifestMatch.Success) {
    throw "Release manifest does not contain InstallerSHA256: $resolvedManifestPath"
}
$expectedHash = $manifestMatch.Groups[1].Value.ToUpperInvariant()
$setupHash = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash.ToUpperInvariant()
if ($setupHash -ne $expectedHash) {
    throw "Local setup SHA256 mismatch: expected $expectedHash, got $setupHash"
}

$verifyRoot = Join-Path $env:TEMP ("quickshot_local_verify_" + [guid]::NewGuid().ToString("N"))
if (-not $InstallDir) {
    $InstallDir = Join-Path $verifyRoot "install"
}

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "QuickShot.lnk"
$commonDesktopShortcut = Join-Path ([Environment]::GetFolderPath("CommonDesktopDirectory")) "QuickShot.lnk"
$logPath = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "QuickShot\debug.log"
$shouldStopQuickShotOnExit = $false

try {
    $runningBefore = @(Get-Process -Name QuickShot -ErrorAction SilentlyContinue)
    $existingEntries = @(Get-QuickShotUninstallEntries)
    if (($runningBefore.Count -gt 0 -or $existingEntries.Count -gt 0) -and -not $RemoveExisting) {
        throw "QuickShot is already installed or running. Close/uninstall it first, or rerun with -RemoveExisting."
    }

    if ($RemoveExisting) {
        $shouldStopQuickShotOnExit = $true
        Stop-QuickShotProcesses
        foreach ($entry in $existingEntries) {
            $uninstaller = Get-UninstallerPath $entry
            if ($uninstaller -and (Test-Path -LiteralPath $uninstaller)) {
                Invoke-InstallerProcess $uninstaller @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") "Existing QuickShot uninstall"
            }
        }
        Start-Sleep -Seconds 2
        Stop-QuickShotProcesses
        if (@(Get-QuickShotUninstallEntries).Count -gt 0) {
            throw "Existing QuickShot uninstall entry remained after cleanup."
        }
    }

    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

    $desktopBefore = Test-Path -LiteralPath $desktopShortcut
    $commonDesktopBefore = Test-Path -LiteralPath $commonDesktopShortcut
    $runBefore = Get-RunValue

    Invoke-InstallerProcess $setupPath @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CURRENTUSER",
        "/LANG=chinesesimp",
        "/DIR=$InstallDir"
    ) "Local setup install"

    $installedExe = Join-Path $InstallDir "QuickShot.exe"
    if (-not (Test-Path -LiteralPath $installedExe)) {
        throw "Installed QuickShot.exe not found: $installedExe"
    }

    if (-not $desktopBefore -and (Test-Path -LiteralPath $desktopShortcut)) {
        throw "Default install created a user desktop shortcut."
    }
    if (-not $commonDesktopBefore -and (Test-Path -LiteralPath $commonDesktopShortcut)) {
        throw "Default install created a public desktop shortcut."
    }
    $runAfterInstall = Get-RunValue
    if (-not (Test-SameValue $runBefore $runAfterInstall)) {
        throw "Default install changed HKCU Run QuickShot entry."
    }

    $installedEntries = @(Get-QuickShotUninstallEntries)
    if ($installedEntries.Count -lt 1) {
        throw "No QuickShot uninstall entry found after install."
    }

    $shouldStopQuickShotOnExit = $true
    $logOffset = 0
    if (Test-Path -LiteralPath $logPath) {
        $logOffset = (Get-Item -LiteralPath $logPath).Length
    }

    Stop-QuickShotProcesses
    $appProcess = Start-Process -FilePath $installedExe -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds $LaunchSeconds
    $runningAfterLaunch = @(Get-Process -Name QuickShot -ErrorAction SilentlyContinue)
    if ($appProcess.HasExited -and $runningAfterLaunch.Count -eq 0) {
        throw "Installed QuickShot exited during launch smoke test with code $($appProcess.ExitCode)"
    }

    $newLog = Read-NewLogText $logPath $logOffset
    if ($newLog -match "UNCAUGHT EXCEPTION|THREAD EXCEPTION|CRASH|Traceback") {
        throw "Launch log contains crash text: $logPath"
    }

    Stop-QuickShotProcesses
    $uninstallerPath = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path -LiteralPath $uninstallerPath)) {
        throw "Uninstaller not found: $uninstallerPath"
    }
    Invoke-InstallerProcess $uninstallerPath @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") "Local setup uninstall"
    Start-Sleep -Seconds 2
    Stop-QuickShotProcesses

    $remainingEntries = @(Get-QuickShotUninstallEntries)
    if ($remainingEntries.Count -gt 0) {
        throw "QuickShot uninstall entry remained after uninstall."
    }
    if (Test-Path -LiteralPath $installedExe) {
        throw "QuickShot.exe remained after uninstall."
    }
    if (-not (Test-SameValue $runBefore (Get-RunValue))) {
        throw "HKCU Run QuickShot entry changed after uninstall."
    }
    if (-not $desktopBefore -and (Test-Path -LiteralPath $desktopShortcut)) {
        throw "User desktop shortcut remained after uninstall."
    }
    if (-not $commonDesktopBefore -and (Test-Path -LiteralPath $commonDesktopShortcut)) {
        throw "Public desktop shortcut remained after uninstall."
    }

    [pscustomobject]@{
        Version = $Version
        Installer = $setupPath
        Manifest = $resolvedManifestPath
        InstallDir = $InstallDir
        RemovedExistingInstall = [bool]$RemoveExisting
        SetupSHA256 = $setupHash
        ManifestContainsSetupSHA256 = $true
        InstalledExeFound = $true
        DesktopShortcutCreatedByDefault = $false
        StartupEntryChangedByDefault = $false
        UninstallEntryCreated = $true
        LaunchSmokePassed = $true
        NewLogBytes = $newLog.Length
        UninstallClean = $true
    } | ConvertTo-Json -Depth 4
}
finally {
    if ($shouldStopQuickShotOnExit) {
        Stop-QuickShotProcesses
    }
    if (-not $KeepArtifacts -and (Test-Path -LiteralPath $verifyRoot)) {
        $resolvedVerifyRoot = (Resolve-Path -LiteralPath $verifyRoot).Path
        $resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path
        if ($resolvedVerifyRoot.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedVerifyRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
