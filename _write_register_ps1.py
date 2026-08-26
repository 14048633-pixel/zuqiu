# -*- coding: utf-8 -*-
import io
ps1 = r'''$ErrorActionPreference = "Stop"
function New-Task($name, $script, $intervalMin) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '"')
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $intervalMin)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host ("OK registered: " + $name + " (every " + $intervalMin + " min, infinite)")
}
New-Task "football_live_pull_30min" "D:\足球分析\live_pull_every30.ps1" 30
New-Task "football_prematch_pull_5min" "D:\足球分析\prematch_pull_once.ps1" 5
Get-ScheduledTask -TaskName "football_live_pull_30min","football_prematch_pull_5min" | Select-Object TaskName, State | Format-Table -AutoSize
'''
p = r"D:\足球分析\_register_live_pull_task.ps1"
io.open(p, "w", encoding="utf-8-sig").write(ps1)
print("written, lines:", ps1.count(chr(10)))
