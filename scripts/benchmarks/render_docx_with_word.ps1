param(
    [Parameter(Mandatory = $true)][string]$InputRoot,
    [string]$OutputName = "rendered-word"
)

$ErrorActionPreference = "Stop"
$inputPath = (Resolve-Path -LiteralPath $InputRoot).Path
$wordPath = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE").'(default)'
$wordFile = Get-Item -LiteralPath $wordPath
$word = $null
$records = [System.Collections.Generic.List[object]]::new()

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.ScreenUpdating = $false
    $word.AutomationSecurity = 3

    $docxFiles = Get-ChildItem -LiteralPath $inputPath -Recurse -File -Filter "*.docx" | Sort-Object FullName
    foreach ($file in $docxFiles) {
        $outputDir = Join-Path $file.DirectoryName $OutputName
        New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
        $pdfPath = Join-Path $outputDir ([System.IO.Path]::GetFileNameWithoutExtension($file.Name) + ".pdf")
        $document = $word.Documents.Open($file.FullName, $false, $true, $false)
        try {
            $pages = $document.ComputeStatistics(2)
            $document.ExportAsFixedFormat($pdfPath, 17)
        }
        finally {
            $document.Close(0)
            [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null
        }
        $records.Add([pscustomobject]@{
            docx = $file.FullName.Substring($inputPath.Length).TrimStart('\', '/')
            pdf = [System.IO.Path]::GetRelativePath($inputPath, $pdfPath)
            page_count = [int]$pages
            pdf_bytes = (Get-Item -LiteralPath $pdfPath).Length
        })
    }
}
finally {
    if ($word -ne $null) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$manifest = [pscustomobject]@{
    renderer = "Microsoft Word"
    word_version = $wordFile.VersionInfo.FileVersion
    word_product_version = $wordFile.VersionInfo.ProductVersion
    page_count_source = "Word Document.ComputeStatistics(wdStatisticPages) before export"
    docs = $records
}
$manifestPath = Join-Path $inputPath "word-render-manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Get-Content -LiteralPath $manifestPath
