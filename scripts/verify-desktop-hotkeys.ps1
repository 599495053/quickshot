param(
    [string]$ExePath,
    [int]$StartupSeconds = 8,
    [int]$HotkeyWaitSeconds = 8,
    [switch]$StopExisting,
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Resolve-QuickShotExe {
    param([string]$Path)

    if ($Path) {
        $candidate = $Path
    }
    elseif (Test-Path -LiteralPath (Join-Path $Root "dist\QuickShot.exe")) {
        $candidate = Join-Path $Root "dist\QuickShot.exe"
    }
    else {
        $candidate = Join-Path $env:LOCALAPPDATA "Programs\QuickShot\QuickShot.exe"
    }

    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "QuickShot executable not found: $candidate"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Get-ProcessExecutablePath {
    param([Parameter(Mandatory = $true)]$Process)

    try {
        if ($Process.Path) {
            return $Process.Path
        }
    }
    catch {
    }

    try {
        $query = "ProcessId=$($Process.Id)"
        $cim = Get-CimInstance Win32_Process -Filter $query -ErrorAction Stop
        if ($cim -and $cim.ExecutablePath) {
            return $cim.ExecutablePath
        }
    }
    catch {
    }

    return $null
}

function Stop-ProcessAndWait {
    param([Parameter(Mandatory = $true)]$Process)

    try {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
    catch {
    }

    try {
        $Process.WaitForExit(5000) | Out-Null
    }
    catch {
    }
}

function Stop-QuickShotProcessesByPath {
    param([Parameter(Mandatory = $true)][string]$ExePath)

    $expectedPath = [System.IO.Path]::GetFullPath($ExePath)
    foreach ($process in @(Get-Process -Name QuickShot -ErrorAction SilentlyContinue)) {
        $path = Get-ProcessExecutablePath $process
        if ($path -and ([System.IO.Path]::GetFullPath($path) -eq $expectedPath)) {
            Stop-ProcessAndWait $process
        }
    }
}

function Test-PathUnder {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$BasePath
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $fullBase = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\')
    return $fullPath.StartsWith($fullBase + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Read-SharedText {
    param([Parameter(Mandatory = $true)][string]$Path)

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
        $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true)
        return $reader.ReadToEnd()
    }
    finally {
        $stream.Dispose()
    }
}

function Wait-LogPattern {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        $Process
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if ($Process -and $Process.HasExited) {
            throw "QuickShot exited before '$Label' was observed. ExitCode=$($Process.ExitCode)"
        }

        $text = Read-SharedText $Path
        if ($text -match $Pattern) {
            return $true
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "Timed out waiting for '$Label' in $Path"
}

function Add-DesktopInputType {
    if ("QuickShotDesktopInput" -as [type]) {
        return
    }

    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class QuickShotDesktopInput
{
    private const uint INPUT_KEYBOARD = 1;
    private const uint KEYEVENTF_KEYUP = 0x0002;

    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT
    {
        public uint type;
        public InputUnion U;
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)]
        public KEYBDINPUT ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    private static void SendKeyboardInput(ushort vk, bool keyUp)
    {
        if (vk > 255)
        {
            throw new ArgumentOutOfRangeException("vk");
        }
        keybd_event((byte)vk, 0, keyUp ? KEYEVENTF_KEYUP : 0, UIntPtr.Zero);
    }

    public static void KeyDown(ushort vk)
    {
        SendKeyboardInput(vk, false);
    }

    public static void KeyUp(ushort vk)
    {
        SendKeyboardInput(vk, true);
    }

    public static void SendKey(ushort vk)
    {
        KeyDown(vk);
        KeyUp(vk);
    }

    public static bool ShowAndFocus(IntPtr hWnd)
    {
        if (hWnd == IntPtr.Zero)
        {
            return false;
        }
        ShowWindow(hWnd, 9);
        return SetForegroundWindow(hWnd);
    }
}
"@
}

function Send-KeyChord {
    param(
        [Parameter(Mandatory = $true)][UInt16[]]$Modifiers,
        [Parameter(Mandatory = $true)][UInt16]$Key
    )

    foreach ($modifier in $Modifiers) {
        [QuickShotDesktopInput]::KeyDown($modifier)
    }

    try {
        [QuickShotDesktopInput]::KeyDown($Key)
        [QuickShotDesktopInput]::KeyUp($Key)
    }
    finally {
        for ($i = $Modifiers.Count - 1; $i -ge 0; $i--) {
            [QuickShotDesktopInput]::KeyUp($Modifiers[$i])
        }
    }

    Start-Sleep -Milliseconds 300
}

function Send-VirtualKey {
    param([Parameter(Mandatory = $true)][UInt16]$Key)

    [QuickShotDesktopInput]::SendKey($Key)
    Start-Sleep -Milliseconds 300
}

function Get-ProcessMainWindowHandle {
    param([Parameter(Mandatory = $true)]$Process)

    for ($i = 0; $i -lt 40; $i++) {
        try {
            $Process.Refresh()
            if ($Process.MainWindowHandle -ne [IntPtr]::Zero) {
                return $Process.MainWindowHandle
            }
        }
        catch {
        }
        Start-Sleep -Milliseconds 250
    }
    return [IntPtr]::Zero
}

function Start-HotkeyTargetWindow {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $targetScriptPath = Join-Path $Directory "hotkey-target-window.ps1"
    $targetScript = @'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$form = New-Object System.Windows.Forms.Form
$form.Text = "QuickShot Hotkey Target"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(480, 260)
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.Text = "QuickShot desktop hotkey target"
$label.Dock = [System.Windows.Forms.DockStyle]::Fill
$label.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$label.Font = New-Object System.Drawing.Font("Segoe UI", 14)
$form.Controls.Add($label)

$form.Add_Shown({ $form.Activate() })
[System.Windows.Forms.Application]::Run($form)
'@
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($targetScriptPath, $targetScript, $utf8NoBom)
    $powershellExe = Join-Path $PSHOME "powershell.exe"
    return Start-Process -FilePath $powershellExe -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $targetScriptPath
    ) -PassThru
}

$resolvedExePath = Resolve-QuickShotExe $ExePath
$verifyRoot = Join-Path $env:TEMP ("quickshot_desktop_hotkeys_" + [guid]::NewGuid().ToString("N"))
$appDataRoot = Join-Path $verifyRoot "appdata"
$configDir = Join-Path $appDataRoot "QuickShot"
$configPath = Join-Path $configDir "config.json"
$logPath = Join-Path $configDir "debug.log"
$quickShotProcess = $null
$targetProcess = $null
$restartedExistingPaths = @()
$stoppedExistingPaths = @()
$oldAppData = $env:APPDATA
$oldDebugLog = $env:QUICKSHOT_DEBUG_LOG
$completed = $false
$result = [ordered]@{
    ExePath = $resolvedExePath
    AppDataRoot = $appDataRoot
    RegionHotkey = "Ctrl+Alt+F9"
    WindowHotkey = "Ctrl+Alt+F10"
    StoppedExistingProcessCount = 0
    RestartedExistingProcesses = 0
    StartupLogSeen = $false
    HotkeysRegistered = $false
    RegionHotkeyTriggered = $false
    RegionOverlayShown = $false
    RegionOverlayClosed = $false
    WindowHotkeyTriggered = $false
    WindowOverlayShown = $false
    LogPath = $logPath
}

try {
    Add-DesktopInputType

    $runningBefore = @(Get-Process -Name QuickShot -ErrorAction SilentlyContinue)
    if ($runningBefore.Count -gt 0 -and -not $StopExisting) {
        throw "QuickShot is already running. Close it first, or rerun with -StopExisting so the verifier can isolate global hotkeys."
    }

    if ($StopExisting) {
        foreach ($process in $runningBefore) {
            $path = Get-ProcessExecutablePath $process
            if ($path) {
                $stoppedExistingPaths += $path
            }
            Stop-ProcessAndWait $process
        }
        $stoppedExistingPaths = @($stoppedExistingPaths | Select-Object -Unique)
        $result.StoppedExistingProcessCount = $runningBefore.Count
    }

    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $verifyRoot "screenshots") | Out-Null

    $config = [ordered]@{
        save_dir = (Join-Path $verifyRoot "screenshots")
        save_dir_mode = "flat"
        save_format = "png"
        jpeg_quality = 90
        auto_copy = $false
        show_notifications = $false
        hdr_color_accurate = $false
        auto_history = $false
        history_limit = 20
        watermark_text = ""
        region_hotkey = "Ctrl+Alt+F9"
        window_hotkey = "Ctrl+Alt+F10"
        history_hotkey = ""
        pin_hotkey = ""
        ocr_hotkey = ""
        delay_seconds = 0
        workflow_auto_ocr = $false
        workflow_auto_upload = $false
        workflow_copy_markdown = $false
        workflow_uploader = "local"
        github_owner = ""
        github_repo = ""
        github_branch = "main"
        github_path_prefix = "screenshots"
        annotation_presets = @()
        snap_to_windows = $true
        snap_threshold_px = 10
        edit_tool_hotkeys = @{}
    }
    $configJson = $config | ConvertTo-Json -Depth 5
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($configPath, $configJson, $utf8NoBom)

    $env:APPDATA = $appDataRoot
    $env:QUICKSHOT_DEBUG_LOG = "1"
    $quickShotProcess = Start-Process -FilePath $resolvedExePath -PassThru -WindowStyle Hidden
    $env:APPDATA = $oldAppData
    $env:QUICKSHOT_DEBUG_LOG = $oldDebugLog

    Wait-LogPattern $logPath "QuickShotApp init done" "startup completion" $StartupSeconds $quickShotProcess | Out-Null
    $result.StartupLogSeen = $true
    Wait-LogPattern $logPath "hotkeys registered: .*region=Ctrl\+Alt\+F9; .*window=Ctrl\+Alt\+F10" "hotkey registration" $StartupSeconds $quickShotProcess | Out-Null
    $result.HotkeysRegistered = $true

    Send-KeyChord -Modifiers @([UInt16]0x11, [UInt16]0x12) -Key ([UInt16]0x78)
    Wait-LogPattern $logPath "region hotkey triggered" "region hotkey trigger" $HotkeyWaitSeconds $quickShotProcess | Out-Null
    $result.RegionHotkeyTriggered = $true
    Wait-LogPattern $logPath "region overlay shown" "region overlay display" $HotkeyWaitSeconds $quickShotProcess | Out-Null
    $result.RegionOverlayShown = $true

    Send-VirtualKey ([UInt16]0x1B)
    Wait-LogPattern $logPath "overlay closed" "region overlay close" $HotkeyWaitSeconds $quickShotProcess | Out-Null
    $result.RegionOverlayClosed = $true

    $targetProcess = Start-HotkeyTargetWindow $verifyRoot
    $handle = Get-ProcessMainWindowHandle $targetProcess
    if ($null -eq $handle -or $handle -eq [IntPtr]::Zero) {
        throw "Hotkey target window did not expose a main window."
    }
    [QuickShotDesktopInput]::ShowAndFocus($handle) | Out-Null
    Start-Sleep -Milliseconds 500

    Send-KeyChord -Modifiers @([UInt16]0x11, [UInt16]0x12) -Key ([UInt16]0x79)
    Wait-LogPattern $logPath "window hotkey triggered" "window hotkey trigger" $HotkeyWaitSeconds $quickShotProcess | Out-Null
    $result.WindowHotkeyTriggered = $true
    Wait-LogPattern $logPath "window overlay shown" "window overlay display" $HotkeyWaitSeconds $quickShotProcess | Out-Null
    $result.WindowOverlayShown = $true

    Send-VirtualKey ([UInt16]0x1B)

    $completed = $true
}
finally {
    $env:APPDATA = $oldAppData
    $env:QUICKSHOT_DEBUG_LOG = $oldDebugLog

    if ($targetProcess -and -not $targetProcess.HasExited) {
        Stop-ProcessAndWait $targetProcess
    }

    if ($quickShotProcess -and -not $quickShotProcess.HasExited) {
        Stop-ProcessAndWait $quickShotProcess
    }
    Stop-QuickShotProcessesByPath $resolvedExePath

    foreach ($path in $stoppedExistingPaths) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            try {
                Start-Process -FilePath $path -WindowStyle Hidden | Out-Null
                $restartedExistingPaths += $path
            }
            catch {
                Write-Warning "Failed to restart QuickShot process: $path"
            }
        }
    }
    $result.RestartedExistingProcesses = $restartedExistingPaths.Count

    if ($completed -and -not $KeepArtifacts -and (Test-Path -LiteralPath $verifyRoot) -and (Test-PathUnder $verifyRoot $env:TEMP)) {
        Remove-Item -LiteralPath $verifyRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($completed) {
    $result | ConvertTo-Json -Depth 4
}
