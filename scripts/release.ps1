param(
    [switch]$SkipInstall,
    [switch]$Clean,
    [switch]$SkipBuild,
    [switch]$SkipInstaller,
    [switch]$SmokeTest,
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

function Resolve-InnoSetupCompiler {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath)) {
            throw "Inno Setup compiler not found: $RequestedPath"
        }
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }

    if ($env:ISCC -and (Test-Path -LiteralPath $env:ISCC)) {
        return (Resolve-Path -LiteralPath $env:ISCC).Path
    }

    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "ISCC.exe was not found. Install Inno Setup 6 or pass -InnoSetupCompiler <path>."
}

function Resolve-CodeSignTool {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath)) {
            throw "SignTool not found: $RequestedPath"
        }
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }

    $command = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $kitRoots = @(
        (Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"),
        (Join-Path $env:ProgramFiles "Windows Kits\10\bin")
    )
    foreach ($kitRoot in $kitRoots) {
        if (-not $kitRoot -or -not (Test-Path -LiteralPath $kitRoot)) {
            continue
        }
        $candidate = Get-ChildItem -LiteralPath $kitRoot -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "\\x64\\signtool\.exe$" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }

    throw "signtool.exe was not found. Install the Windows SDK or pass -SignToolPath <path>."
}

function Invoke-CodeSign {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Cannot sign missing file: $Path"
    }
    if ($CertificateThumbprint -and $CertificateFile) {
        throw "Use either -CertificateThumbprint or -CertificateFile, not both."
    }
    if (-not $CertificateThumbprint -and -not $CertificateFile) {
        throw "Signing requires -CertificateThumbprint or -CertificateFile."
    }

    $signtool = Resolve-CodeSignTool $SignToolPath
    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $args = @("sign", "/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256")

    if ($CertificateThumbprint) {
        $args += @("/sha1", $CertificateThumbprint)
    }
    else {
        $resolvedCertificate = (Resolve-Path -LiteralPath $CertificateFile).Path
        $args += @("/f", $resolvedCertificate)
        $password = [Environment]::GetEnvironmentVariable($CertificatePasswordEnvVar)
        if ($password) {
            $args += @("/p", $password)
        }
    }

    $args += $resolvedPath
    Invoke-Native $signtool $args

    $signature = Get-AuthenticodeSignature -LiteralPath $resolvedPath
    if ($signature.Status -ne "Valid") {
        throw "Signature verification failed for ${resolvedPath}: $($signature.Status)"
    }
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
        SizeMB = [Math]::Round($item.Length / 1MB, 2)
        SHA256 = $hash.Hash
    }
}

function Test-VersionConsistency {
    $projectVersion = Get-RegexValue "pyproject.toml" '^\s*version\s*=\s*"([^"]+)"' "project version"
    $appVersion = Get-RegexValue "quickshot\utils.py" '^\s*APP_VERSION\s*=\s*"([^"]+)"' "APP_VERSION"
    $innoVersion = Get-RegexValue "QuickShot.iss" '^\s*AppVersion\s*=\s*([^\r\n]+)' "AppVersion"
    $outputName = Get-RegexValue "QuickShot.iss" '^\s*OutputBaseFilename\s*=\s*([^\r\n]+)' "OutputBaseFilename"

    $expectedOutputName = "QuickShot-$projectVersion-Setup"
    $versions = @($projectVersion, $appVersion, $innoVersion)
    if (@($versions | Select-Object -Unique).Count -ne 1) {
        throw "Version mismatch: pyproject=$projectVersion, APP_VERSION=$appVersion, Inno=$innoVersion"
    }
    if ($outputName -ne $expectedOutputName) {
        throw "Installer output name mismatch: expected $expectedOutputName, got $outputName"
    }
    return $projectVersion
}

