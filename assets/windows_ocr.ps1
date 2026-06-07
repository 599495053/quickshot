param(
    [Parameter(Mandatory=$true)][string]$ImagePath,
    [ValidateSet("Text", "Json")][string]$Output = "Text"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and
    $_.IsGenericMethodDefinition -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await-Operation($Operation, [Type]$ResultType) {
    $task = $asTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    foreach ($tag in @("zh-Hans", "en-US")) {
        $language = [Windows.Globalization.Language]::new($tag)
        if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($language)) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
            if ($null -ne $engine) {
                break
            }
        }
    }
}
if ($null -eq $engine) {
    throw "当前系统没有可用的 OCR 语言包，请在 Windows 设置中添加中文或英文语言包。"
}

$stream = $null
try {
    $file = Await-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
    $stream = Await-Operation ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
    $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    if ($Output -eq "Json") {
        $lines = @()
        foreach ($line in $result.Lines) {
            $words = @($line.Words)
            if ($words.Count -eq 0) {
                continue
            }

            $left = [double]::PositiveInfinity
            $top = [double]::PositiveInfinity
            $right = [double]::NegativeInfinity
            $bottom = [double]::NegativeInfinity
            foreach ($word in $words) {
                $rect = $word.BoundingRect
                $left = [Math]::Min($left, [double]$rect.X)
                $top = [Math]::Min($top, [double]$rect.Y)
                $right = [Math]::Max($right, [double]($rect.X + $rect.Width))
                $bottom = [Math]::Max($bottom, [double]($rect.Y + $rect.Height))
            }

            if ([double]::IsInfinity($left) -or [double]::IsInfinity($top) -or [double]::IsInfinity($right) -or [double]::IsInfinity($bottom)) {
                continue
            }

            $lines += [pscustomobject]@{
                Text = $line.Text
                BoundingBox = @($left, $top, $right, $bottom)
            }
        }
        $json = ConvertTo-Json -InputObject $lines -Compress -Depth 4
        Write-Output ([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($json)))
    }
    else {
        Write-Output ([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($result.Text)))
    }
}
finally {
    if ($null -ne $stream) {
        $stream.Dispose()
    }
}
