# Admin WebUI Smoke Checklist

> Goal: quick confidence pass without a JS build step. Run with admin enabled and basic auth configured.

## Setup
- Start proxy: `uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 18000`
- Ensure `ENABLE_ADMIN=1`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` (or hash), token/config files if needed.
- Optionally set `ADMIN_EVENTS_FILE` to verify persisted logs.

## Steps
1. **Dashboard load**
   - Visit `http://127.0.0.1:18000/admin` with basic auth.
   - Within 10s, summary cards show uptime, requests, errors, users, latency.
2. **User management**
   - Create a user via form (leave token blank to auto-generate). Confirm toast and token copy button works.
   - Verify row appears in table; search filters by id/name/email.
   - Click row → detail drawer shows metadata; disable then enable; reset token copies new value.
   - Delete user and confirm removal + event log entry.
3. **Metrics**
   - Trigger a couple of chat/completions requests (non-stream and stream).
   - Verify metrics table updates counts/errors, token usage, and latency column.
   - Charts (requests/errors/latency) update; click "Reset metrics" and confirm counts clear.
4. **Config/Flags**
   - Confirm admin auth flags display; if config store is set, snapshot renders path and JSON dump.
5. **Logs/Events**
   - Check recent events list reflects user actions/metrics reset.
   - If `ADMIN_EVENTS_FILE` set, confirm path is shown; click "Download events" saves NDJSON with recent entries.

## Notes
- Latency values are poll-based averages from recorded durations.
- If user management is disabled, expect disabled message; otherwise all actions should be available.
