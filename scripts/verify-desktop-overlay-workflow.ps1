param(
    [string]$ExePath,
    [int]$StartupSeconds = 8,
    [int]$WorkflowWaitSeconds = 10,
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

function Read-TestEvents {
    param([Parameter(Mandatory = $true)][string]$Path)

    $text = Read-SharedText $Path
    if (-not $text) {
        return @()
    }

    $events = @()
    foreach ($line in ($text -split "`r?`n")) {
        if (-not $line.Trim()) {
            continue
        }
        try {
            $events += ($line | ConvertFrom-Json)
        }
        catch {
            # A writer may have flushed a partial final line. Ignore it and retry later.
        }
    }
    return $events
}

function Wait-TestEventCount {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$EventName,
        [Parameter(Mandatory = $true)][int]$MinCount,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        $Process
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if ($Process -and $Process.HasExited) {
            throw "QuickShot exited before event '$EventName' count $MinCount was observed. ExitCode=$($Process.ExitCode)"
        }

        $events = @(Read-TestEvents $Path)
        $count = @($events | Where-Object { $_.event -eq $EventName }).Count
        if ($count -ge $MinCount) {
            return $events
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "Timed out waiting for event '$EventName' count $MinCount in $Path"
}

function Read-HistoryItems {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }
    $parsed = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $parsed) {
        return @()
    }
    if ($parsed -is [System.Array]) {
        return @($parsed)
    }
    return @($parsed)
}

function Add-DesktopWorkflowInputType {
    if ("QuickShotDesktopWorkflowInput" -as [type]) {
        return
    }

    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class QuickShotDesktopWorkflowInput
{
    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    private const uint MOUSEEVENTF_LEFTUP = 0x0004;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern int GetSystemMetrics(int nIndex);

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

    public static void MoveMouse(int x, int y)
    {
        if (!SetCursorPos(x, y))
        {
            throw new InvalidOperationException("SetCursorPos failed");
        }
    }

    public static void LeftDown()
    {
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, UIntPtr.Zero);
    }

    public static void LeftUp()
    {
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, UIntPtr.Zero);
    }

    public static int Metric(int index)
    {
        return GetSystemMetrics(index);
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
        [QuickShotDesktopWorkflowInput]::KeyDown($modifier)
    }

    try {
        [QuickShotDesktopWorkflowInput]::KeyDown($Key)
        [QuickShotDesktopWorkflowInput]::KeyUp($Key)
    }
    finally {
        for ($i = $Modifiers.Count - 1; $i -ge 0; $i--) {
            [QuickShotDesktopWorkflowInput]::KeyUp($Modifiers[$i])
        }
    }

    Start-Sleep -Milliseconds 300
}

function Send-VirtualKey {
    param([Parameter(Mandatory = $true)][UInt16]$Key)

    [QuickShotDesktopWorkflowInput]::SendKey($Key)
    Start-Sleep -Milliseconds 300
}

function Send-MouseDrag {
    param(
        [Parameter(Mandatory = $true)][int]$StartX,
        [Parameter(Mandatory = $true)][int]$StartY,
        [Parameter(Mandatory = $true)][int]$EndX,
        [Parameter(Mandatory = $true)][int]$EndY
    )

    [QuickShotDesktopWorkflowInput]::MoveMouse($StartX, $StartY)
    Start-Sleep -Milliseconds 150
    [QuickShotDesktopWorkflowInput]::LeftDown()
    Start-Sleep -Milliseconds 120

    for ($i = 1; $i -le 12; $i++) {
        $x = [int][Math]::Round($StartX + (($EndX - $StartX) * $i / 12.0))
        $y = [int][Math]::Round($StartY + (($EndY - $StartY) * $i / 12.0))
        [QuickShotDesktopWorkflowInput]::MoveMouse($x, $y)
        Start-Sleep -Milliseconds 30
    }

    Start-Sleep -Milliseconds 120
    [QuickShotDesktopWorkflowInput]::LeftUp()
    Start-Sleep -Milliseconds 400
}

