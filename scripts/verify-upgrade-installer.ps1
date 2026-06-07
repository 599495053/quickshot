param(
    [string]$Version,
    [string]$InstallerPath,
    [string]$ManifestPath,
    [string]$PreviousInstallerPath,
    [string]$PreviousVersion,
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

function Resolve-InstallerPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label installer not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-ManifestInstallerHash {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Release manifest not found: $Path"
    }
    $manifestText = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $manifestMatch = [System.Text.RegularExpressions.Regex]::Match(
        $manifestText,
        '(?m)^InstallerSHA256=([A-Fa-f0-9]{64})\s*$'
    )
    if (-not $manifestMatch.Success) {
        throw "Release manifest does not contain InstallerSHA256: $Path"
    }
    return $manifestMatch.Groups[1].Value.ToUpperInvariant()
}

function Assert-SetupHash {
    param(
        [Parameter(Mandatory = $true)][string]$SetupPath,
        [Parameter(Mandatory = $true)][string]$ExpectedHash,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $setupHash = (Get-FileHash -LiteralPath $SetupPath -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($setupHash -ne $ExpectedHash.ToUpperInvariant()) {
        throw "$Label SHA256 mismatch: expected $ExpectedHash, got $setupHash"
    }
    return $setupHash
}

function Assert-DefaultInstallSideEffects {
    param(
        [Parameter(Mandatory = $true)][bool]$DesktopBefore,
        [Parameter(Mandatory = $true)][bool]$CommonDesktopBefore,
        $RunBefore,
        [Parameter(Mandatory = $true)][string]$DesktopShortcut,
        [Parameter(Mandatory = $true)][string]$CommonDesktopShortcut,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not $DesktopBefore -and (Test-Path -LiteralPath $DesktopShortcut)) {
        throw "$Label created a user desktop shortcut."
    }
    if (-not $CommonDesktopBefore -and (Test-Path -LiteralPath $CommonDesktopShortcut)) {
        throw "$Label created a public desktop shortcut."
    }
    if (-not (Test-SameValue $RunBefore (Get-RunValue))) {
        throw "$Label changed HKCU Run QuickShot entry."
    }
}

function Assert-UninstallEntry {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedInstallDir,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $entries = @(Get-QuickShotUninstallEntries)
    if ($entries.Count -ne 1) {
        throw "$Label expected exactly one QuickShot uninstall entry, found $($entries.Count)."
    }
    $entry = $entries[0]
    $displayVersion = $entry.PSObject.Properties["DisplayVersion"]
    if (-not $displayVersion -or [string]$displayVersion.Value -ne $ExpectedVersion) {
        throw "$Label uninstall DisplayVersion mismatch: expected $ExpectedVersion, got $($displayVersion.Value)"
    }
    $installLocation = $entry.PSObject.Properties["InstallLocation"]
    if ($installLocation -and $installLocation.Value) {
        $resolvedExpected = [System.IO.Path]::GetFullPath($ExpectedInstallDir).TrimEnd('\')
        $resolvedActual = [System.IO.Path]::GetFullPath([string]$installLocation.Value).TrimEnd('\')
        if (-not $resolvedActual.Equals($resolvedExpected, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "$Label uninstall InstallLocation mismatch: expected $resolvedExpected, got $resolvedActual"
        }
    }
    return $entry
}

function Write-TestConfig {
    param(
        [Parameter(Mandatory = $true)][string]$AppDataRoot,
        [Parameter(Mandatory = $true)][string]$ScenarioName
    )

    $quickShotDir = Join-Path $AppDataRoot "QuickShot"
    New-Item -ItemType Directory -Path $quickShotDir -Force | Out-Null
    $configPath = Join-Path $quickShotDir "config.json"
    $data = [ordered]@{
        save_dir = (Join-Path $AppDataRoot "Pictures")
        save_dir_mode = "flat"
        save_format = "png"
        auto_copy = $true
        show_notifications = $false
        auto_history = $true
        history_limit = 37
        region_hotkey = "Ctrl+Shift+A"
        window_hotkey = "Ctrl+Shift+W"
        workflow_uploader = "local"
        quickshot_upgrade_test_marker = $ScenarioName
    }
    $data | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $configPath -Encoding UTF8
    return $configPath
}

function Assert-TestConfigPreserved {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$ScenarioName
    )

    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        throw "$ScenarioName config was removed: $ConfigPath"
    }
    $data = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$data.quickshot_upgrade_test_marker -ne $ScenarioName) {
        throw "$ScenarioName config marker changed."
    }
    if ([int]$data.history_limit -ne 37) {
        throw "$ScenarioName config history_limit changed."
    }
    if ([string]$data.region_hotkey -ne "Ctrl+Shift+A" -or [string]$data.window_hotkey -ne "Ctrl+Shift+W") {
        throw "$ScenarioName hotkey config changed."
    }
}

function Invoke-LaunchSmokeTest {
    param(
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string]$AppDataRoot,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $previousAppData = $env:APPDATA
    $previousDebugLog = $env:QUICKSHOT_DEBUG_LOG
    $env:APPDATA = $AppDataRoot
    $env:QUICKSHOT_DEBUG_LOG = "1"
    $logPath = Join-Path $AppDataRoot "QuickShot\debug.log"
    $logOffset = 0
    if (Test-Path -LiteralPath $logPath) {
        $logOffset = (Get-Item -LiteralPath $logPath).Length
    }

    try {
        Stop-QuickShotProcesses
        $appProcess = Start-Process -FilePath $ExePath -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds $LaunchSeconds
        $runningAfterLaunch = @(Get-Process -Name QuickShot -ErrorAction SilentlyContinue)
        if ($appProcess.HasExited -and $runningAfterLaunch.Count -eq 0) {
            throw "$Label exited during launch smoke test with code $($appProcess.ExitCode)"
        }

        $newLog = Read-NewLogText $logPath $logOffset
        if ($newLog -match "UNCAUGHT EXCEPTION|THREAD EXCEPTION|CRASH|Traceback") {
            throw "$Label launch log contains crash text: $logPath"
        }
        return $newLog.Length
    }
    finally {
        Stop-QuickShotProcesses
        if ($null -eq $previousAppData) {
            Remove-Item Env:\APPDATA -ErrorAction SilentlyContinue
        }
        else {
            $env:APPDATA = $previousAppData
        }
        if ($null -eq $previousDebugLog) {
            Remove-Item Env:\QUICKSHOT_DEBUG_LOG -ErrorAction SilentlyContinue
        }
        else {
            $env:QUICKSHOT_DEBUG_LOG = $previousDebugLog
        }
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

function Invoke-Install {
    param(
        [Parameter(Mandatory = $true)][string]$SetupPath,
        [Parameter(Mandatory = $true)][string]$TargetInstallDir,
        [Parameter(Mandatory = $true)][string]$Label
    )

    Invoke-InstallerProcess $SetupPath @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CURRENTUSER",
        "/LANG=chinesesimp",
        "/DIR=$TargetInstallDir"
    ) $Label
}

function Invoke-Scenario {
    param(
        [Parameter(Mandatory = $true)][string]$ScenarioName,
        [Parameter(Mandatory = $true)][string]$BaselineInstaller,
        [Parameter(Mandatory = $true)][string]$BaselineVersion,
        [Parameter(Mandatory = $true)][string]$TargetInstaller,
        [Parameter(Mandatory = $true)][string]$TargetVersion,
        [Parameter(Mandatory = $true)][string]$ScenarioInstallDir,
        [Parameter(Mandatory = $true)][string]$ScenarioAppData,
        [Parameter(Mandatory = $true)][bool]$DesktopBefore,
        [Parameter(Mandatory = $true)][bool]$CommonDesktopBefore,
        $RunBefore,
        [Parameter(Mandatory = $true)][string]$DesktopShortcut,
        [Parameter(Mandatory = $true)][string]$CommonDesktopShortcut
    )

    New-Item -ItemType Directory -Path $ScenarioInstallDir, $ScenarioAppData -Force | Out-Null
    $configPath = Write-TestConfig $ScenarioAppData $ScenarioName
    $installedExe = Join-Path $ScenarioInstallDir "QuickShot.exe"
    $uninstallerPath = Join-Path $ScenarioInstallDir "unins000.exe"
    $scenarioUninstalled = $false

    try {
        Invoke-Install $BaselineInstaller $ScenarioInstallDir "$ScenarioName baseline install"
        if (-not (Test-Path -LiteralPath $installedExe)) {
            throw "$ScenarioName baseline QuickShot.exe not found: $installedExe"
        }
        Assert-UninstallEntry $BaselineVersion $ScenarioInstallDir "$ScenarioName baseline install" | Out-Null
        Assert-DefaultInstallSideEffects $DesktopBefore $CommonDesktopBefore $RunBefore $DesktopShortcut $CommonDesktopShortcut "$ScenarioName baseline install"
        Assert-TestConfigPreserved $configPath $ScenarioName
        $baselineExeHash = (Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToUpperInvariant()

        Invoke-Install $TargetInstaller $ScenarioInstallDir "$ScenarioName target install"
        if (-not (Test-Path -LiteralPath $installedExe)) {
            throw "$ScenarioName target QuickShot.exe not found: $installedExe"
        }
        Assert-UninstallEntry $TargetVersion $ScenarioInstallDir "$ScenarioName target install" | Out-Null
        Assert-DefaultInstallSideEffects $DesktopBefore $CommonDesktopBefore $RunBefore $DesktopShortcut $CommonDesktopShortcut "$ScenarioName target install"
        Assert-TestConfigPreserved $configPath $ScenarioName
        $targetExeHash = (Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToUpperInvariant()

        $newLogBytes = Invoke-LaunchSmokeTest $installedExe $ScenarioAppData "$ScenarioName target launch"
        if ($PrivacySelfTest) {
            Invoke-QuickShotSelfTest $installedExe "privacy-ocr-fallback"
        }
        if ($OverlaySelfTest) {
            Invoke-QuickShotSelfTest $installedExe "overlay-edit-smoke"
        }
        if ($CaptureSelfTest) {
            Invoke-QuickShotSelfTest $installedExe "capture-backend-smoke"
        }
        Assert-TestConfigPreserved $configPath $ScenarioName

        if (-not (Test-Path -LiteralPath $uninstallerPath)) {
            throw "$ScenarioName uninstaller not found: $uninstallerPath"
        }
        Invoke-InstallerProcess $uninstallerPath @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") "$ScenarioName uninstall"
        $scenarioUninstalled = $true
        Start-Sleep -Seconds 2
        Stop-QuickShotProcesses

        $remainingEntries = @(Get-QuickShotUninstallEntries)
        if ($remainingEntries.Count -gt 0) {
            throw "$ScenarioName QuickShot uninstall entry remained after uninstall."
        }
        if (Test-Path -LiteralPath $installedExe) {
            throw "$ScenarioName QuickShot.exe remained after uninstall."
        }
        if (-not (Test-SameValue $RunBefore (Get-RunValue))) {
            throw "$ScenarioName HKCU Run QuickShot entry changed after uninstall."
        }
        if (-not $DesktopBefore -and (Test-Path -LiteralPath $DesktopShortcut)) {
            throw "$ScenarioName user desktop shortcut remained after uninstall."
        }
        if (-not $CommonDesktopBefore -and (Test-Path -LiteralPath $CommonDesktopShortcut)) {
            throw "$ScenarioName public desktop shortcut remained after uninstall."
        }
        Assert-TestConfigPreserved $configPath $ScenarioName

        [pscustomobject]@{
            Scenario = $ScenarioName
            BaselineInstaller = $BaselineInstaller
            BaselineVersion = $BaselineVersion
            TargetInstaller = $TargetInstaller
            TargetVersion = $TargetVersion
            InstallDir = $ScenarioInstallDir
            AppDataRoot = $ScenarioAppData
            BaselineExeSHA256 = $baselineExeHash
            TargetExeSHA256 = $targetExeHash
            SingleUninstallEntryAfterTargetInstall = $true
            ConfigPreserved = $true
            DesktopShortcutCreatedByDefault = $false
            StartupEntryChangedByDefault = $false
            LaunchSmokePassed = $true
            PrivacyOcrFallbackSelfTestRun = [bool]$PrivacySelfTest
            PrivacyOcrFallbackSelfTestPassed = [bool]$PrivacySelfTest
            OverlayEditSmokeSelfTestRun = [bool]$OverlaySelfTest
            OverlayEditSmokeSelfTestPassed = [bool]$OverlaySelfTest
            CaptureBackendSmokeSelfTestRun = [bool]$CaptureSelfTest
            CaptureBackendSmokeSelfTestPassed = [bool]$CaptureSelfTest
            NewLogBytes = $newLogBytes
            UninstallClean = $true
        }
    }
    finally {
        if (-not $scenarioUninstalled -and (Test-Path -LiteralPath $uninstallerPath)) {
            try {
                Invoke-InstallerProcess $uninstallerPath @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") "$ScenarioName cleanup uninstall"
                Start-Sleep -Seconds 2
            }
            catch {
                Write-Warning "$ScenarioName cleanup uninstall failed: $($_.Exception.Message)"
            }
        }
        Stop-QuickShotProcesses
    }
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

$currentInstaller = Resolve-InstallerPath $InstallerPath "Current"
$resolvedManifestPath = (Resolve-Path -LiteralPath $ManifestPath).Path
$currentExpectedHash = Get-ManifestInstallerHash $resolvedManifestPath
$currentHash = Assert-SetupHash $currentInstaller $currentExpectedHash "Current setup"

$previousInstaller = $null
if ($PreviousInstallerPath) {
    $previousInstaller = Resolve-InstallerPath $PreviousInstallerPath "Previous"
    if (-not $PreviousVersion) {
        $previousName = [System.IO.Path]::GetFileName($previousInstaller)
        if ($previousName -match '^QuickShot-(.+)-Setup\.exe$') {
            $PreviousVersion = $Matches[1]
        }
        else {
            throw "Pass -PreviousVersion when previous installer name is not QuickShot-<version>-Setup.exe."
        }
    }
}

$verifyRoot = Join-Path $env:TEMP ("quickshot_upgrade_verify_" + [guid]::NewGuid().ToString("N"))
$baseInstallDir = $InstallDir
if (-not $baseInstallDir) {
    $baseInstallDir = Join-Path $verifyRoot "install"
}
$appDataRoot = Join-Path $verifyRoot "appdata"

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "QuickShot.lnk"
$commonDesktopShortcut = Join-Path ([Environment]::GetFolderPath("CommonDesktopDirectory")) "QuickShot.lnk"
$shouldStopQuickShotOnExit = $false
$scenarioResults = @()

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

    $desktopBefore = Test-Path -LiteralPath $desktopShortcut
    $commonDesktopBefore = Test-Path -LiteralPath $commonDesktopShortcut
    $runBefore = Get-RunValue

    if ($previousInstaller) {
        $upgradeInstallDir = Join-Path $baseInstallDir "upgrade"
        $upgradeAppData = Join-Path $appDataRoot "upgrade"
        $scenarioResults += Invoke-Scenario `
            "previous-to-current-upgrade" `
            $previousInstaller `
            $PreviousVersion `
            $currentInstaller `
            $Version `
            $upgradeInstallDir `
            $upgradeAppData `
            $desktopBefore `
            $commonDesktopBefore `
            $runBefore `
            $desktopShortcut `
            $commonDesktopShortcut
    }

    $reinstallInstallDir = Join-Path $baseInstallDir "reinstall"
    $reinstallAppData = Join-Path $appDataRoot "reinstall"
    $scenarioResults += Invoke-Scenario `
        "same-version-reinstall" `
        $currentInstaller `
        $Version `
        $currentInstaller `
        $Version `
        $reinstallInstallDir `
        $reinstallAppData `
        $desktopBefore `
        $commonDesktopBefore `
        $runBefore `
        $desktopShortcut `
        $commonDesktopShortcut

    [pscustomobject]@{
        Version = $Version
        Installer = $currentInstaller
        Manifest = $resolvedManifestPath
        SetupSHA256 = $currentHash
        PreviousInstaller = $previousInstaller
        PreviousVersion = $PreviousVersion
        VerifyRoot = $verifyRoot
        RemovedExistingInstall = [bool]$RemoveExisting
        Scenarios = $scenarioResults
    } | ConvertTo-Json -Depth 6
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
