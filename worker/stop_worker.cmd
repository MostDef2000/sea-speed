@echo off
setlocal

cd /d D:\sea-speed

echo Stopping Sea Speed worker...
echo.

echo stop > "D:\sea-speed\stop_worker.flag"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$targets = Get-CimInstance Win32_Process | Where-Object { ($_.Name -in @('python.exe','pythonw.exe','cmd.exe')) -and ($_.CommandLine -like '*D:\sea-speed*') -and (($_.CommandLine -like '*hls_motion_yolo_worker_events.py*') -or ($_.CommandLine -like '*run_event_worker_forever.cmd*')) }; foreach ($p in $targets) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Host ('Stopped PID ' + $p.ProcessId + ' ' + $p.Name) } catch { Write-Host ('Could not stop PID ' + $p.ProcessId) } }"

echo.
echo Worker stop command sent.
pause
