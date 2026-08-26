# 每30分钟后台守护拉取: BSD临场窗口 + the-odds全量快照
# 停止方式: 新建 analysis_records\live_pull_watchdog.stop 文件
# 运行窗口: 仅 00:00-03:00, 其余时间直接退出(保护配额)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$h = (Get-Date).Hour
$m = (Get-Date).Minute
if ($h -gt 3 -or ($h -eq 3 -and $m -gt 0)) { exit 0 }
$log = "D:\足球分析\analysis_records\live_pull_watchdog.log"
$stopFile = "D:\足球分析\analysis_records\live_pull_watchdog.stop"
cd "D:\足球分析"
while (-not (Test-Path $stopFile)) {
    "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 拉取开始 ===" | Out-File -Append -Encoding utf8 $log
    python form_phase0\_fetch_live_window.py --min 5 --max 150 *>> $log
    python prediction_v2\fetch_live_odds.py *>> $log
    "=== 拉取完成 ===" | Out-File -Append -Encoding utf8 $log
    Start-Sleep -Seconds 1800
}
"守护退出 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -Encoding utf8 $log