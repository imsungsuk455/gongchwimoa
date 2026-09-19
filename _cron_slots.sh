#!/bin/bash
# 슬롯별 발송 cron 등록 (UTC 기준: KST-9)
# KST 07:00=22:00UTC, 08:30=23:30, 10:00=01:00, 11:30=02:30, 13:00=04:00,
# 14:30=05:30, 16:00=07:00, 17:30=08:30, 19:00=10:00, 20:30=11:30
declare -A SLOTS=(
  ["07:00"]="0 22 * * *"
  ["08:30"]="30 23 * * *"
  ["10:00"]="0 1 * * *"
  ["11:30"]="30 2 * * *"
  ["13:00"]="0 4 * * *"
  ["14:30"]="30 5 * * *"
  ["16:00"]="0 7 * * *"
  ["17:30"]="30 8 * * *"
  ["19:00"]="0 10 * * *"
  ["20:30"]="30 11 * * *"
)
for slot in "${!SLOTS[@]}"; do
  cron="${SLOTS[$slot]}"
  # 기존 잡 제거
  existing=$(hermes cron list 2>/dev/null | grep "send-$slot" | awk '{print $1}')
  [ -n "$existing" ] && hermes cron remove "$existing" >/dev/null 2>&1
  hermes cron create "$cron" \
    --name "send-$slot" \
    --script send_slot.sh \
    --no-agent \
    --workdir /root/public-jobs \
    --deliver local 2>&1 | grep -E "Created|Error" | head -1
done
echo "=== 등록된 cron ==="
hermes cron list 2>&1 | head -20