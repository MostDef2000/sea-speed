@echo off
setlocal

cd /d D:\sea-speed

echo Restarting Sea Speed worker...
echo.

call "D:\sea-speed\stop_worker.cmd"

timeout /t 3 /nobreak >nul

if exist "D:\sea-speed\stop_worker.flag" del /f /q "D:\sea-speed\stop_worker.flag"

start "Sea Speed Worker" cmd /k "D:\sea-speed\run_event_worker_forever.cmd"

echo Worker restart command sent.
pause
