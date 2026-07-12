@echo off
setlocal

cd /d D:\sea-speed

echo Sea Speed worker processes:
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$targets = Get-CimInstance Win32_Process | Where-Object { ($_.Name -in @('python.exe','pythonw.exe','cmd.exe')) -and ($_.CommandLine -like '*D:\sea-speed*') -and (($_.CommandLine -like '*hls_motion_yolo_worker_events.py*') -or ($_.CommandLine -like '*run_event_worker_forever.cmd*')) }; if (-not $targets) { Write-Host 'No Sea Speed worker process found.' } else { $targets | Select-Object ProcessId, Name, CommandLine | Format-List }"

echo.
pause
