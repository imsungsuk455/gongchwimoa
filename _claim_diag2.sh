#!/bin/bash
cd /root/public-jobs
echo "=== send_queue.py가 보는 remote ==="
git remote get-url origin
echo "=== 실제 send_queue.py 실행 (dry 확인 위해 임시) ==="
export THREADS_USER_ID=39460061993584477
export THREADS_ACCESS_TOKEN=THAATDwBN1pWFBYlp4eWxLS3FNZAndQUGJScGFpaWxhbU5lUUx6SVAxTzdhYU5ROHNadXJWSXZAkTkcwRHFkcmZANTkZAfa1doQlBoMkdSUHhHM21nWi1Ibm9ZAd1dUUVNYM3VhMUJBeFJTRzVTX2t5aVNXNnZAxc0owVE5GcUFENjktY1hVUG9xX25QNy02M3NkTTAZD
export THREADS_LIVE=1
# 08:30 슬롯은 posted이므로 중복 방지 없이 통과하는지 확인
python3 send_queue.py --slot 20:30 2>&1 | head -8
echo "EXIT=$?"