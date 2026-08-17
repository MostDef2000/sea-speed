Sea Speed Windows local tooling — DEPRECATED / NON-PRODUCTION

Windows Worker is no longer a supported Sea Speed production/runtime contour.
The canonical analytics runtime is Ubuntu Worker/relay under deploy/worker/ubuntu/.

These BAT/CMD files are retained only for historical compatibility and optional local troubleshooting. They are not packaged by canonical CI, are not a release target, do not require production authorization, and do not count as runtime acceptance evidence.

Historical local path:
D:\sea-speed\

Retained local helpers may include:
- run_event_worker_forever.cmd
- start_worker.cmd
- stop_worker.cmd
- restart_worker.cmd
- status_worker.cmd
- update_worker.cmd

Do not interpret the presence or successful execution of these files as a supported Windows production deployment. Historical Windows Issue/PR/package/process evidence remains audit history only.

For supported production Worker deployment and rollback use repository-owned Ubuntu paths under deploy/worker/ubuntu/ and the canonical delivery policy.
