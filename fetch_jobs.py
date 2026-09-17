#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나라일터(인사혁신처 공공취업정보) API -> jobs.json 자동갱신 스켈레톤.
- data.go.kr에서 '인사혁신처_공공취업정보 조회 서비스' 활용신청 후 API 키 발급 (무료, 자동승인)
- 환경변수 DATA_GO_KR_KEY 에 키를 넣고 실행. 키 없으면 --mock 으로 목업 동작(프로토타입 검증용).
- GitHub Actions cron(2시간 간격 권장)에서 실행 -> jobs.json 갱신 -> sitemap.xml 갱신 -> threads_queue.json(신규분) 생성
- 신규분 스레드 발송은 testlab 스킬의 threads_publish.py 방식을 재사용 (500자 이내, 댓글에 원문링크)
"""
import argparse, json, os, sys, datetime, xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_JSON = os.path.join(BASE, "jobs.json")
QUEUE_JSON = os.path.join(BASE, "threads_queue.json")
SITE_URL = os.environ.get("SITE_URL", "https://your-domain/jobs/")
# data.go.kr 상세 스펙은 신청 후 '활용신청 > 참고문서'에서 확인 (엔드포인트/파라미터가 버전별로 바뀜)
API_ENDPOINT = os.environ.get("GOJOBS_API_ENDPOINT", "")
PAGE_SIZE = 100

# ---- 하루 발행량 조절 (기본값, 환경변수로 변경 가능) ----
# 사이트 기사: 하루 5건 (마감일순). 나머지는 다음날로 자동 이월.
ARTICLES_PER_DAY = int(os.environ.get("ARTICLES_PER_DAY", "5"))
# 스레드: 하루 5개 슬롯에 1건씩 (수집과 발송 분리. 버퍼에 쌓고 정시에 1건씩 꺼냄).
MAX_THREADS_PER_DAY = int(os.environ.get("MAX_THREADS_PER_DAY", "5"))
THREAD_SLOTS = [s.strip() for s in os.environ.get("THREAD_SLOTS", "08:00,11:00,14:00,17:00,20:00").split(",") if s.strip()]
KST = datetime.timezone(datetime.timedelta(hours=9))

def _today():
    return datetime.datetime.now(KST).date().isoformat()

def load_buffer():
    """발송 버퍼. {"slots":[{date,slot,job_id,text,comment,status}]}"""
    try:
        with open(QUEUE_JSON, encoding="utf-8") as f:
            buf = json.load(f)
    except Exception:
        return {"slots": []}
    # 구버전 형식 마이그레이션: {"date":..., "slots":[{text,comment,job_id}]} → 신형식
    fixed = []
    for s in buf.get("slots", []):
        if "date" not in s:
            s = dict(s, date=buf.get("date", _today()), slot=s.get("slot", "08:00"),
                     status=s.get("status", "pending"), approved=s.get("approved", True))
        fixed.append(s)
    buf["slots"] = fixed
    return buf

def assign_slots(picks):
    """신규분을 오늘→내일 빈 슬롯에 순서대로 배정. 둘 다 차면 초과분은 탈락(로그)."""
    buf = load_buffer()
    today = _today()
    tomorrow = (datetime.datetime.now(KST).date() + datetime.timedelta(days=1)).isoformat()
    # 이틀 지난 발송완료는 정리
    buf["slots"] = [s for s in buf["slots"] if not (s.get("status") == "posted" and s.get("date", "") < today)]
    used = {(s.get("date"), s.get("slot")) for s in buf["slots"] if s.get("status") == "pending"}
    assigned, dropped = [], []
    for j in picks:
        placed = False
        for d in (today, tomorrow):
            for slot in THREAD_SLOTS:
                if (d, slot) not in used:
                    used.add((d, slot))
                    assigned.append({"date": d, "slot": slot, "job_id": j["id"],
                                     "text": thread_text(j), "comment": j["url"],
                                     "status": "pending", "approved": True})
                    placed = True
                    break
            if placed:
                break
        if not placed:
            dropped.append(j["id"])
    buf["slots"] = sorted(buf.get("slots", []) + assigned, key=lambda s: (s["date"], s["slot"]))
    with open(QUEUE_JSON, "w", encoding="utf-8") as f:
        json.dump(buf, f, ensure_ascii=False, indent=2)
    return assigned, dropped

def priority_key(job):
    try:
        left = (datetime.date.fromisoformat(job["deadline"]) - datetime.date.today()).days
    except Exception:
        left = 999
    urgent = 0 if 0 <= left <= 3 else 1
    intern = 0 if job.get("category") == "청년인턴" else 1
    return (urgent, intern, job["deadline"])

def load_jobs():
    with open(JOBS_JSON, encoding="utf-8") as f:
        return json.load(f)

def save_jobs(jobs):
    with open(JOBS_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

def fetch_api(key):
    """실제 API 호출. 스펙 확정 후 파라미터 조정 필요. 공통 패턴: serviceKey, pageNo, numOfRows, returnType."""
    params = urlencode({"serviceKey": key, "pageNo": 1, "numOfRows": PAGE_SIZE})
    url = f"{API_ENDPOINT}?{params}"
    print("GET", API_ENDPOINT, f"(rows={PAGE_SIZE})")
    with urlopen(url, timeout=30) as r:
        return r.read()

def exact_url(seq, source="나라일터"):
    """해당 공고로 곧장 가는 상세 URL (실측 규격).
    - 나라일터: apmView.do?empmnsn={공고번호}&menuNo=401&selMenuNo=400
    - 잡알리오: recruitview.do?idx={idx}"""
    seq = (seq or "").strip()
    if not seq:
        return ""
    if source == "잡알리오":
        return f"https://job.alio.go.kr/recruitview.do?idx={seq}"
    return f"https://www.gojobs.go.kr/apmView.do?empmnsn={seq}&menuNo=401&selMenuNo=400"

def parse_items(raw):
    """XML 응답 -> 표준 job dict 변환. 태그명은 실제 스펙에 맞춰 매핑."""
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        def g(tag):
            el = it.find(tag)
            return el.text.strip() if el is not None and el.text else ""
        seq = g("공고ID") or g("empmnsn") or g("seq") or g("idx") or g("id")
        src = g("출처") or "나라일터"
        url = g("상세URL") or g("원문URL") or exact_url(seq, src) or "https://www.gojobs.go.kr/apmList.do"
        items.append({
            "id": "gojobs-" + seq,
            "title": g("공고명") or g("title"),
            "org": g("기관명") or g("org"),
            "category": g("기관유형") or "공공기관",
            "type": g("채용유형") or "정규직",
            "region": g("채용지역") or "전국",
            "posted": g("게시일") or datetime.date.today().isoformat(),
            "deadline": g("마감일") or g("접수마감일") or "2026-12-31",
            "tags": [],
            "summary": [g("응시자격")] if g("응시자격") else ["원문 공고문 확인 필수"],
            "source": "나라일터",
            "url": url,
        })
    return [x for x in items if x["title"] and x["id"] != "gojobs-"]

def thread_text(job):
    d = job["deadline"]
    t = f"📢 {job['org']}\n「{job['title']}」\n마감 {d} · {job['region']} · {job['type']}\n✅ " + " / ".join(job["summary"][:2])
    if len(t) > 420:
        t = t[:420] + "…"
    return t + "\n원문 링크는 댓글에 👇"

def verify_links(items, timeout=15):
    """수집 단계 실측 검증: 상세 URL을 열어 기관명/공고명이 있는지 확인.
    불일치 항목은 저장하지 않고 반환에서 제외 (번호 어긋남 원천 차단)."""
    from urllib.request import Request, urlopen
    good, bad = [], []
    for j in items:
        try:
            req = Request(j["url"], headers={"User-Agent": "Mozilla/5.0"})
            html = urlopen(req, timeout=timeout).read().decode("utf-8", errors="replace")
            if j["org"][:4] in html and j["title"][:8] in html:
                good.append(j)
            else:
                bad.append(j["id"])
        except Exception:
            bad.append(j["id"])
    return good, bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="API 없이 목업 1건을 신규로 가정해 큐 생성")
    ap.add_argument("--skip-verify", action="store_true", help="링크 실측 검증 생략 (긴급시)")
    args = ap.parse_args()
    old = load_jobs()
    old_ids = {j["id"] for j in old}
    if args.mock:
        new_items = [dict(old[0], id=old[0]["id"] + "-new")]
    else:
        key = os.environ.get("DATA_GO_KR_KEY", "")
        if not key or not API_ENDPOINT:
            print("DATA_GO_KR_KEY 또는 GOJOBS_API_ENDPOINT 미설정. --mock 으로 검증하거나 키 발급 후 재실행.", file=sys.stderr)
            print("발급: data.go.kr > '인사혁신처_공공취업정보 조회 서비스' 검색 > 활용신청(무료/자동승인) > 참고문서에서 엔드포인트 확인", file=sys.stderr)
            sys.exit(2)
        new_items = parse_items(fetch_api(key))
    fresh = [x for x in new_items if x["id"] not in old_ids]
    if not fresh:
        print("신규 공고 0건. 갱신 없음.")
        return
    if args.skip_verify:
        verified, rejected = fresh, []
    else:
        verified, rejected = verify_links(fresh)
        if rejected:
            print(f"링크 불일치 {len(rejected)}건 제외: {', '.join(rejected)}", file=sys.stderr)
    if not verified:
        print("검증 통과 0건. 저장 없이 종료.")
        return
    merged = verified + old
    save_jobs(merged)
    # 스레드는 우선순위순으로 발송 버퍼에 적재 (오늘→내일 빈 슬롯). 발송은 send_queue.py가 정시에 처리.
    import quota
    allow = quota.remaining("threads", MAX_THREADS_PER_DAY)
    picks = sorted(verified, key=priority_key)[:allow]
    quota.consume("threads", len(picks))
    assigned, dropped = assign_slots(picks)
    print(f"신규 {len(verified)}건 반영. 스레드 버퍼 배정 {len(assigned)}건" +
          (f" ({', '.join(s['date']+' '+s['slot'] for s in assigned)})" if assigned else "") +
          (f". 슬롯 만석으로 탈락 {len(dropped)}건" if dropped else "") + f": {QUEUE_JSON}")

if __name__ == "__main__":
    main()
