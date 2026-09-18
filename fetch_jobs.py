#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나라일터(인사혁신처 공공취업정보) API -> jobs.json 자동갱신 스켈레톤.
- data.go.kr에서 '인사혁신처_공공취업정보 조회 서비스' 활용신청 후 API 키 발급 (무료, 자동승인)
- 환경변수 DATA_GO_KR_KEY 에 키를 넣고 실행. 키 없으면 --mock 으로 목업 동작(프로토타입 검증용).
- GitHub Actions cron(2시간 간격 권장)에서 실행 -> jobs.json 갱신 -> sitemap.xml 갱신 -> threads_queue.json(신규분) 생성
- 신규분 스레드 발송은 testlab 스킬의 threads_publish.py 방식을 재사용 (500자 이내, 댓글에 원문링크)
"""
import argparse, json, os, sys, datetime, re, xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_JSON = os.path.join(BASE, "jobs.json")
QUEUE_JSON = os.path.join(BASE, "threads_queue.json")
SITE_URL = os.environ.get("SITE_URL", "https://gongchwimoa.org/")
# data.go.kr 참고문서(활용신청 > 상세 ⁄ 참고문서)에서 오퍼레이션·파라미터 확인.
# 인사혁신처 공공취업정보: base https://apis.data.go.kr/1760000/PblJobService + op /getList
# 실측(2026-09-17): idx 오름차순 고정, 최신정렬·상세조회 없음. 일일 최신 수집은 fetch_gojobs_html.py가 담당.
# API 경로는 title 키워드 보충 수집용.
API_ENDPOINT = os.environ.get("GOJOBS_API_ENDPOINT",
                              "https://apis.data.go.kr/1760000/PblJobService/getList")
API_TITLE_QUERY = os.environ.get("API_TITLE_QUERY", "")
PAGE_SIZE = 100

def infer_type(title):
    t = title or ""
    if "청년인턴" in t or "체험형" in t:
        return "청년인턴(체험형)"
    if "시간강사" in t:
        return "시간강사"
    if "기간제" in t and ("교사" in t or "교원" in t):
        return "기간제교사"
    if any(k in t for k in ["공무직", "무기계약", "집배원", "시설관리원", "미화", "조리원", "운전원"]):
        return "공무직"
    if "기간제" in t:
        return "기간제"
    if "임기제" in t or "개방형" in t:
        return "임기제"
    return "정규직"

def ymd8(s):
    s = (s or "").strip()
    return s[:4] + "-" + s[4:6] + "-" + s[6:8] if len(s) == 8 and s.isdigit() else s

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
                                     "text": thread_text(j),
                                     "comment": f"자세한 사항 확인하러 가기 ▽\n{j['url']}",
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
    intern = 0 if (job.get("category") == "청년인턴" or "인턴" in job.get("type", "")) else 1
    return (urgent, intern, job["deadline"])

def load_jobs():
    with open(JOBS_JSON, encoding="utf-8") as f:
        return json.load(f)

def save_jobs(jobs):
    with open(JOBS_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

def prune_expired(jobs):
    """마감 지난 공고 처리. 기본(승인 전)은 유지(마감 뱃지).
    PRUNE_EXPIRED=1일 때만 기사/썸네일 파일까지 삭제."""
    if os.environ.get("PRUNE_EXPIRED", "") != "1":
        return jobs, []
    today = datetime.date.today().isoformat()
    keep, dropped = [], []
    for j in jobs:
        if (j.get("deadline") or "") < today:
            dropped.append(j["id"])
            for p in (os.path.join(BASE, "articles", j["id"] + ".html"),
                      os.path.join(BASE, "thumbnails", j["id"] + ".png")):
                try:
                    os.remove(p)
                except OSError:
                    pass
        else:
            keep.append(j)
    return keep, dropped

def fetch_api(key):
    """PblJobService/getList 호출. serviceKey, pageNo, numOfRows + 선택 title."""
    params = {"serviceKey": key, "pageNo": 1, "numOfRows": PAGE_SIZE}
    if API_TITLE_QUERY:
        params["title"] = API_TITLE_QUERY
    url = API_ENDPOINT + "?" + urlencode(params)
    print("GET", API_ENDPOINT, f"(rows={PAGE_SIZE}" + (f", title={API_TITLE_QUERY}" if API_TITLE_QUERY else "") + ")")
    with urlopen(url, timeout=30) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("euc-kr", errors="replace")

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
    """PblJobService 응답 -> 표준 job dict. 필드: idx/title/insttname/regdate/enddate."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            raw = raw.decode("euc-kr", errors="replace")
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        def g(tag):
            el = it.find(tag)
            return el.text.strip() if el is not None and el.text else ""
        seq = g("idx") or g("공고ID") or g("empmnsn") or g("seq") or g("id")
        src = g("출처") or "나라일터"
        title = g("title") or g("공고명")
        org = g("insttname") or g("기관명") or g("org")
        url = g("상세URL") or g("원문URL") or exact_url(seq, src) or "https://www.gojobs.go.kr/apmList.do"
        items.append({
            "id": "gojobs-" + seq,
            "title": title,
            "org": org,
            "category": g("기관유형") or "공공기관",
            "type": infer_type(title),
            "region": "전국",
            "posted": ymd8(g("regdate")) or g("게시일") or datetime.date.today().isoformat(),
            "deadline": ymd8(g("enddate")) or g("마감일") or g("접수마감일") or "2026-12-31",
            "tags": [],
            "summary": [g("응시자격")] if g("응시자격") else ["접수 ~" + ymd8(g("enddate")) + " 마감", "세부 조건은 원문 공고문 확인"],
            "source": "나라일터",
            "url": url,
        })
    return [x for x in items if x["title"] and x["id"] != "gojobs-"]

