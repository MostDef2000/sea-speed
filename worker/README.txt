Sea Speed worker BAT files

Copy these files into:
D:\sea-speed\

Files:
1. run_event_worker_forever.cmd
   Main loop. Starts the Python worker and restarts it if FFmpeg stream ends.
   Now supports stop_worker.flag.

2. start_worker.cmd
   Starts worker in a new window.

3. stop_worker.cmd
   Stops worker and prevents the loop from restarting it.

4. restart_worker.cmd
   Stops then starts worker again.

5. status_worker.cmd
   Shows current worker-related processes.

Recommended usage:
- Double-click start_worker.cmd to start.
- Double-click stop_worker.cmd to stop.
- Double-click restart_worker.cmd to restart.
- Double-click status_worker.cmd to check status.

If Windows SmartScreen warns about downloaded .cmd files, open each file in Notepad and confirm the content before running.
