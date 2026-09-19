#!/bin/bash
# 서버 .env에 Threads 크레덴셜 설정
touch /root/.hermes/.env
grep -q THREADS_ACCESS_TOKEN /root/.hermes/.env && sed -i '/^THREADS_ACCESS_TOKEN=/d' /root/.hermes/.env
grep -q THREADS_USER_ID /root/.hermes/.env && sed -i '/^THREADS_USER_ID=/d' /root/.hermes/.env
cat >> /root/.hermes/.env <<'EOF'
THREADS_ACCESS_TOKEN=THAATDwBN1pWFBYlp4eWxLS3FNZAndQUGJScGFpaWxhbU5lUUx6SVAxTzdhYU5ROHNadXJWSXZAkTkcwRHFkcmZANTkZAfa1doQlBoMkdSUHhHM21nWi1Ibm9ZAd1dUUVNYM3VhMUJBeFJTRzVTX2t5aVNXNnZAxc0owVE5GcUFENjktY1hVUG9xX25QNy02M3NkTTAZD
THREADS_USER_ID=39460061993584477
EOF
chmod 600 /root/.hermes/.env
echo "=== .env 확인 (마스킹) ==="
grep -o '^THREADS_[A-Z_]*=' /root/.hermes/.env
echo "=== 발송 스크립트 실행 테스트 (20:30 슬롯) ==="
cd /root/public-jobs
export THREADS_USER_ID=39460061993584477
export THREADS_ACCESS_TOKEN=THAATDwBN1pWFBYlp4eWxLS3FNZAndQUGJScGFpaWxhbU5lUUx6SVAxTzdhYU5ROHNadXJWSXZAkTkcwRHFkcmZANTkZAfa1doQlBoMkdSUHhHM21nWi1Ibm9ZAd1dUUVNYM3VhMUJBeFJTRzVTX2t5aVNXNnZAxc0owVE5GcUFENjktY1hVUG9xX25QNy02M3NkTTAZD
export THREADS_LIVE=1
python3 send_queue.py --slot 20:30