function Invoke-SmokeTest {
    param([Parameter(Mandatory = $true)][string]$ExePath)

    $resolvedExePath = (Resolve-Path -LiteralPath $ExePath).Path
    $logPath = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "QuickShot\debug.log"
    $previousLength = 0
    if (Test-Path -LiteralPath $logPath) {
        $previousLength = (Get-Item -LiteralPath $logPath).Length
    }

    $process = Start-Process -FilePath $resolvedExePath -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 5
    try {
        if ($process.HasExited -and $process.ExitCode -ne 0) {
            throw "QuickShot exited during smoke test with code $($process.ExitCode)"
        }

        if (Test-Path -LiteralPath $logPath) {
            $stream = [System.IO.File]::Open($logPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            try {
                if ($previousLength -lt $stream.Length) {
                    $stream.Seek($previousLength, [System.IO.SeekOrigin]::Begin) | Out-Null
                    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true, 4096, $true)
                    $newLog = $reader.ReadToEnd()
                    if ($newLog -match "UNCAUGHT EXCEPTION|THREAD EXCEPTION|CRASH|Traceback") {
                        throw "Smoke test found crash text in $logPath"
                    }
                }
            }
            finally {
                $stream.Dispose()
            }
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $process.WaitForExit(5000) | Out-Null
        }
        $processName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedExePath)
        $matchingProcesses = Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object {
            try {
                $_.Path -eq $resolvedExePath
            }
            catch {
                $false
            }
        }
        foreach ($matchingProcess in $matchingProcesses) {
            Stop-Process -Id $matchingProcess.Id -Force -ErrorAction SilentlyContinue
            $matchingProcess.WaitForExit(5000) | Out-Null
        }
    }
}

function Invoke-PackagedSelfTest {
    param(
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string]$TestName,
        [int]$TimeoutSeconds = 45
    )

    $resolvedExePath = (Resolve-Path -LiteralPath $ExePath).Path
    $process = Start-Process -FilePath $resolvedExePath -ArgumentList @("--quickshot-self-test", $TestName) -WindowStyle Hidden -PassThru
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

$version = Invoke-Step "Validate version metadata" {
    Test-VersionConsistency
}

Invoke-Step "Run static checks" {
    Invoke-Native "python" @("-m", "pyflakes", "quickshot", "launcher.py", "build_config.py")
}

Invoke-Step "Compile Python files" {
    Invoke-Native "python" @("-m", "compileall", "-q", "quickshot", "launcher.py", "build_config.py")
}

Invoke-Step "Run test suite" {
    Invoke-Native "python" @("-m", "pytest", "-q")
}

if (-not $SkipBuild) {
    Invoke-Step "Build QuickShot.exe" {
        $args = @("-ExecutionPolicy", "Bypass", "-File", ".\build.ps1")
        if ($SkipInstall) { $args += "-SkipInstall" }
        if ($Clean) { $args += "-Clean" }
        Invoke-Native "powershell" $args
    }
}

if ($Sign) {
    Invoke-Step "Sign QuickShot.exe" {
        Invoke-CodeSign "dist\QuickShot.exe"
    }
}

$exeInfo = Get-ArtifactInfo "dist\QuickShot.exe"

if (-not $SkipInstaller) {
    Invoke-Step "Build installer" {
        $iscc = Resolve-InnoSetupCompiler $InnoSetupCompiler
        Invoke-Native $iscc @("QuickShot.iss")
    }
}

$installerPath = "installer_output\QuickShot-$version-Setup.exe"

if ($Sign) {
    Invoke-Step "Sign installer" {
        Invoke-CodeSign $installerPath
    }
}

$installerInfo = Get-ArtifactInfo $installerPath

if ($SmokeTest) {
    Invoke-Step "Smoke test packaged app" {
        Invoke-SmokeTest $exeInfo.Path
    }
    Invoke-Step "Self-test privacy OCR fallback" {
        Invoke-PackagedSelfTest $exeInfo.Path "privacy-ocr-fallback"
    }
    Invoke-Step "Self-test overlay edit smoke" {
        Invoke-PackagedSelfTest $exeInfo.Path "overlay-edit-smoke"
    }
}

Invoke-Step "Write release manifest" {
    $manifestPath = Join-Path "installer_output" "QuickShot-$version-release.txt"
    $lines = @(
        "QuickShot $version",
        "GeneratedAt=$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))",
        "",
        "Executable=$($exeInfo.Path)",
        "ExecutableSizeBytes=$($exeInfo.SizeBytes)",
        "ExecutableSHA256=$($exeInfo.SHA256)",
        "",
        "Installer=$($installerInfo.Path)",
        "InstallerSizeBytes=$($installerInfo.SizeBytes)",
        "InstallerSHA256=$($installerInfo.SHA256)"
    )
    $lines | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Host "Manifest: $((Resolve-Path -LiteralPath $manifestPath).Path)"
}

Write-Host ""
Write-Host "Release ready: QuickShot $version" -ForegroundColor Green
Write-Host "EXE:       $($exeInfo.Path)"
Write-Host "EXE SHA:   $($exeInfo.SHA256)"
Write-Host "Installer: $($installerInfo.Path)"
Write-Host "Setup SHA: $($installerInfo.SHA256)"
