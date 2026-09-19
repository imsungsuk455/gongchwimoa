#!/bin/bash
TOKEN=$(cat /tmp/gh_token.txt)
cd /root/public-jobs
git remote set-url origin "https://x-access-token:${TOKEN}@github.com/imsungsuk455/gongchwimoa.git"
echo "=== push 테스트 ==="
timeout 30 git push origin main 2>&1 | tail -2
echo "=== 원복 (토큰 URL 유지 - 자격 증명 내장) ==="
git remote -v | head -1