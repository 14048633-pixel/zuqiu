$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location 'D:\足球分析'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = "D:\足球分析\analysis_records\carabao_live_0200_$ts.log"
& python 'D:\足球分析\_carabao_live.py' *> $log
"=== exit: $LASTEXITCODE ===" | Out-File -FilePath $log -Append -Encoding utf8
