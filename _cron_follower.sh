#!/bin/bash
cat > /tmp/follower_prompt.txt <<'PROMPT_EOF'
공공기관 취업 도움 콘텐츠 1개를 만들어라. 주제 예시: 행정직 필수 자격증, 시설직 자격증 준비법, 공공기관 전형 팁 등. jobs.json과 웹 리서치를 활용해 사실 기반으로 작성. 초안만 만들고 절대 발행하지 말 것. 최종 보고에 제목/본문(훅+빈줄+내용)/해시태그 3개를 포함하라. 발행은 사용자가 텔레그램에서 승인한 뒤 별도로 한다.
PROMPT_EOF
hermes cron create "0 3 * * *" \
  --name follower-content \
  --skill gongchwimoa-daily-content \
  --model muse-spark-1.3-contributor \
  --workdir /root/public-jobs \
  --deliver telegram \
  "$(cat /tmp/follower_prompt.txt)"