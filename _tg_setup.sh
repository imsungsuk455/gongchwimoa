#!/bin/bash
# 텔레그램 봇 토큰 등록 (기본 설정 - ALLOWED_USERS는 봇에 첫 메시지 후 확인)
sed -i 's/^# TELEGRAM_BOT_TOKEN=.*/TELEGRAM_BOT_TOKEN=8748993031:AAHLfc7--dUC4aKmeObFPlsg64G5urOcEpU/' /root/.hermes/.env
grep -n '^TELEGRAM_BOT_TOKEN=' /root/.hermes/.env
echo "=== 봇 정보 확인 (getMe) ==="
python3 -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('https://api.telegram.org/bot8748993031:AAHLfc7--dUC4aKmeObFPlsg64G5urOcEpU/getMe', timeout=15)
    print(r.read().decode())
except Exception as e:
    print('실패:', e)
"