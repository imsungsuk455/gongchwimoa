#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스레드 정시 발송기. 수집(fetch_jobs.py)과 분리 동작.
- GitHub Actions cron을 최대 10개 슬롯(기본 07:00~20:30 KST)에 걸고 실행.
- 해당 슬롯의 pending 1건을 발행하고 posted로 표시. 빈 슬롯이면 skip (콘텐츠성 글 없음).
- 공고 → 사이트 기사 업로드 → 스레드 글로만 자동 배포. 링크는 댓글로 내 사이트 기사.
- 기본 --dry-run (발행 없이 출력만). 실제 발송은 --live + 환경변수 필요.
"""
import argparse, json, os, sys, time, datetime, re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = os.path.dirname(os.path.abspath(__file__))
QUEUE_JSON = os.path.join(BASE, "threads_queue.json")
EDITORIAL_JSON = os.path.join(BASE, "threads_editorial.json")
JOBS_JSON = os.path.join(BASE, "jobs.json")
SITE_URL = os.environ.get("SITE_URL", "https://gongchwimoa.org/")
KST = datetime.timezone(datetime.timedelta(hours=9))
API = "https://graph.threads.net/v1.0"
# 하루 실제 발송 상한 (배정 쿼터와 별개. 어제 밀린 분 포함, 금일 posted+발송 합계 기준)
POSTS_PER_DAY = int(os.environ.get("MAX_POSTS_PER_DAY", "10"))

def sunday_digest():
    """일요일 20시 슬롯: 이번 주 마감 TOP5 자동 생성. 없으면 None."""
    try:
        jobs = json.load(open(JOBS_JSON, encoding="utf-8"))
    except Exception:
        return None
    today = now_kst().date()
    upcoming = [j for j in jobs
                if 0 <= (datetime.date.fromisoformat(j["deadline"]) - today).days <= 7]
    upcoming.sort(key=lambda x: x["deadline"])
    if not upcoming:
        return None
    lines = []
    for i, j in enumerate(upcoming[:5], 1):
        org = (j.get("org") or "").strip()
        short = org.split()[-1] if org else ""
        t = j.get("title") or ""
        for u in sorted(org.split(), key=len, reverse=True):
            t = t.replace(u, "")
        t = re.sub(r"\s+", " ", t).strip(" -·")
        lines.append(f"{i}. {short} {t[:28]} (~{j['deadline'][5:]})")
    text = "📅 이번 주 마감 공고 TOP5\n\n" + "\n".join(lines) + "\n\n상세 해설은 공취모아에서 👇"
    return {"date": today.isoformat(), "slot": "20:00", "job_id": "digest",
            "text": text, "comment": SITE_URL, "status": "pending", "approved": True}

def editorial_pick():
    """빈 슬롯용 에디토리얼. 요일 코너(weekday) 우선, 없으면 전체 순환. 당일 중복 금지."""
    import quota
    try:
        bank = json.load(open(EDITORIAL_JSON, encoding="utf-8"))["posts"]
    except Exception:
        return None
    if not bank:
        return None
    today = now_kst().date().isoformat()
    try:
        done = {s.get("job_id") for s in load().get("slots", [])
                if s.get("date") == today and s.get("status") == "posted"}
    except Exception:
        done = set()
    wd = now_kst().weekday()
    wd_posts = [(i, p) for i, p in enumerate(bank) if p.get("weekday") == wd
                and f"editorial-{i}" not in done]
    if wd_posts:
        k = quota.next_round_robin(f"editorial_wd{wd}", len(wd_posts))
        i, p = wd_posts[k]
    else:
        rest = [(i, p) for i, p in enumerate(bank) if f"editorial-{i}" not in done]
        if not rest:
            rest = [(i, p) for i, p in enumerate(bank)]
        i = quota.next_round_robin("editorial_idx", len(rest))
        i, p = rest[i]
    return {"date": today, "slot": "", "job_id": f"editorial-{i}",
            "text": p["text"], "comment": p.get("comment"), "status": "pending", "approved": True}

def now_kst():
    return datetime.datetime.now(KST)

def load():
    with open(QUEUE_JSON, encoding="utf-8") as f:
        return json.load(f)

def save(buf):
    with open(QUEUE_JSON, "w", encoding="utf-8") as f:
        json.dump(buf, f, ensure_ascii=False, indent=2)

def api_post(path, params):
    data = urlencode(params).encode()
    req = Request(API + path, data=data, method="POST")
    with urlopen(req, timeout=30) as r:
        return json.load(r)

def publish_text(uid, token, text):
    cid = api_post(f"/{uid}/threads",
                   {"media_type": "TEXT", "text": text, "access_token": token})["id"]
    time.sleep(5)
    mid = api_post(f"/{uid}/threads_publish",
                   {"creation_id": cid, "access_token": token})["id"]
    return mid

def publish_reply(uid, token, reply_to, text):
    time.sleep(60)  # 본문 전파 대기 (testlab 실측: 바로 답글 달면 Media Not Found)
    for i in range(5):
        try:
            cid = api_post(f"/{uid}/threads",
                           {"media_type": "TEXT", "text": text,
                            "reply_to_id": reply_to, "access_token": token})["id"]
            time.sleep(10)
            return api_post(f"/{uid}/threads_publish",
                            {"creation_id": cid, "access_token": token})["id"]
        except Exception as e:
            print(f"  답글 재시도 {i+1}/5: {e}", file=sys.stderr)
            time.sleep(30)
    return None

def git_claim(msg):
    """상태 파일을 커밋/푸시. 실패(충돌) 시 False — 다른 실행이 먼저 점유한 것."""
    import subprocess
    for _ in range(3):
        subprocess.run(["git", "config", "user.name", "gongchwimoa-bot"],
                       capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email",
                        "gongchwimoa-bot@users.noreply.github.com"],
                       capture_output=True, text=True)
        r = subprocess.run(["git", "pull", "--rebase", "origin", "main"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return False
        r = subprocess.run(["git", "commit", "-m", msg, "--",
                            QUEUE_JSON, "publish_state.json"],
                           capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in r.stderr:
            return False
        r = subprocess.run(["git", "push"], capture_output=True, text=True)
        if r.returncode == 0:
            return True
        if "non-fast-forward" in r.stderr or "fetch first" in r.stderr:
            continue  # 충돌 → rebase 후 재시도
        return False
    return False

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="", help="발송 슬롯 지정 (예: 14:00). 생략하면 현재 KST 시각 이하의 오늘 pending 전부")
    ap.add_argument("--live", action="store_true", help="실제 발송. 없으면 dry-run")
    args = ap.parse_args()
    live = args.live or os.environ.get("THREADS_LIVE", "") == "1"
    buf = load()
    today = now_kst().date().isoformat()
    cur = now_kst().strftime("%H:%M")
    due = sorted([s for s in buf.get("slots", [])
           if s.get("status") == "pending" and s.get("approved", True)
           and s.get("date") == today
           and (s.get("slot") == args.slot if args.slot else s.get("slot", "") <= cur)],
           key=lambda s: s.get("slot", ""))
    # 중복 방지: 같은 job_id가 오늘 이미 posted면 남은 복제 슬롯은 skip
    posted_ids = {s.get("job_id") for s in buf.get("slots", [])
                  if s.get("status") == "posted" and s.get("date") == today}
    dup = [s for s in due if s.get("job_id") in posted_ids]
    if dup:
        due = [s for s in due if s.get("job_id") not in posted_ids]
    over = []
    if not args.slot:
        # 일일 발송 상한: 금일 posted + 이번 발송 합계가 POSTS_PER_DAY를 넘지 않음. 초과분은 skip(영구).
        posted_today = sum(1 for s in buf.get("slots", [])
                           if s.get("status") == "posted" and s.get("date") == today)
        budget = max(POSTS_PER_DAY - posted_today, 0)
        if len(due) > budget:
            over, due = due[budget:], due[:budget]
    if not due and not over:
        print(f"발송 대상 없음 (오늘 {today}, 기준 {args.slot or cur}). 빈 슬롯은 skip.")
        return
    if not live:
        for s in due:
            print(f"[dry-run] {s['date']} {s['slot']} {s['job_id']}\n{s['text']}\n→ 댓글: {s['comment']}\n")
        for s in over:
            print(f"[dry-run] 상한 초과로 skip 예정: {s['date']} {s['slot']} {s['job_id']}")
        print("실제 발송은 --live (THREADS_ACCESS_TOKEN / THREADS_USER_ID 필요).")
        return
    uid = os.environ.get("THREADS_USER_ID", "")
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not uid or not token:
        print("THREADS_USER_ID / THREADS_ACCESS_TOKEN 미설정.", file=sys.stderr)
        sys.exit(2)
    # 점유(claim): 발송 전 상태를 커밋/푸시. 성공한 실행만 발송 (중복 발송 방지).
    for s in due:
        s["status"] = "claiming"
    save(buf)
    if not git_claim(f"Threads claim: {', '.join(s['slot'] for s in due)}"):
        # 점유 실패 → claiming 상태를 pending으로 되돌려 다음 실행이 발송 가능하게
        for s in due:
            s["status"] = "pending"
        save(buf)
        print("점유 실패 (다른 실행이 먼저 진행). 중복 발송 방지로 종료.", file=sys.stderr)
        sys.exit(0)
    for s in over:
        s["status"] = "skipped"
        print(f"상한 초과 skip: {s['slot']} {s['job_id']}")
    for s in due:
        try:
            mid = publish_text(uid, token, s["text"])
            rid = publish_reply(uid, token, mid, s["comment"]) if s.get("comment") else None
            s["status"] = "posted"
            s["post_id"] = mid
            if rid:
                s["comment_id"] = rid
            print(f"발송 완료: {s['slot']} {s['job_id']} post={mid}")
        except Exception as e:
            s["status"] = "pending"  # 실패 시 재시도 가능하게 복구
            print(f"발송 실패 ({s['slot']} {s['job_id']}): {e}", file=sys.stderr)
    save(buf)
    git_claim(f"Threads sent: {', '.join(s['slot'] for s in due)}")

if __name__ == "__main__":
    main()
