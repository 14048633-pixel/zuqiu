# 08:30 结算复盘: 拉当日赛果 -> 复盘报告
$env:PYTHONIOENCODING="utf-8"
$log = "D:\足球分析\analysis_records\settle_48h_task.log"
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 开始 ===" | Out-File -Append -Encoding utf8 $log
cd "D:\足球分析"
python form_phase0\_settle_48h.py --date 2026-08-18 *>> $log
"=== 完成 ===" | Out-File -Append -Encoding utf8 $log
