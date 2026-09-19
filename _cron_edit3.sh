#!/bin/bash
python3 - <<'PYEOF'
prompt = """Create ONE short follower-content piece for public-sector job seekers. MUST research from the web first (web search for current info: essential certificates for admin/facility jobs, recent exam schedules, current trends). Base facts on web sources, not assumptions. RULES: body max 4 lines (hook line, blank line, 2-3 short lines). No long lists. Draft only, NEVER publish. Report title/body/hashtags. Publishing happens after user approval."""
open("/tmp/fp.txt", "w", encoding="utf-8").write(prompt)
PYEOF
PROMPT=$(cat /tmp/fp.txt)
hermes cron edit 4b717995f801 --prompt "$PROMPT" 2>&1 | head -4