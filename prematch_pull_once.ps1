# 每5分钟: 赛前30分钟定点拉取(由计划任务触发)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
cd "D:\足球分析"
python prematch_pull.py *>> "D:\足球分析\analysis_records\prematch_pull.log"
