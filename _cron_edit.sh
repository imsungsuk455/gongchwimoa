#!/bin/bash
python3 - <<'PYEOF'
prompt = "Create one useful public-sector job content piece for followers (e.g., essential certificates for admin positions, facility job cert prep, exam tips). Research from jobs.json and web. Draft only, NEVER publish. Include title/body/hashtags in the report. Publishing happens separately after user approval on Telegram."
open("/tmp/fp.txt", "w", encoding="utf-8").write(prompt)
PYEOF
PROMPT=$(cat /tmp/fp.txt)
hermes cron edit 4b717995f801 --prompt "$PROMPT" 2>&1 | head -5