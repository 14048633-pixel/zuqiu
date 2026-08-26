# 48h 临场快照循环: 每30分钟跑一次, 覆盖未来150分钟窗口
$env:PYTHONIOENCODING="utf-8"
$log = "D:\足球分析\analysis_records\live_snap_task.log"
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 开始 ===" | Out-File -Append -Encoding utf8 $log
cd "D:\足球分析"
python form_phase0\_fetch_live_window.py --min 5 --max 150 *>> $log
"=== 完成 ===" | Out-File -Append -Encoding utf8 $log
