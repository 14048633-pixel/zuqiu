# 48h 后台守护: 每30分钟拉临场快照, 08:45 后结算复盘
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$log = "D:\足球分析\analysis_records\watchdog_48h_0831.log"
$snapDeadline = Get-Date "2026-08-18 08:45:00"
$settleDone = $false
cd "D:\足球分析"

function Log($msg) {
    $line = "$(Get-Date -Format 'MM-dd HH:mm:ss') $msg"
    Write-Output $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

Log "守护启动, 快照截止 08:45"
while ((Get-Date) -lt $snapDeadline) {
    Log "---- 拉取临场快照窗口 ----"
    python form_phase0\_fetch_live_window.py --min 5 --max 150 *>> $log
    Log "---- 快照完成, 休眠30分钟 ----"
    Start-Sleep -Seconds 1800
}

Log "到达 08:45, 开始结算复盘"
python form_phase0\_settle_48h.py --date 2026-08-18 *>> $log
Log "结算完成, 守护退出"
