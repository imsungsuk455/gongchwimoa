#!/bin/bash
python3 - <<'PYEOF'
import re
p = "/root/.hermes/config.yaml"
src = open(p, encoding="utf-8").read()

# 1) cron_mode: deny → approve
src2 = re.sub(r'cron_mode:\s*"deny"|cron_mode:\s*deny', 'cron_mode: "approve"', src, count=1)

# 2) command_allowlist 채우기 (cron 작업에 필요한 명령만)
if '"command_allowlist": []' in src2:
    src2 = src2.replace('"command_allowlist": []', '''"command_allowlist": [
    "git pull*", "git fetch*", "git status*", "git add*", "git commit*", "git push*", "git remote*",
    "python*", "python3*", "pip*"
  ]''')

if src2 == src:
    print("WARN: 패턴 매치 실패 — 직접 확인 필요")
else:
    open(p, "w", encoding="utf-8").write(src2)
    print("적용 완료")

# 확인
for line in src2.splitlines():
    if 'cron_mode' in line or 'command_allowlist' in line:
        print(">", line.strip())
PYEOF