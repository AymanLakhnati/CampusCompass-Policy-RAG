param([string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = 'Stop'
$source = Join-Path $ProjectRoot 'deliverables\CampusCompass_Technical_Report.docx'
$target = Join-Path $ProjectRoot 'deliverables\CampusCompass_Technical_Report.pdf'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $document = $word.Documents.Open($source, $false, $true)
    try { $document.ExportAsFixedFormat($target, 17) }
    finally { $document.Close($false) }
} finally { $word.Quit() }
Write-Output $target
