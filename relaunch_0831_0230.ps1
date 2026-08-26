$ErrorActionPreference = 'Continue'
Set-Location 'D:\足球分析'
$log = 'D:\足球分析\analysis_records\relaunch_log_0831_0230.txt'
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 拉盘开始 ====" | Out-File $log -Encoding utf8
try { python -X utf8 prediction_v2\fetch_live_odds.py 2>&1 | Out-File $log -Append -Encoding utf8 } catch { $_ | Out-File $log -Append -Encoding utf8 }
try { python -X utf8 prediction_v2\_fetch_key_matches_odds.py 2>&1 | Out-File $log -Append -Encoding utf8 } catch { $_ | Out-File $log -Append -Encoding utf8 }
try { python -X utf8 prediction_v2\pipeline_scan.py --odds analysis_records\key_matches_odds_20260817.json --out analysis_records\pipeline_0831_0300.json 2>&1 | Out-File $log -Append -Encoding utf8 } catch { $_ | Out-File $log -Append -Encoding utf8 }
try { python -X utf8 prediction_v2\relaunch_scan.py 2>&1 | Out-File $log -Append -Encoding utf8 } catch { $_ | Out-File $log -Append -Encoding utf8 }
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 完成 ====" | Out-File $log -Append -Encoding utf8