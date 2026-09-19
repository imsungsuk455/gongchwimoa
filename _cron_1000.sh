#!/bin/bash
# 이력 파일 확인
mkdir -p /root/.hermes/state
if [ ! -f /root/.hermes/state/follower_topics.json ]; then
  echo '{"history": []}' > /root/.hermes/state/follower_topics.json
fi

python3 - <<'PYEOF'
import json, datetime

themes = {
    0: "자격증 준비 (필수/우대 자격, 준비 방법)",
    1: "이번 주 핫한 채용 리서치 (마감 임박·대형 공고)",
    2: "전형별 팁 (서류/필기/면접)",
    3: "채용 트렌드 (NCS·인적성·최근 변화)",
    4: "특정 기관/직군 소개 (예: 공무직·공기업·지자체)",
    5: "수험생/구직자 실전 팁 (커뮤니티 반응 기반)",
    6: "한 주 채용 마감 요약",
}
wd = datetime.datetime.now().weekday()
theme = themes[wd]

try:
    hist = json.load(open("/root/.hermes/state/follower_topics.json", encoding="utf-8"))["history"]
except Exception:
    hist = []
recent = ", ".join(hist[-10:]) if hist else "없음"

prompt = f"""Create ONE follower-content piece (about 1000 characters total) for public-sector job seekers. Today's fixed theme: {theme}.

REQUIRED research steps:
1. Read /root/.hermes/state/follower_topics.json BEFORE writing. Avoid duplicating these already-used topics: {recent}
2. Web search (MUST): search community/forum discussions too — DC Inside (gall.dcinside.com) job-hunting/exam galleries, plus news/sites. Quote real community sentiment or current info.

WRITING FORMAT (Threads):
- Main post: max 500 characters (Korean). Structure: hook line, blank line, then content.
- If the full content exceeds 500 chars, the remainder goes into a follow-up comment (continuation). Plan the split so the main post ends at a natural break.
- Total content across post + comments: ~1000 characters.
- No long lists.

After drafting, append today's topic to the history file: python3 -c 'import json; p="/root/.hermes/state/follower_topics.json"; d=json.load(open(p)); d["history"].append("{theme}"); json.dump(d,open(p,"w"),ensure_ascii=False)'

Draft only, NEVER publish. Report: title / main post (with char count) / continuation comment(s) / hashtags / sources. Publishing happens after user approval."""
open("/tmp/fp.txt", "w", encoding="utf-8").write(prompt)
print("테마:", theme)
PYEOF

PROMPT=$(cat /tmp/fp.txt)
hermes cron edit 4b717995f801 --prompt "$PROMPT" 2>&1 | head -4