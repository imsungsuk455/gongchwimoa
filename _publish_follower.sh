#!/bin/bash
# 팔로워 콘텐츠 스레드 발행 (Hermes 승인 후 호출)
# 사용법: publish_follower.sh "본문" "댓글"
set -e
TEXT="$1"
COMMENT="$2"
if [ -z "$TEXT" ]; then
  echo "본문 필요"; exit 1
fi
# .env 로드 (THREADS 토큰 등)
if [ -f /root/.hermes/.env ]; then
  set -a
  . /root/.hermes/.env
  set +a
fi
export THREADS_USER_ID="${THREADS_USER_ID:-}"
export THREADS_ACCESS_TOKEN="${THREADS_ACCESS_TOKEN:-}"
python3 - <<'PY'
import os, json, sys, time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

uid = os.environ["THREADS_USER_ID"]
token = os.environ["THREADS_ACCESS_TOKEN"]
text = os.environ.get("FTEXT", "")
comment = os.environ.get("FCOMMENT", "")

def api_post(path, params):
    data = urlencode(params).encode()
    req = Request("https://graph.threads.net/v1.0" + path, data=data, method="POST")
    with urlopen(req, timeout=30) as r:
        return json.load(r)

def publish_text(t):
    cid = api_post(f"/{uid}/threads", {"media_type": "TEXT", "text": t, "access_token": token})["id"]
    time.sleep(5)
    return api_post(f"/{uid}/threads_publish", {"creation_id": cid, "access_token": token})["id"]

mid = publish_text(text)
print("발행 완료 post=" + mid)
if comment:
    time.sleep(60)
    cid = api_post(f"/{uid}/threads", {"media_type": "TEXT", "text": comment, "reply_to_id": mid, "access_token": token})["id"]
    time.sleep(10)
    rid = api_post(f"/{uid}/threads_publish", {"creation_id": cid, "access_token": token})["id"]
    print("댓글 완료 reply=" + rid)
PY