#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plan B 수집기: API 키 없이 나라일터 목록 HTML에서 직접 수집.
- 목록(apmList, 최신순) 파싱 → 신규분만 상세 GET 1회 (근무지역·직급 추출 + 링크 실측 검증)
- 출력 형식은 fetch_jobs.py와 동일 (jobs.json). 이후 gen_articles.py로 연결.
- 예의범절: 2시간 간격, 페이지당 10건·최대 3페이지(30건), Verify 실패분은 저장 안 함.
- robots.txt에서 목록/상세 경로 차단 없음 확인됨 (2026-09-17).
"""
import json, os, re, sys, datetime, html as htmlmod
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from fetch_jobs import exact_url, priority_key, assign_slots, thread_text, infer_type, prune_expired, is_school_job  # noqa
import quota

JOBS_JSON = os.path.join(BASE, "jobs.json")
QUEUE_JSON = os.path.join(BASE, "threads_queue.json")
LIST_URL = "https://www.gojobs.go.kr/apmList.do"
MAX_PAGES = int(os.environ.get("GOJOBS_PAGES", "3"))
ARTICLES_PER_DAY = int(os.environ.get("ARTICLES_PER_DAY", "5"))
MAX_THREADS_PER_DAY = int(os.environ.get("MAX_THREADS_PER_DAY", "10"))
UA = {"User-Agent": "Mozilla/5.0"}

ICON_CAT = {"공공": "공공기관", "지자체": "지자체", "국가": "국가기관", "교육": "교육청"}

def clean(s, limit=0):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = htmlmod.unescape(re.sub(r"\s+", " ", s)).strip()
    return s[:limit] if limit else s

def short_region(s):
    s = clean(s)
    for full, short in [("서울특별시", "서울"), ("부산광역시", "부산"), ("대구광역시", "대구"),
                        ("인천광역시", "인천"), ("광주광역시", "광주"), ("대전광역시", "대전"),
                        ("울산광역시", "울산"), ("세종특별자치시", "세종"), ("경기도", "경기"),
                        ("강원특별자치도", "강원"), ("강원도", "강원"), ("충청북도", "충북"),
                        ("충청남도", "충남"), ("전북특별자치도", "전북"), ("전라북도", "전북"),
                        ("전라남도", "전남"), ("경상북도", "경북"), ("경상남도", "경남"),
                        ("제주특별자치도", "제주"), ("제주도", "제주")]:
        if s.startswith(full):
            return short
    m = re.match(r"([가-힣]{2})", s)
    return m.group(1) if m else (s[:2] if s else "전국")

# 결과발표성 공고 제외 (채용速보 정체성 유지).
# 합격자 발표/면접 안내는 다음 전형 안내지 채용이 아니므로, 면접 언급이 있어도 제외한다.
ANNOUNCE_RE = re.compile(r"합격자|명단|발표|안내")
KEEP_IF_RE = re.compile(r"채용\s*공고|모집\s*공고|채용시험\s*(?:시행)?계획|임용시험|신규\s*채용")

def is_announcement(title):
    return bool(ANNOUNCE_RE.search(title)) and not bool(KEEP_IF_RE.search(title))

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
        if is_announcement(title):
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
        job["region"] = short_region(m.group(1))
    m = re.search(r"채용직급</th>\s*<td[^>]*?>(.+?)</td>", flat)
    grade = clean(m.group(1), 40) if m else ""
    m = re.search(r"(응시자격|지원자격|자격요건)</th>\s*<td[^>]*?>(.+?)</td>", flat)
    qual = clean(m.group(2), 80) if m else ""
    m = re.search(r"(전형절차|전형방법|선발방법|평가방법)</th>\s*<td[^>]*?>(.+?)</td>", flat)
    excerpt = clean(m.group(2), 600) if m else ""
    if len(excerpt) < 20:
        # 폴백: 상세 본문 셀 발췌 — 보수·수당·급여(훅 재료) 셀 우선, 없으면 가장 긴 상세 셀
        cands, pay = [], []
        for cm in re.finditer(r"<td[^>]*>(.*?)</td>", flat):
            txt = clean(cm.group(1))
            if len(txt) > 100 and re.search(r"응시|자격|전형|우대|결격|서류|면접|보수|수당|급여|연봉", txt):
                cands.append(txt)
            if re.search(r"보수|수당|급여|연봉|임금", txt):
                pay.append(txt)
        if pay:
            excerpt = max(pay, key=len)[:600]
        elif cands:
            excerpt = max(cands, key=len)[:600]
    summ = ["접수 ~" + job["deadline"] + " 마감", "세부 조건은 원문 공고문 확인"]
    if grade:
        summ.insert(0, grade)
    if len(qual) > 12:
        summ.insert(0, qual)
    job["summary"] = summ[:3]
    if len(excerpt) > 20:
        job["excerpt"] = excerpt
    return job

def main():
    old = json.load(open(JOBS_JSON, encoding="utf-8"))
    old_ids = {j["id"] for j in old}
    old, pruned = prune_expired(old)
    if pruned:
        print(f"마감경과 {len(pruned)}건 삭제")
        json.dump(old, open(JOBS_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
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
    today = datetime.date.today().isoformat()
    fresh_all = [x for x in fresh_all if (x.get("deadline") or "") >= today]
    verified, rejected = [], []
    for job in fresh_all:
        ok = enrich_and_verify(job)
        (verified if ok else rejected).append(job["id"] if not ok else ok)
    if rejected:
        print(f"링크 불일치 {len(rejected)}건 제외: {', '.join(rejected)}", file=sys.stderr)
    if not verified:
        print("검증 통과 0건. 저장 없이 종료.")
        return
    kept, pruned = prune_expired(verified + old)
    n_school = sum(1 for x in kept if is_school_job(x))
    kept = [x for x in kept if not is_school_job(x)]
    if n_school:
        print(f"학교 교직 계열 {n_school}건 제외 (사이트 미반영)")
    json.dump(kept, open(JOBS_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    allow = quota.remaining("threads", MAX_THREADS_PER_DAY)
    today = datetime.date.today().isoformat()
    pool = [x for x in verified if (x.get("deadline") or "") >= today and not is_school_job(x)]
    skipped = len(verified) - len(pool)
    picks = sorted(pool, key=priority_key)[:allow]
    if skipped:
        print(f"스레드 제외(학교) {skipped}건. 사이트에는 반영됨.")
    quota.consume("threads", len(picks))
    assigned, dropped = assign_slots(picks)
    print(f"신규 {len(verified)}건 반영. 스레드 버퍼 배정 {len(assigned)}건" +
          (f" ({', '.join(s['date']+' '+s['slot'] for s in assigned)})" if assigned else "") +
          (f". 슬롯 만석으로 탈락 {len(dropped)}건" if dropped else ""))

if __name__ == "__main__":
    main()
