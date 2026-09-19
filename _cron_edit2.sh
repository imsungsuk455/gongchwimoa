#!/bin/bash
python3 - <<'PYEOF'
prompt = """Create ONE short follower-content piece for public-sector job seekers (e.g., essential certificates for admin/facility jobs, quick prep tips). Base it on jobs.json data. RULES: body must be max 4 lines (each line short). Structure: hook line, blank line, 2-3 content lines. No long lists. Draft only, NEVER publish. Report title/body/hashtags. Publishing happens after user approval."""
open("/tmp/fp.txt", "w", encoding="utf-8").write(prompt)
PYEOF
PROMPT=$(cat /tmp/fp.txt)
hermes cron edit 4b717995f801 --prompt "$PROMPT" 2>&1 | head -4