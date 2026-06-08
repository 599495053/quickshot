param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Path,
    [switch]$RequireSigned,
    [ValidateSet("Valid", "UnknownError", "NotSigned", "HashMismatch", "NotTrusted", "NotSupportedFileFormat", "Incompatible")]
    [string]$ExpectedStatus
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Test-ArtifactSignature {
    param([Parameter(Mandatory = $true)][string]$ArtifactPath)

    if (-not (Test-Path -LiteralPath $ArtifactPath)) {
        throw "Artifact not found: $ArtifactPath"
    }

    $resolvedPath = (Resolve-Path -LiteralPath $ArtifactPath).Path
    $signature = Get-AuthenticodeSignature -LiteralPath $resolvedPath
    $status = [string]$signature.Status

    Write-Host ("{0}: SignatureStatus={1}" -f $resolvedPath, $status)
    if ($signature.SignerCertificate) {
        Write-Host ("{0}: SignerThumbprint={1}" -f $resolvedPath, $signature.SignerCertificate.Thumbprint)
        Write-Host ("{0}: SignerSubject={1}" -f $resolvedPath, $signature.SignerCertificate.Subject)
    }
    if ($signature.TimeStamperCertificate) {
        Write-Host ("{0}: TimeStamperSubject={1}" -f $resolvedPath, $signature.TimeStamperCertificate.Subject)
    }

    if ($ExpectedStatus -and $status -ne $ExpectedStatus) {
        throw "Expected signature status '$ExpectedStatus' for $resolvedPath, got '$status'."
    }
    if ($RequireSigned -and $status -ne "Valid") {
        throw "Expected a valid Authenticode signature for $resolvedPath, got '$status'."
    }
}

foreach ($artifactPath in $Path) {
    Test-ArtifactSignature $artifactPath
}

Write-Host "Signature verification complete."
