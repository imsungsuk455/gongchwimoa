#!/bin/bash
# 텔레그램 허용 사용자 + 홈 채널 등록
sed -i 's/^# TELEGRAM_ALLOWED_USERS=.*/TELEGRAM_ALLOWED_USERS=5032205044/' /root/.hermes/.env
sed -i 's/^# TELEGRAM_HOME_CHANNEL=.*/TELEGRAM_HOME_CHANNEL=5032205044/' /root/.hermes/.env
grep -n '^TELEGRAM_' /root/.hermes/.env | grep -v '^.*#'