#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공취모아 AdSense 승인 사전점검 (testlab 2026-09-11 반려 실측 규칙 반영).
- 승인 전: head 자동광고 + account 메타만 허용, 수동 <ins> 금지
- 기사: 한글 2000자+, 페이지별 고유 서술, 과장·보장 표현 금지
- 전 페이지: canonical, 신뢰 4종 링크, viewport, lang=ko
- 종료코드 0=통과, 1=미통과. cron 배포 전 게이트로 사용.
"""
import glob, os, re, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
PUB = "ca-pub-3484572882367046"
fails, warns = [], []

def check(name, cond, detail=""):
    if not cond:
        fails.append(f"{name} {detail}".strip())

pages = ["index.html", "about.html", "privacy.html", "terms.html", "contact.html"] + sorted(glob.glob("articles/*.html"))
print(f"점검 대상: {len(pages)}페이지")

for p in pages:
    t = open(os.path.join(BASE, p), encoding="utf-8").read()
    check(p, 'name="google-adsense-account"' in t and PUB in t, "adsense 메타/ID 누락")
    check(p, "<ins " not in t and "data-ad-slot" not in t, "수동 광고 유닛 존재(승인 전 금지)")
    check(p, "SLOT_ID" not in t, "슬롯 플레이스홀더 잔존")
    check(p, 'rel="canonical"' in t or p == "index.html" and "canonical" in t, "canonical 누락")
    check(p, 'lang="ko"' in t, "lang 누락")
    check(p, 'name="viewport"' in t, "viewport 누락")

for must in ["about.html", "privacy.html", "terms.html", "contact.html"]:
    t = open(os.path.join(BASE, "index.html"), encoding="utf-8").read()
    check("index 푸터", must in t, f"{must} 링크 누락")
    break

arts = sorted(glob.glob("articles/*.html"))
min_ko, ratios = 10**9, []
bodies = {}
for p in arts:
    t = open(os.path.join(BASE, p), encoding="utf-8").read()
    body = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    body = re.sub(r"<[^>]+>", "", body)
    ko = len(re.findall(r"[가-힣]", body))
    min_ko = min(min_ko, ko)
    bodies[p] = set(re.findall(r"[가-힣]{2,}", body))
check("기사 분량", min_ko >= 2000, f"최소 한글자수 {min_ko}")

# 고유성: 기사 간 공통 어휘 비율이 80%를 넘으면 cookie-cutter 의심
keys = list(bodies)
if len(keys) >= 2:
    worst = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = bodies[keys[i]], bodies[keys[j]]
            r = len(a & b) / max(len(a | b), 1)
            worst = max(worst, r)
    if worst >= 0.8:
        warns.append(f"기사 간 유사도 {worst:.0%} — 템플릿 비중 점검 권장")

# 과장·보장 표현 (면책 문맥 제외, '근무조건' 같은 정상 단어 제외)
banned = ["최첨단 AI", "정밀 분석", "100% 합격", "합격 보장", "(?<!근)무조건"]
for p in pages:
    t = open(os.path.join(BASE, p), encoding="utf-8").read()
    t2 = t.replace("합격을 보장하지 않습니다", "").replace("정보 제공용", "")
    for w in banned:
        check("과장표현", re.search(w, t2) is None, f"{p}에 '{w}'")

# 원문 링크 정확성: 목록식이 아닌 해당 공고 상세 URL이어야 함
bare = 0
for p in arts:
    t = open(os.path.join(BASE, p), encoding="utf-8").read()
    hrefs = re.findall(r'href="(https?://[^"]+)"', t)
    ext = [h for h in hrefs if "gojobs.go.kr" in h or "alio.go.kr" in h]
    for h in ext:
        if "empmnsn=" not in h and "idx=" not in h:
            bare += 1
check("원문링크", bare == 0, f"상세 아닌 링크 {bare}건(목록 링크 금지)")

# ads.txt / robots / sitemap
ads = open(os.path.join(BASE, "ads.txt"), encoding="utf-8").read()
check("ads.txt", "pub-3484572882367046" in ads, "ID 불일치")
check("robots.txt", os.path.exists(os.path.join(BASE, "robots.txt")), "없음")
sm = open(os.path.join(BASE, "sitemap.xml"), encoding="utf-8").read()
check("sitemap", sm.count("<loc>") >= 1, "URL 없음")
# sitemap은 진행중 공고만 (마감분 제외 — 2026-09-23 규칙)
import json as _json, datetime as _dt
_jobs = _json.load(open(os.path.join(BASE, "jobs.json"), encoding="utf-8"))
_today = _dt.date.today().isoformat()
_exp = {j["id"] for j in _jobs if (j.get("deadline") or "") < _today}
_live = {j["id"] for j in _jobs if (j.get("deadline") or "") >= _today}
check("sitemap-진행중", not any(f"articles/{i}.html" in sm for i in _exp), f"마감 {len(_exp)}건 중 sitemap 잔존")
check("sitemap-누락", all(f"articles/{i}.html" in sm for i in _live), "진행중 기사 sitemap 누락")
# 유형판정 회귀 테스트 (실측 오표기 재발 방지 — 2026-09-23)
sys.path.insert(0, BASE)
from fetch_jobs import infer_type
TYPE_PROBES = {
    "[한국수자원공사] 전남북부권지사 단기계약근로자(사무관리) 채용 공고": "일용직",
    "내장산국립공원백암사무소 한시인력(국립공원지킴이) 채용 공고": "일용직",
    "국회사무처 한시임기제공무원 7호(조경) 채용시험": "임기제",
    "(재)인천여성가족재단 아이사랑꿈터운영지원단 보육직5급(정규직) 채용 공고": "정규직",
    "한국마사회 임원(상임이사) 모집 공고": "임원",
    "한국선원복지고용센터 이사장 모집 공고": "임원",
    "서울특별시 서초구 시간선택제임기제공무원(교통행정) 채용계획 공고": "임기제",
    "2026년 PAO 인턴 채용 공고": "연수/실습",
    "계약직 연구원(데이터기반정책연구팀) 재공고": "기간제",
}
for _title, _want in TYPE_PROBES.items():
    _got = infer_type(_title)
    check("유형판정", _got == _want, f"'{_title[:22]}...' → {_got} (기대 {_want})")
# 홈페이지 정적 SEO 블록 (JS 미실행 크롤러용 — 2026-09-23 규칙)
_idx = open(os.path.join(BASE, "index.html"), encoding="utf-8").read()
check("index-SEO", "SEO_STATIC_START" in _idx and _idx.count("articles/") >= 20, "정적 공고 링크 20개 미만")
check("privacy", "애드센스" in open(os.path.join(BASE, "privacy.html"), encoding="utf-8").read(), "광고 쿠키 고지 누락")

print(f"기사 {len(arts)}건 · 최소 한글자수 {min_ko}")
for w in warns:
    print("WARN:", w)
if fails:
    print(f"FAIL {len(fails)}건:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS: 승인 신청 가능 상태")
