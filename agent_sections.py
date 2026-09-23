#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
에이전트 작성 해설 섹션 -> articles/{id}.html 조립기.
- HTML 껍데기(SEO/게이트 요소)는 gen_articles.py와 동일하게 재사용.
- 템플릿 로테이션 문단 대신 에이전트가 리서치해서 쓴 섹션을 넣는다.
- 사용법: python3 agent_sections.py sections.json
  sections.json: {"job_id": "...", "lead": "...", "qual": "...", "point": "...",
    "proc": "...", "rec": [...3항], "check": [...4항], "sched": "...",
    "duty": "...", "essay": "...", "iv": "...", "pay": "...",
    "faq": [[q,a]x3]}
- 게이트 사전검증: 한글 2000자+, 금지표현 없음. 미달이면 작성 없이 exit 3.
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from gen_articles import HTML_HEAD, HTML_TAIL, dday  # noqa

JOBS_JSON = os.path.join(BASE, "jobs.json")
ART_DIR = os.path.join(BASE, "articles")
SITE_URL = os.environ.get("SITE_URL", "https://gongchwimoa.org/")
BANNED = ["100% 합격", "합격 보장", r"(?<!근)무조건"]

REQUIRED = ["lead", "qual", "point", "proc", "rec", "check", "sched",
            "duty", "essay", "iv", "pay", "faq"]


def build_agent(job, sec, all_jobs):
    d = dday(job["deadline"])
    dlabel = "마감" if d < 0 else ("D-DAY" if d == 0 else f"D-{d}")
    rec = "".join(f"<li>{r}</li>" for r in sec["rec"][:3])
    checklist = "".join(f"<li>{c}</li>" for c in sec["check"][:4])
    faq = "".join(f"<li><b>{q}</b><br>{a}</li>" for q, a in sec["faq"][:3])
    if job.get("excerpt"):
        excerpt_block = (
            "<h2>원문에서 확인한 전형 방식</h2>"
            f"<p class=\"quote\">{job['excerpt']}</p>"
        )
    else:
        excerpt_block = ""
    desc = (f"{job['org']} {job['title']} 정리. 마감 {job['deadline']}({dlabel}), "
            f"{job['region']}·{job['type']}. 지원자격·전형·추천대상 해설과 원문 링크.")
    cands = [j for j in all_jobs if j["id"] != job["id"]]
    same = [j for j in cands if j["category"] == job["category"]]
    rest = sorted([j for j in cands if j["category"] != job["category"]],
                  key=lambda x: x["deadline"])
    rels = (same + rest)[:3]
    rel_html = "".join(
        f"<a href=\"{r['id']}.html\">[{r['category']}] {r['title']} — 마감 {r['deadline']}</a>"
        for r in rels)
    summ = "".join(f"<li>{s}</li>" for s in job["summary"])
    body = f"""<!-- agent-written -->
<h1>[{job['category']}] {job['title']}</h1>
<p style="color:#666;font-size:.9rem;margin-top:8px">{job['org']} · {job['region']} · 마감 {job['deadline']} <b>({dlabel})</b> · 출처 {job['source']}</p>
<img class="hero" src="../thumbnails/{job['id']}.png" alt="{job['title']} 썸네일" loading="lazy">
<div class="lead">{sec['lead']}</div>
<h2>한눈에 보는 모집 조건</h2>
<table>
<tr><th>기관</th><td>{job['org']}</td></tr>
<tr><th>공고명</th><td>{job['title']}</td></tr>
<tr><th>고용형태</th><td>{job['type']}</td></tr>
<tr><th>근무지</th><td>{job['region']}</td></tr>
<tr><th>게시일</th><td>{job['posted']}</td></tr>
<tr><th>마감일</th><td>{job['deadline']} ({dlabel})</td></tr>
</table>
<h2>지원자격, 이렇게 읽으세요</h2>
<ul>{summ}</ul>
<p>{sec['qual']}</p>
<h2>이 공고의 포인트</h2>
<p>{sec['point']}</p>
<h2>전형은 어떻게 진행되나</h2>
<p>{sec['proc']}</p>
{excerpt_block}
<h2>이런 분께 추천해요</h2>
<ul>
{rec}
</ul>
<h2>지원 전 체크리스트</h2>
<ul>
{checklist}
</ul>
<h2>모집 일정과 제출 타이밍</h2>
<p>{sec['sched']}</p>
<h2>직무 이해하기: {job['category']}</h2>
<p>{sec['duty']}</p>
<h2>자기소개서 작성 팁</h2>
<p>{sec['essay']}</p>
<h2>면접 준비 포인트</h2>
<p>{sec['iv']}</p>
<h2>급여·근무조건 읽는 법</h2>
<p>{sec['pay']}</p>
<h2>자주 묻는 질문</h2>
<ul>
{faq}
</ul>
<a class="cta" href="{job['url']}" target="_blank" rel="noopener">원문 공고문 확인하고 지원하기 ↗</a>
"""
    html = HTML_HEAD.format(
        title=f"[{job['category']}] {job['title']}", desc=desc,
        canon=f"{SITE_URL}articles/{job['id']}.html",
        ogimg=f"{SITE_URL}thumbnails/{job['id']}.png")
    html += body + HTML_TAIL.format(rels=rel_html, source=job["source"])
    return html


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sec = json.load(open(sys.argv[1], encoding="utf-8"))
    missing = [k for k in REQUIRED if not sec.get(k)]
    if not sec.get("job_id") or missing:
        print(f"섹션 누락: {missing}", file=sys.stderr)
        sys.exit(2)
    jobs = json.load(open(JOBS_JSON, encoding="utf-8"))
    job = next((j for j in jobs if j["id"] == sec["job_id"]), None)
    if not job:
        print("job 없음", file=sys.stderr)
        sys.exit(2)
    html = build_agent(job, sec, jobs)
    text = re.sub(r"<[^>]+>", "", html)
    ko = len(re.findall(r"[가-힣]", text))
    if ko < 2000:
        print(f"분량 미달: 한글 {ko}자 (2000자 필요)", file=sys.stderr)
        sys.exit(3)
    for w in BANNED:
        if re.search(w, html):
            print(f"금지표현 포함: {w}", file=sys.stderr)
            sys.exit(3)
    os.makedirs(ART_DIR, exist_ok=True)
    out = os.path.join(ART_DIR, job["id"] + ".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    # 에이전트 작성 표시 (목록·사이트맵·스레드 노출 기준)
    all_jobs2 = json.load(open(JOBS_JSON, encoding="utf-8"))
    for x in all_jobs2:
        if x["id"] == job["id"]:
            x["aw"] = 1
            break
    json.dump(all_jobs2, open(JOBS_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"기사 작성 완료: {out} (한글 {ko}자)")


if __name__ == "__main__":
    main()
