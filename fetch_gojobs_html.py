#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plan B 수집기: API 키 없이 나라일터 목록 HTML에서 직접 수집.
- 목록(apmList, 최신순) 파싱 → 신규분만 상세 GET 1회 (근무지역·직급 추출 + 링크 실측 검증)
- 출력 형식은 fetch_jobs.py와 동일 (jobs.json). 이후 gen_articles.py로 연결.
- 예의범절: 2시간 간격, 페이지당 10건·최대 3페이지(30건), Verify 실패분은 저장 안 함.
- robots.txt에서 목록/상세 경로 차단 없음 확인됨 (2026-09-17).
"""
import json, os, re, sys, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from fetch_jobs import exact_url, priority_key, assign_slots, thread_text  # noqa
import quota

JOBS_JSON = os.path.join(BASE, "jobs.json")
QUEUE_JSON = os.path.join(BASE, "threads_queue.json")
LIST_URL = "https://www.gojobs.go.kr/apmList.do"
MAX_PAGES = int(os.environ.get("GOJOBS_PAGES", "3"))
ARTICLES_PER_DAY = int(os.environ.get("ARTICLES_PER_DAY", "5"))
MAX_THREADS_PER_DAY = int(os.environ.get("MAX_THREADS_PER_DAY", "5"))
UA = {"User-Agent": "Mozilla/5.0"}

ICON_CAT = {"공공": "공공기관", "지자체": "지자체", "국가": "국가기관", "교육": "교육청"}

def get(url, timeout=20):
    raw = urlopen(Request(url, headers=UA), timeout=timeout).read()
    try:
        t = raw.decode("utf-8")
        # 깨짐 감지: 대체문자가 많으면 EUC-KR로 재시도
        if t.count("\ufffd") > len(t) // 500:
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "mangled")
        return t
    except (UnicodeDecodeError, ValueError):
        return raw.decode("euc-kr", errors="replace")

def infer_type(title):
    t = title
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

ROW_RE = re.compile(
    r'alt="([^"]+)"[^>]*>\s*</div>\s*<a[^>]*?fn_apmView\(\'020\', \'(\d+)\'\)[^>]*?>(.+?)</a>\s*</td>\s*'
    r'<td[^>]*?>(.+?)</td>\s*<td[^>]*?>\s*([\d-]+).*?</td>\s*<td[^>]*?>\s*([\d-]+)\s*</td>',
    re.S,
)

def parse_list(html):
    items = []
    for icon, seq, title, org, posted, deadline in ROW_RE.findall(html):
        title = re.sub(r"\s+", " ", title).strip()
        org = re.sub(r"\s+", " ", org).strip()
        if not title or not seq:
            continue
        items.append({
            "id": "gojobs-" + seq,
            "title": title,
            "org": org,
            "category": ICON_CAT.get(icon, "공공기관"),
            "type": infer_type(title),
            "region": "전국",
            "posted": posted.strip(),
            "deadline": deadline.strip(),
            "tags": [],
            "summary": ["원문 공고문 확인 필수"],
            "source": "나라일터",
            "url": exact_url(seq),
        })
    return items

def enrich_and_verify(job, timeout=15):
    """상세 1회 GET: 링크 검증 + 근무지역·채용직급 추출. 실패시 None."""
    try:
        html = get(job["url"], timeout=timeout)
    except Exception:
        return None
    flat = re.sub(r"\s+", " ", html)
    if job["org"][:4] not in flat or job["title"][:8] not in flat:
        return None
    m = re.search(r"근무지역</th>\s*<td[^>]*?>(.+?)</td>", flat)
    if m:
        region = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        mm = re.match(r"([가-힣]{2})", region)
        job["region"] = mm.group(1) if mm else region[:2]
    m = re.search(r"채용직급</th>\s*<td[^>]*?>(.+?)</td>", flat)
    if m:
        grade = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        job["summary"] = [grade[:40], "접수 ~" + job["deadline"] + " 마감", " 세부 조건은 원문 공고문 확인"]
    return job

def main():
    old = json.load(open(JOBS_JSON, encoding="utf-8"))
    old_ids = {j["id"] for j in old}
    seen, fresh_all = set(), []
    for page in range(1, MAX_PAGES + 1):
        try:
            html = get(LIST_URL + "?" + urlencode(
                {"menuNo": 401, "mngrMenuYn": "N", "selMenuNo": 400, "pageIndex": page}))
        except Exception as e:
            print(f"목록 {page}p 실패: {e}", file=sys.stderr)
            break
        rows = [r for r in parse_list(html) if r["id"] not in seen and not seen.add(r["id"])]
        if not rows:
            break
        fresh_all += [r for r in rows if r["id"] not in old_ids]
    print(f"목록 수집: 신규 후보 {len(fresh_all)}건")
    verified, rejected = [], []
    for job in fresh_all:
        ok = enrich_and_verify(job)
        (verified if ok else rejected).append(job["id"] if not ok else ok)
    if rejected:
        print(f"링크 불일치 {len(rejected)}건 제외: {', '.join(rejected)}", file=sys.stderr)
    if not verified:
        print("검증 통과 0건. 저장 없이 종료.")
        return
    json.dump(verified + old, open(JOBS_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    allow = quota.remaining("threads", MAX_THREADS_PER_DAY)
    picks = sorted(verified, key=priority_key)[:allow]
    quota.consume("threads", len(picks))
    assigned, dropped = assign_slots(picks)
    print(f"신규 {len(verified)}건 반영. 스레드 버퍼 배정 {len(assigned)}건" +
          (f" ({', '.join(s['date']+' '+s['slot'] for s in assigned)})" if assigned else "") +
          (f". 슬롯 만석으로 탈락 {len(dropped)}건" if dropped else ""))

if __name__ == "__main__":
    main()
