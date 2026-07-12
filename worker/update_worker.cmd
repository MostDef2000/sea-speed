@echo off
setlocal

cd /d D:\sea-speed

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\sea-speed\update_worker.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo Sea Speed worker update completed successfully.
) else (
  echo Sea Speed worker update failed with exit code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
