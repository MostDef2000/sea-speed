@echo off
setlocal

cd /d D:\sea-speed

if exist "D:\sea-speed\stop_worker.flag" del /f /q "D:\sea-speed\stop_worker.flag"

echo Starting Sea Speed worker...
echo.

start "Sea Speed Worker" cmd /k "D:\sea-speed\run_event_worker_forever.cmd"

echo Worker start command sent.
echo Check the new window named "Sea Speed Worker".
pause
