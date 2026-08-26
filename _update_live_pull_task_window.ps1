# 将 football_live_pull_30min 收紧为每日 00:00-03:00 窗口(每30分钟)
# 用途: 已注册旧版全天任务时, 运行本脚本一次即可(只动30分钟任务)
$ErrorActionPreference = "Stop"

$now = Get-Date
if ($now.Hour -lt 3 -or ($now.Hour -eq 3 -and $now.Minute -lt 5)) {
    $start = $now.Date
} else {
    $start = $now.Date.AddDays(1)
}
$startStr = $start.ToString("yyyy-MM-ddTHH:mm:ss")
$user = "$env:USERDOMAIN\$env:USERNAME"

$xml30 = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>football 30min full snapshot (daily 00:00-03:00)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startStr</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
      <Repetition>
        <Interval>PT30M</Interval>
        <Duration>PT3H5M</Duration>
        <StopAtDurationEnd>true</StopAtDurationEnd>
      </Repetition>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$user</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT20M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\足球分析\live_pull_every30.ps1"</Arguments>
    </Exec>
  </Actions>
</Task>
"@
Register-ScheduledTask -TaskName "football_live_pull_30min" -Xml $xml30 -Force | Out-Null
Write-Host "OK updated: football_live_pull_30min -> daily 00:00-03:00 every 30min"
Get-ScheduledTask -TaskName "football_live_pull_30min","football_prematch_pull_5min" | Select-Object TaskName, State | Format-Table -AutoSize