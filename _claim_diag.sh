#!/bin/bash
cd /root/public-jobs
echo "=== 1. pull --rebase ==="
timeout 30 git pull --rebase origin main 2>&1 | tail -2
echo "=== 2. 큐에 claim 상태 쓰기 ==="
python3 - <<'PY'
import json
q = json.load(open("threads_queue.json", encoding="utf-8"))
for s in q["slots"]:
    if s.get("date") == "2026-09-19" and s.get("status") == "pending":
        s["status"] = "claiming"
json.dump(q, open("threads_queue.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("claiming으로 변경")
PY
echo "=== 3. commit ==="
git add threads_queue.json
git commit -m "test claim" 2>&1 | tail -1
echo "=== 4. push ==="
timeout 30 git push origin main 2>&1 | tail -2