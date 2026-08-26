# -*- coding: utf-8 -*-
import io
prematch = r'''# 每5分钟: 赛前30分钟定点拉取(由计划任务触发)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
cd "D:\足球分析"
python prematch_pull.py *>> "D:\足球分析\analysis_records\prematch_pull.log"
'''
live30 = r'''# 每30分钟拉取: BSD临场窗口 + the-odds全量快照(配额保护)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$log = "D:\足球分析\analysis_records\live_pull_30min.log"
cd "D:\足球分析"
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 拉取开始 ===" | Out-File -Append -Encoding utf8 $log
python form_phase0\_fetch_live_window.py --min 5 --max 150 *>> $log
python prediction_v2\fetch_live_odds.py *>> $log
"=== 拉取完成 ===" | Out-File -Append -Encoding utf8 $log
'''
io.open(r"D:\足球分析\prematch_pull_once.ps1", "w", encoding="utf-8-sig").write(prematch)
io.open(r"D:\足球分析\live_pull_every30.ps1", "w", encoding="utf-8-sig").write(live30)
print("两个 ps1 已用 UTF-8 BOM 重写")
