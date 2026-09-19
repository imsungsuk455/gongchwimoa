#!/bin/bash
# 공취모아 스레드 정시 발송 (Hermes cron용, --no-agent 모드)
# 사용법: send_slot.sh <슬롯시각 KST>  예: send_slot.sh 17:30
set -e
cd /root/public-jobs
git pull --rebase origin main >/dev/null 2>&1 || true
SLOT="$1"
if [ -z "$SLOT" ]; then
  echo "슬롯 시각 필요: send_slot.sh 17:30"
  exit 1
fi
export THREADS_USER_ID="${THREADS_USER_ID:-}"
export THREADS_ACCESS_TOKEN="${THREADS_ACCESS_TOKEN:-}"
export THREADS_LIVE="1"
python3 send_queue.py --slot "$SLOT"
echo "DONE $SLOT"