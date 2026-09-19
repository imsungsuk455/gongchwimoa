#!/bin/bash
cd /root/public-jobs
export THREADS_USER_ID=39460061993584477
export THREADS_ACCESS_TOKEN=THAATDwBN1pWFBYlp4eWxLS3FNZAndQUGJScGFpaWxhbU5lUUx6SVAxTzdhYU5ROHNadXJWSXZAkTkcwRHFkcmZANTkZAfa1doQlBoMkdSUHhHM21nWi1Ibm9ZAd1dUUVNYM3VhMUJBeFJTRzVTX2t5aVNXNnZAxc0owVE5GcUFENjktY1hVUG9xX25QNy02M3NkTTAZD
export THREADS_LIVE=1
python3 - <<'PY'
import sys, json, subprocess, os
sys.path.insert(0, os.getcwd())
# git_claim을 직접 재현 (send_queue.py와 동일 로직)
import send_queue
from send_queue import QUEUE_JSON
buf = send_queue.load()
today = send_queue.now_kst().date().isoformat()
cur = send_queue.now_kst().strftime("%H:%M")
due = [s for s in buf["slots"] if s.get("status") == "pending" and s.get("approved", True)
       and s.get("date") == today and s.get("slot", "") <= cur]
print("due 슬롯:", [(s["slot"], s["job_id"]) for s in due])
for s in due:
    s["status"] = "claiming"
send_queue.save(buf)
ok = send_queue.git_claim("debug claim")
print("git_claim 결과:", ok)
if not ok:
    # 실패 원인 추적: 수동으로 재실행
    for step in ["pull", "commit", "push"]:
        if step == "pull":
            r = subprocess.run(["git", "pull", "--rebase", "origin", "main"], capture_output=True, text=True)
        elif step == "commit":
            r = subprocess.run(["git", "commit", "-m", "debug-claim", "--", QUEUE_JSON, "publish_state.json"], capture_output=True, text=True)
        else:
            r = subprocess.run(["git", "push"], capture_output=True, text=True)
        print(f"[{step}] rc={r.returncode} out={r.stdout.strip()[:100]} err={r.stderr.strip()[:150]}")
PY