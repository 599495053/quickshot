param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$')]
    [string]$Version,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VersionPattern = '\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?'

function Get-PreservedUtf8Encoding {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Path).Path)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    return New-Object System.Text.UTF8Encoding($hasBom)
}

function Update-TextFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Replacement,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $text = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).Path, [System.Text.Encoding]::UTF8)
    $options = [System.Text.RegularExpressions.RegexOptions]::Multiline
    $matches = [System.Text.RegularExpressions.Regex]::Matches($text, $Pattern, $options)
    if ($matches.Count -eq 0) {
        throw "Could not find $Label in $Path"
    }

    $updated = [System.Text.RegularExpressions.Regex]::Replace($text, $Pattern, $Replacement, $options)
    if ($updated -eq $text) {
        Write-Host "OK: $Path ($Label already $Version)"
        return
    }

    if ($CheckOnly) {
        throw "$Path is not synchronized: $Label should be $Version"
    }

    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    [System.IO.File]::WriteAllText($resolvedPath, $updated, (Get-PreservedUtf8Encoding $Path))
    Write-Host "Updated: $Path ($Label)"
}

Update-TextFile "pyproject.toml" '^(version\s*=\s*)"[^"]+"' "`$1`"$Version`"" "project version"
Update-TextFile "quickshot\utils.py" '^(APP_VERSION\s*=\s*)"[^"]+"' "`$1`"$Version`"" "APP_VERSION"
Update-TextFile "QuickShot.iss" '^(AppVersion\s*=\s*).+$' "`${1}$Version" "Inno AppVersion"
Update-TextFile "QuickShot.iss" '^(OutputBaseFilename\s*=\s*)QuickShot-.+-Setup$' "`${1}QuickShot-$Version-Setup" "Inno output filename"
Update-TextFile "README.md" "^(#\s+QuickShot\s+V)$VersionPattern" "`${1}$Version" "README title version"
Update-TextFile "RELEASE_CHECKLIST.md" '^Version:\s*.+$' "Version: $Version" "release checklist version"
Update-TextFile "RELEASE_CHECKLIST.md" ('(Output:\s*`installer_output\\)QuickShot-' + $VersionPattern + '-Setup') "`${1}QuickShot-$Version-Setup" "release checklist installer output"
Update-TextFile "RELEASE_CHECKLIST.md" ('(Downloaded\s+`)QuickShot-' + $VersionPattern + '-Setup') "`${1}QuickShot-$Version-Setup" "release checklist downloaded installer"
Update-TextFile "RELEASE_CHECKLIST.md" ('(Publish\s+`installer_output\\)QuickShot-' + $VersionPattern + '-Setup') "`${1}QuickShot-$Version-Setup" "release checklist published installer"
Update-TextFile "RELEASE_CHECKLIST.md" ('(Manifest:\s*`installer_output\\)QuickShot-' + $VersionPattern + '-release') "`${1}QuickShot-$Version-release" "release checklist manifest output"
Update-TextFile "RELEASE_CHECKLIST.md" ('(Downloaded\s+`)QuickShot-' + $VersionPattern + '-release') "`${1}QuickShot-$Version-release" "release checklist downloaded manifest"

Write-Host ""
if ($CheckOnly) {
    Write-Host "Version references are synchronized: $Version" -ForegroundColor Green
}
else {
    Write-Host "Version references updated to $Version" -ForegroundColor Green
    Write-Host "Next: run .\scripts\release.ps1 -SkipInstall -Clean"
}