BENEFIT_RE = [
    (re.compile(r"(?:초봉|연봉|급여|보수)\s*(\d[\d,]*만원)"), lambda m: f"초봉 {m.group(1)}"),
    (re.compile(r"(\d[\d,]*만원)\s*(?:이상|~)"), lambda m: f"연봉 {m.group(1)} 이상"),
    (re.compile(r"(?:수당|보수|급여)\s*[:：]\s*(\d[\d,]*원)/시간"), lambda m: f"시간당 {m.group(1)}"),
    (re.compile(r"월\s*(\d[\d,]*원)"), lambda m: f"월급 {m.group(1)}"),
    (re.compile(r"정년"), lambda m: "정년보장"),
    (re.compile(r"주\s*5일"), lambda m: "주 5일 근무"),
    (re.compile(r"(?:경력|전공)\s*무관"), lambda m: "경력 무관"),
    (re.compile(r"임기\s*(\d+)\s*년"), lambda m: f"임기 {m.group(1)}년"),
]

def extract_benefit(job):
    """공고 최대 이점 1~2개 추출. 정규직/공무직은 구조적 이점(정년보장) 포함."""
    text = " ".join([
        job.get("excerpt", "") or "",
        " ".join(job.get("summary", [])),
        job["title"],
    ])
    found = []
    for rx, fmt in BENEFIT_RE:
        m = rx.search(text)
        v = fmt(m) if m else None
        if v and v not in found:
            found.append(v)
    jt = job.get("type", "")
    if jt in ("정규직", "공무직") and "정년보장" not in found:
        found.append("정년보장")
    return ", ".join(found[:2]) if found else None

def thread_text(job):
    d = job["deadline"]
    try:
        days = (datetime.date.fromisoformat(d) - datetime.date.today()).days
    except Exception:
        days = 99
    if days <= 0:
        hook = "오늘 마감!"
    elif days == 1:
        hook = "내일 마감!"
    elif days <= 3:
        hook = f"마감 임박 D-{days}!"
    else:
        benefit = extract_benefit(job)
        hook = benefit or {"정규직": "정규직 채용",
                           "공무직": "공무직 채용",
                           "임기제": "임기제 채용",
                           "기간제": "기간제 채용",
                           "시간강사": "시간강사 모집",
                           "청년인턴": "청년인턴 모집"}.get(job.get("type", ""), "공공 채용")
    title = job["title"].strip()
    if len(title) > 42:
        cut = title[:42]
        sp = cut.rfind(" ")
        title = (cut[:sp] if sp > 20 else cut).rstrip() + "…"
    return f"{hook}\n{title} 떴다!"

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
    old, pruned = prune_expired(old)
    if pruned:
        print(f"마감경과 {len(pruned)}건 삭제")
        save_jobs(old)
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
    today = datetime.date.today().isoformat()
    stale = [x for x in fresh if (x.get("deadline") or "") < today]
    if stale:
        print(f"마감경과 {len(stale)}건 제외 (오래된 데이터 유입 방지)")
        fresh = [x for x in fresh if (x.get("deadline") or "") >= today]
    if not fresh:
        print("유효 신규 0건. 저장 없이 종료.")
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
    merged, pruned = prune_expired(merged)
    if pruned:
        print(f"마감경과 {len(pruned)}건 삭제")
    save_jobs(merged)
    # 스레드는 우선순위순으로 발송 버퍼에 적재 (오늘→내일 빈 슬롯). 발송은 send_queue.py가 정시에 처리.
    import quota
    allow = quota.remaining("threads", MAX_THREADS_PER_DAY)
    today = datetime.date.today().isoformat()
    picks = sorted([x for x in verified if (x.get("deadline") or "") >= today],
                   key=priority_key)[:allow]
    quota.consume("threads", len(picks))
    assigned, dropped = assign_slots(picks)
    print(f"신규 {len(verified)}건 반영. 스레드 버퍼 배정 {len(assigned)}건" +
          (f" ({', '.join(s['date']+' '+s['slot'] for s in assigned)})" if assigned else "") +
          (f". 슬롯 만석으로 탈락 {len(dropped)}건" if dropped else "") + f": {QUEUE_JSON}")

if __name__ == "__main__":
    main()
