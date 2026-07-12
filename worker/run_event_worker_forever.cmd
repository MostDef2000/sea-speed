@echo off
cd /d D:\sea-speed

set "HLS_URL=https://mostdef.ru/cams/hls/cam1/index.m3u8"
set "FRAME_WIDTH=704"
set "FRAME_HEIGHT=576"
set "SAMPLE_FPS=5"
set "CAMERA_ID=cam1_road_test"

set "MODEL_NAME=yolo11s.pt"
set "YOLO_CONFIDENCE=0.25"
set "YOLO_IMAGE_SIZE=960"

set "MOTION_THRESHOLD=10"
set "MOTION_MIN_AREA=250"
set "MOTION_ACTIVE_SECONDS=8"

set "SEA_SPEED_API_URL=https://mostdef.ru/sea-speed/api/cam1/state"
set "SEA_SPEED_ROI_URL=https://mostdef.ru/sea-speed/api/cam1/roi"
set "SEA_SPEED_SPEED_CONFIG_URL=https://mostdef.ru/sea-speed/api/cam1/speed-config"
set "SEA_SPEED_SPEED_LINES_URL=https://mostdef.ru/sea-speed/api/cam1/speed-lines"

set "STATE_POST_INTERVAL_SEC=1"
set "EVENT_COOLDOWN_SEC=12"

set "ALLOW_EVENT_WITHOUT_LINE_SPEED=1"
set "MIN_EVENT_SPEED_PX_PER_SEC=1"

set "ROI_REFRESH_SEC=5"
set "SPEED_CONFIG_REFRESH_SEC=10"
set "SPEED_LINES_REFRESH_SEC=5"

set "LINE_SPEED_MIN_TRAVEL_SEC=0.3"
set "LINE_SPEED_MAX_TRAVEL_SEC=15"

set "DETECTION_TRACK_MAX_GAP_SEC=2.0"
set "DETECTION_SPEED_MIN_DT_SEC=0.05"
set "DETECTION_SPEED_MAX_DT_SEC=1.5"
set "DETECTION_SPEED_MIN_KMH=1"
set "DETECTION_SPEED_MAX_KMH=180"
set "DETECTION_SPEED_SMOOTH_SAMPLES=5"
set "LINE_SPEED_MIN_INSTANT_KMH=1"
set "LINE_SPEED_MAX_INSTANT_KMH=180"

if exist "D:\sea-speed\stop_worker.flag" del /f /q "D:\sea-speed\stop_worker.flag"

:loop
if exist "D:\sea-speed\stop_worker.flag" goto stopped

echo.
echo ==================================================
echo Sea Speed event-worker start %date% %time%
echo ==================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\sea-speed\run_worker_once.ps1"

if exist "D:\sea-speed\stop_worker.flag" goto stopped

echo.
echo Worker exited at %date% %time%
echo Restarting in 5 seconds...
timeout /t 5 /nobreak >nul

goto loop

:stopped
echo.
echo Stop flag found. Sea Speed worker loop stopped.
del /f /q "D:\sea-speed\stop_worker.flag" 2>nul
pause