function Get-PrimaryDragRect {
    $left = [QuickShotDesktopWorkflowInput]::Metric(76)
    $top = [QuickShotDesktopWorkflowInput]::Metric(77)
    $width = [QuickShotDesktopWorkflowInput]::Metric(78)
    $height = [QuickShotDesktopWorkflowInput]::Metric(79)
    if ($width -le 0 -or $height -le 0) {
        $left = 0
        $top = 0
        $width = [QuickShotDesktopWorkflowInput]::Metric(0)
        $height = [QuickShotDesktopWorkflowInput]::Metric(1)
    }
    return [ordered]@{
        StartX = [int]($left + [Math]::Max(80, $width * 0.30))
        StartY = [int]($top + [Math]::Max(80, $height * 0.28))
        EndX = [int]($left + [Math]::Min($width - 80, $width * 0.62))
        EndY = [int]($top + [Math]::Min($height - 80, $height * 0.58))
        VirtualLeft = $left
        VirtualTop = $top
        VirtualWidth = $width
        VirtualHeight = $height
    }
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

function Start-WorkflowTargetWindow {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $targetScriptPath = Join-Path $Directory "workflow-target-window.ps1"
    $targetScript = @'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$form = New-Object System.Windows.Forms.Form
$form.Text = "QuickShot Workflow Target"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(620, 380)
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(248, 250, 252)

$label = New-Object System.Windows.Forms.Label
$label.Text = "QuickShot desktop workflow target"
$label.Dock = [System.Windows.Forms.DockStyle]::Fill
$label.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$label.Font = New-Object System.Drawing.Font("Segoe UI", 18)
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

function Assert-WorkflowArtifacts {
    param(
        [Parameter(Mandatory = $true)][string]$ScreenshotDir,
        [Parameter(Mandatory = $true)][string]$HistoryIndexPath,
        [Parameter(Mandatory = $true)]$Events
    )

    $saveEvents = @($Events | Where-Object { $_.event -eq "overlay_save_current" })
    if ($saveEvents.Count -lt 2) {
        throw "Expected at least two overlay_save_current events, got $($saveEvents.Count)."
    }

    foreach ($event in $saveEvents) {
        if (-not $event.filepath -or -not (Test-Path -LiteralPath $event.filepath)) {
            throw "Saved file from event does not exist: $($event.filepath)"
        }
        if ([int]$event.width -le 0 -or [int]$event.height -le 0) {
            throw "Saved event has invalid dimensions: $($event | ConvertTo-Json -Compress)"
        }
    }

    $files = @(Get-ChildItem -LiteralPath $ScreenshotDir -Filter "screenshot_*.png" -ErrorAction SilentlyContinue)
    if ($files.Count -lt 2) {
        throw "Expected at least two saved screenshots in $ScreenshotDir, got $($files.Count)."
    }

    if (-not (Test-Path -LiteralPath $HistoryIndexPath)) {
        throw "History index was not written: $HistoryIndexPath"
    }
    $history = @(Read-HistoryItems $HistoryIndexPath)
    if ($history.Count -lt 2) {
        throw "Expected at least two history entries, got $($history.Count)."
    }
}

$resolvedExePath = Resolve-QuickShotExe $ExePath
$verifyRoot = Join-Path $env:TEMP ("quickshot_desktop_overlay_workflow_" + [guid]::NewGuid().ToString("N"))
$appDataRoot = Join-Path $verifyRoot "appdata"
$configDir = Join-Path $appDataRoot "QuickShot"
$configPath = Join-Path $configDir "config.json"
$logPath = Join-Path $configDir "debug.log"
$eventPath = Join-Path $verifyRoot "events.jsonl"
$screenshotDir = Join-Path $verifyRoot "screenshots"
$historyDir = Join-Path $configDir "history"
$historyIndexPath = Join-Path $historyDir "index.json"
$quickShotProcess = $null
$targetProcess = $null
$restartedExistingPaths = @()
$stoppedExistingPaths = @()
$oldAppData = $env:APPDATA
$oldDebugLog = $env:QUICKSHOT_DEBUG_LOG
$oldTestEventsLog = $env:QUICKSHOT_TEST_EVENTS_LOG
$completed = $false
$dragRect = $null
$result = [ordered]@{
    ExePath = $resolvedExePath
    AppDataRoot = $appDataRoot
    EventPath = $eventPath
    ScreenshotDir = $screenshotDir
    HistoryIndexPath = $historyIndexPath
    RegionHotkey = "Ctrl+Alt+F9"
    WindowHotkey = "Ctrl+Alt+F10"
    StoppedExistingProcessCount = 0
    RestartedExistingProcesses = 0
    StartupLogSeen = $false
    HotkeysRegistered = $false
    RegionWorkflowCompleted = $false
    WindowWorkflowCompleted = $false
    EventCounts = @{}
    SavedScreenshotCount = 0
    HistoryItemCount = 0
    DragRect = $null
}

try {
    Add-DesktopWorkflowInputType

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

    New-Item -ItemType Directory -Force -Path $configDir, $screenshotDir | Out-Null

    $config = [ordered]@{
        save_dir = $screenshotDir
        save_dir_mode = "flat"
        save_format = "png"
        jpeg_quality = 90
        auto_copy = $false
        show_notifications = $false
        hdr_color_accurate = $false
        auto_history = $true
        history_limit = 20
        watermark_text = ""
        region_hotkey = "Ctrl+Alt+F9"
        window_hotkey = "Ctrl+Alt+F10"
        history_hotkey = ""
        pin_hotkey = ""
        ocr_hotkey = ""
        delay_seconds = 0
        workflow_auto_save = $true
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

    $targetProcess = Start-WorkflowTargetWindow $verifyRoot
    $handle = Get-ProcessMainWindowHandle $targetProcess
    if ($null -eq $handle -or $handle -eq [IntPtr]::Zero) {
        throw "Workflow target window did not expose a main window."
    }
    [QuickShotDesktopWorkflowInput]::ShowAndFocus($handle) | Out-Null
    Start-Sleep -Milliseconds 500

    $env:APPDATA = $appDataRoot
    $env:QUICKSHOT_DEBUG_LOG = "1"
    $env:QUICKSHOT_TEST_EVENTS_LOG = $eventPath
    $quickShotProcess = Start-Process -FilePath $resolvedExePath -PassThru -WindowStyle Hidden
    $env:APPDATA = $oldAppData
    $env:QUICKSHOT_DEBUG_LOG = $oldDebugLog
    $env:QUICKSHOT_TEST_EVENTS_LOG = $oldTestEventsLog

    Wait-LogPattern $logPath "QuickShotApp init done" "startup completion" $StartupSeconds $quickShotProcess | Out-Null
    $result.StartupLogSeen = $true
    Wait-LogPattern $logPath "hotkeys registered: .*region=Ctrl\+Alt\+F9; .*window=Ctrl\+Alt\+F10" "hotkey registration" $StartupSeconds $quickShotProcess | Out-Null
    $result.HotkeysRegistered = $true

    $dragRect = Get-PrimaryDragRect
    $result.DragRect = $dragRect

    [QuickShotDesktopWorkflowInput]::ShowAndFocus($handle) | Out-Null
    Start-Sleep -Milliseconds 300
    Send-KeyChord -Modifiers @([UInt16]0x11, [UInt16]0x12) -Key ([UInt16]0x78)
    Wait-TestEventCount $eventPath "region_overlay_shown" 1 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    Send-MouseDrag -StartX $dragRect.StartX -StartY $dragRect.StartY -EndX $dragRect.EndX -EndY $dragRect.EndY
    Wait-TestEventCount $eventPath "overlay_enter_edit" 1 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    Send-KeyChord -Modifiers @([UInt16]0x11) -Key ([UInt16]0x43)
    Wait-TestEventCount $eventPath "overlay_copy_current" 1 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    Send-VirtualKey ([UInt16]0x0D)
    Wait-TestEventCount $eventPath "overlay_save_current" 1 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    Wait-TestEventCount $eventPath "overlay_closed" 1 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    $result.RegionWorkflowCompleted = $true

    [QuickShotDesktopWorkflowInput]::ShowAndFocus($handle) | Out-Null
    Start-Sleep -Milliseconds 500
    Send-KeyChord -Modifiers @([UInt16]0x11, [UInt16]0x12) -Key ([UInt16]0x79)
    Wait-TestEventCount $eventPath "window_overlay_shown" 1 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    Wait-TestEventCount $eventPath "overlay_enter_edit" 2 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    Send-KeyChord -Modifiers @([UInt16]0x11) -Key ([UInt16]0x43)
    Wait-TestEventCount $eventPath "overlay_copy_current" 2 $WorkflowWaitSeconds $quickShotProcess | Out-Null
    Send-VirtualKey ([UInt16]0x0D)
    $events = Wait-TestEventCount $eventPath "overlay_save_current" 2 $WorkflowWaitSeconds $quickShotProcess
    $events = Wait-TestEventCount $eventPath "overlay_closed" 2 $WorkflowWaitSeconds $quickShotProcess
    $result.WindowWorkflowCompleted = $true
    Start-Sleep -Milliseconds 900
    $events = @(Read-TestEvents $eventPath)

    Assert-WorkflowArtifacts -ScreenshotDir $screenshotDir -HistoryIndexPath $historyIndexPath -Events $events

    $eventCounts = [ordered]@{}
    foreach ($event in $events) {
        $name = [string]$event.event
        if (-not $eventCounts.Contains($name)) {
            $eventCounts[$name] = 0
        }
        $eventCounts[$name] += 1
    }
    $result.EventCounts = $eventCounts
    $result.SavedScreenshotCount = @(Get-ChildItem -LiteralPath $screenshotDir -Filter "screenshot_*.png").Count
    $result.HistoryItemCount = @(Read-HistoryItems $historyIndexPath).Count

    $completed = $true
}
finally {
    $env:APPDATA = $oldAppData
    $env:QUICKSHOT_DEBUG_LOG = $oldDebugLog
    $env:QUICKSHOT_TEST_EVENTS_LOG = $oldTestEventsLog

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
    $result | ConvertTo-Json -Depth 6
}
