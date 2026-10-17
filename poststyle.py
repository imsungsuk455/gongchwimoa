#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스레드 공고문 본문 생성 — 3줄 고정 패턴 (2026-10-17 사용자 확정)

    초임 3183만원대 세라믹기술원 행정직 채용 모집중
    접수마감 10-29까지
    전체 공고는 아래 댓글에서

- 1줄(후크): [연봉·초임 수치] + 기관 + 직무 + "채용 모집중"
  수치가 없으면 정년보장/무기계약/기관 속성으로 대체한다. 수치 지어내기 금지.
- 2줄(마감): "접수마감 MM-DD까지"  (D-3 이내면 "접수마감 MM-DD까지 · D-N" 덧붙임)
- 3줄(유도): "전체 공고는 아래 댓글에서"  ← 댓글에 기사 링크가 붙는다.
"""
import json, os, re, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_JSON = os.path.join(BASE, "jobs.json")
QUEUE_JSON = os.path.join(BASE, "threads_queue.json")
ARTICLE_DIR = os.path.join(BASE, "articles")

NOISE_WORDS = [
    "채용 공고", "채용공고", "모집 공고", "모집공고", "임용시험 공고", "임용시험 시행계획",
    "경력경쟁채용시험 공고", "경력경쟁채용 공고", "공개 채용", "공개채용", "신규 채용",
    "직원 채용", "채용 시험", "채용시험", "재공고", "기간연장", "변경 모집공고",
]
YEAR_RE = re.compile(r"20\d{2}\s*년(?:도)?")
ROUND_RE = re.compile(r"(?:제\s*)?\d+\s*(?:분기|회|차|호)")
BRACKET_RE = re.compile(r"[\[\(（].*?[\]\)）]")


def pay_label(job):
    """기사 '급여·근무조건' 섹션에서 초임/초봉 수치를 뽑아 '3183' 형태로 반환."""
    try:
        t = open(os.path.join(ARTICLE_DIR, job["id"] + ".html"), encoding="utf-8").read()
    except Exception:
        return None
    m = re.search(r"<h2>급여·근무조건 읽는 법</h2>\s*<p>(.*?)</p>", t, flags=re.S)
    if not m:
        return None
    para = re.sub(r"<[^>]+>", "", m.group(1))
    cands = list(re.finditer(
        r"((?:초봉|신입\s*초봉|초임|평균\s*연봉|평균연봉|연봉|월급)\s*(?:은|는|이)?\s*(?:약\s*)?(\d[\d,]*)\s*만원)", para))
    if not cands:
        return None
    def rank(mm):
        s = mm.group(1)
        if "초봉" in s or "초임" in s:
            return 0
        if "월급" in s:
            return 1
        if "평균" in s:
            return 3
        return 2
    best = sorted(cands, key=rank)[0]
    return best.group(2).replace(",", "")


def org_short(job):
    org = (job.get("org") or "").replace("(주)", "").replace("주식회사", "").strip()
    org = re.sub(r"^(문화체육관광부|과학기술정보통신부|고용노동부|국방부|행정안전부|보건복지부)\s+", "", org)
    org = re.sub(r"^국군조직\s*", "", org)
    parts = [p for p in org.split() if p]
    if not parts:
        return ""
    short = parts[-1]
    return short if len(short) <= 14 else short[:14]


GENERIC_ROLES = {"장애인", "채용", "모집", "직원", "공고", "정규직", "신입", "경력", "인턴"}


def role_of(job):
    """제목에서 직무명만 뽑는다. 괄호 안 직무가 있으면 그것을 우선."""
    title = job.get("title") or ""
    if "인턴" in title:
        return "청년인턴"
    for w in NOISE_WORDS:
        title = title.replace(w, " ")
    title = YEAR_RE.sub(" ", title)
    title = ROUND_RE.sub(" ", title)
    # 기관명 토큰 제거
    org_tokens = set((job.get("org") or "").split())
    title = " ".join(t for t in title.split() if t not in org_tokens)
    org = org_short(job)
    # 괄호 직무 우선 (예: (행정직), (시설관리원)). 중첩 괄호는 안쪽부터.
    for b in re.findall(r"\(([^()]{2,18})\)", title) + BRACKET_RE.findall(title):
        cand = b.strip("[]()（） ").strip()
        cand = re.sub(r"(신입|경력|정규직|기간제|재공고|기간연장)", "", cand)
        cand = re.sub(r"\s+", " ", cand).strip(" ,·/")
        if not (2 <= len(cand) <= 18):
            continue
        if cand in GENERIC_ROLES or cand in org:
            continue
        return cand
    title = re.sub(r"[\[\]()（）]", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -·/,")
    toks = [t for t in title.split() if len(t) >= 2 and not re.fullmatch(r"[\d,.]+", t)]
    if not toks:
        return ""
    role = toks[-1]
    role = re.sub(r"(직원채용|직원|채용|모집|공고|시험|분야|임용)$", "", role).strip()
    if len(role) < 2 and len(toks) >= 2:
        role = toks[-2]
    if role in GENERIC_ROLES or role in org:
        return ""
    return role[:18]


def hook_line(job):
    pay = pay_label(job)
    org = org_short(job)
    role = role_of(job)
    tail = " ".join(x for x in [org, role] if x)
    tail = re.sub(r"\s+", " ", tail).strip(" ,·/")
    if re.search(r"채용$", tail):
        tail = tail[:-2].strip()
    title = job.get("title") or ""
    if pay:
        return f"초임 {pay}만원대 {tail} 채용 모집중"
    if job.get("type") == "공무직" or "무기계약" in title:
        return f"정년보장 {tail} 채용 모집중"
    if "청년인턴" in title or "체험형" in title:
        return f"청년인턴 {tail} 모집중"
    if not tail:
        return "신규 채용 공고 모집중"
    return f"{tail} 채용 모집중"


def make_post(job):
    """3줄 고정 포맷."""
    d = (job.get("deadline") or "")[5:]
    line2 = f"접수마감 {d}까지" if d else "접수기간 원문 확인"
    try:
        left = (datetime.date.fromisoformat(job["deadline"]) - datetime.date.today()).days
        if 0 <= left <= 3:
            line2 += f" · D-{left}" if left else " · 오늘"
    except Exception:
        pass
    return f"{hook_line(job)}\n{line2}\n전체 공고는 아래 댓글에서"


def comment_of(job):
    return f"자세한 공고 보러 가기 ▽\nhttps://gongchwimoa.org/articles/{job['id']}.html"


def fill_queue(target_date=None, only_empty=True, approve=True, dates=None):
    """큐의 빈 본문 슬롯을 새 포맷으로 채운다. approve=True면 승인 처리(자동 발행용).
    dates=[...] 를 주면 그 날짜들만 처리한다. only_empty=False면 기존 본문도 새 포맷으로 덮는다."""
    jobs = {j["id"]: j for j in json.load(open(JOBS_JSON, encoding="utf-8"))}
    buf = json.load(open(QUEUE_JSON, encoding="utf-8"))
    today = target_date or datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
    targets = set(dates) if dates else {today}
    filled = 0
    for s in buf.get("slots", []):
        if s.get("date") not in targets or s.get("status") != "pending":
            continue
        jid = s.get("job_id") or ""
        if jid.startswith("editorial") or jid.startswith("blog"):
            continue
        j = jobs.get(jid)
        if not j:
            continue
        if only_empty and (s.get("text") or "").strip():
            pass
        else:
            s["text"] = make_post(j)
            filled += 1
        if not s.get("comment"):
            s["comment"] = comment_of(j)
        if approve:
            s["approved"] = True
    json.dump(buf, open(QUEUE_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return filled


if __name__ == "__main__":
    import sys
    jobs = {j["id"]: j for j in json.load(open(JOBS_JSON, encoding="utf-8"))}
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg and arg in jobs:
        print(make_post(jobs[arg]))
    elif arg == "fill":
        print("filled:", fill_queue())
    else:
        n = fill_queue()
        print(f"오늘 슬롯 본문 {n}건 생성")
