param(
    [Parameter(Mandatory = $true)]
    [string]$Tag,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedSha256,

    [string]$Repo = "599495053/quickshot",
    [string]$InstallerName,
    [string]$ManifestName,
    [string]$DownloadDir,
    [string]$InstallDir,
    [int]$LaunchSeconds = 6,
    [switch]$PrivacySelfTest,
    [switch]$OverlaySelfTest,
    [switch]$CaptureSelfTest,
    [switch]$RemoveExisting,
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

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

function Invoke-QuickShotSelfTest {
    param(
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string]$TestName,
        [int]$TimeoutSeconds = 45
    )

    $process = Start-Process -FilePath $ExePath -ArgumentList @("--quickshot-self-test", $TestName) -PassThru -WindowStyle Hidden
    try {
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "QuickShot self-test '$TestName' timed out after $TimeoutSeconds seconds."
        }
        if ($process.ExitCode -ne 0) {
            throw "QuickShot self-test '$TestName' failed with exit code $($process.ExitCode)."
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
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

if (-not (Get-Command "gh" -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required to download release assets."
}

if ($Tag -match '^v(.+)$') {
    $version = $Matches[1]
}
else {
    $version = $Tag
}

if (-not $InstallerName) {
    $InstallerName = "QuickShot-$version-Setup.exe"
}
if (-not $ManifestName) {
    $ManifestName = "QuickShot-$version-release.txt"
}

$verifyRoot = Join-Path $env:TEMP ("quickshot_release_verify_" + [guid]::NewGuid().ToString("N"))
if (-not $DownloadDir) {
    $DownloadDir = Join-Path $verifyRoot "download"
}
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

    New-Item -ItemType Directory -Path $DownloadDir, $InstallDir -Force | Out-Null
    Remove-Item -LiteralPath (Join-Path $DownloadDir $InstallerName) -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $DownloadDir $ManifestName) -Force -ErrorAction SilentlyContinue

    Invoke-Native "gh" @(
        "release", "download", $Tag,
        "--repo", $Repo,
        "--pattern", $InstallerName,
        "--pattern", $ManifestName,
        "--dir", $DownloadDir
    )

    $setupPath = Join-Path $DownloadDir $InstallerName
    $manifestPath = Join-Path $DownloadDir $ManifestName
    if (-not (Test-Path -LiteralPath $setupPath)) {
        throw "Downloaded setup not found: $setupPath"
    }
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Downloaded manifest not found: $manifestPath"
    }

    $setupHash = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash.ToUpperInvariant()
    $expectedHash = $ExpectedSha256.ToUpperInvariant()
    if ($setupHash -ne $expectedHash) {
        throw "Setup SHA256 mismatch: expected $expectedHash, got $setupHash"
    }

    $manifestText = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
    if ($manifestText -notmatch [regex]::Escape($expectedHash)) {
        throw "Release manifest does not contain expected installer SHA256."
    }

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
    ) "Release setup install"

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
    if ($PrivacySelfTest) {
        Invoke-QuickShotSelfTest $installedExe "privacy-ocr-fallback"
    }
    if ($OverlaySelfTest) {
        Invoke-QuickShotSelfTest $installedExe "overlay-edit-smoke"
    }
    if ($CaptureSelfTest) {
        Invoke-QuickShotSelfTest $installedExe "capture-backend-smoke"
    }

    $uninstallerPath = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path -LiteralPath $uninstallerPath)) {
        throw "Uninstaller not found: $uninstallerPath"
    }
    Invoke-InstallerProcess $uninstallerPath @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") "Release setup uninstall"
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
        Repo = $Repo
        Tag = $Tag
        Installer = $InstallerName
        DownloadDir = (Resolve-Path -LiteralPath $DownloadDir).Path
        InstallDir = $InstallDir
        RemovedExistingInstall = [bool]$RemoveExisting
        SetupSHA256 = $setupHash
        ManifestContainsSetupSHA256 = $true
        InstalledExeFound = $true
        DesktopShortcutCreatedByDefault = $false
        StartupEntryChangedByDefault = $false
        UninstallEntryCreated = $true
        LaunchSmokePassed = $true
        PrivacyOcrFallbackSelfTestRun = [bool]$PrivacySelfTest
        PrivacyOcrFallbackSelfTestPassed = [bool]$PrivacySelfTest
        OverlayEditSmokeSelfTestRun = [bool]$OverlaySelfTest
        OverlayEditSmokeSelfTestPassed = [bool]$OverlaySelfTest
        CaptureBackendSmokeSelfTestRun = [bool]$CaptureSelfTest
        CaptureBackendSmokeSelfTestPassed = [bool]$CaptureSelfTest
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
