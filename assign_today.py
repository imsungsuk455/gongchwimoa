#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
아침 큐 배정 (에이전트 작성 기사만 노출 규칙, 2026-09-23).
- 오늘+내일 슬롯을 에이전트 작성(aw=1)·진행중 공고 중에서 최대 10건/일로 채운다.
- 품질 필터: 학교 교직·결과성(합격자발표 등) 제외, 같은 기관 하루 1건.
- 이미 posted/pending인 슬롯은 건드리지 않는다.
- 아침 에이전트가 실행 후 전문을 검수·수정하고 사용자에게 보고한다.
"""
import json, os, sys, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from fetch_jobs import (THREAD_SLOTS, CONTENT_SLOT, priority_key, thread_text, is_school_job,
                        is_specialist_job, load_buffer, SITE_URL, QUEUE_JSON, JOBS_JSON)  # noqa

RESULT_RE = ["합격자발표", "서류전형 합격자", "면접장소", "면접 장소", "최종합격"]
MAX_PER_DAY = 5  # 5슬롯제 (공고 4 + 콘텐츠 1, 2026-09-26)


def is_result(job):
    t = (job.get("title") or "") + " " + (job.get("org") or "")
    if any(k in t for k in RESULT_RE):
        return True
    # 자원봉사 모집은 채용 공고가 아니라 큐에서 제외 (2026-09-24)
    if "자원봉사" in t or "봉사자" in t:
        return True
    return False


def article_pay_point(j):
    """기사의 급여 섹션에서 첫 연봉 수치 읽기 (2026-10-09: 배정 시 자동 주입용).
    반환: (표기, 주의딱지) — 주의딱지가 있으면 본문 포인트로만 쓰고 후크에는 안 쓴다."""
    import re as _re
    try:
        t = open(os.path.join(BASE, "articles", j["id"] + ".html"), encoding="utf-8").read()
    except Exception:
        return None, False
    m = _re.search(r"<h2>급여·근무조건 읽는 법</h2>\s*<p>(.*?)</p>", t, flags=_re.S)
    if not m:
        return None, False
    para = _re.sub(r"<[^>]+>", "", m.group(1))
    cands = list(_re.finditer(r"((?:초봉|평균\s*연봉|평균연봉|신입\s*초봉|연봉|월급|월|일급)\s*(?:은|는|이)?\s*\d[\d,]*\s*만원)", para))
    if not cands:
        return None, False
    def _rank(m):
        s = m.group(1)
        if "초봉" in s or "신입" in s:
            return 0
        if "월급" in s or s.strip().startswith("월") or "일급" in s:
            return 1
        if "평균" in s:
            return 3
        return 2
    pm = sorted(cands, key=_rank)[0]
    label = _re.sub(r"\s+", " ", pm.group(1)).strip()
    label = _re.sub(r"^(초봉|평균\s*연봉|평균연봉|신입\s*초봉|연봉|월급|월|일급)[은는이]\s*", r"\1 ", label).strip()
    ctx = para[max(0, pm.start() - 60):pm.end() + 10]
    caveat = any(k in ctx for k in ["유사", "참고", "집계", "추정", "원문에서 확인", "원문 확인"])
    return label, caveat


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    jobs = json.load(open(JOBS_JSON, encoding="utf-8"))
    buf = load_buffer()
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))).date()
    days = [today.isoformat(),
            (today + datetime.timedelta(days=1)).isoformat()]
    # 날짜 지난 posted 정리 + 기존 슬롯 유지.
    # 정리 전 posted 기록을 posted_log.json에 누적 → 7일 내 발행분 재배정 방지 (2026-09-27)
    LOG_JSON = os.path.join(BASE, "posted_log.json")
    try:
        posted_log = json.load(open(LOG_JSON, encoding="utf-8"))
    except Exception:
        posted_log = []
    pruned = [s for s in buf.get("slots", [])
              if s.get("status") == "posted" and s.get("date", "") < days[0]]
    if pruned:
        seen = {(e.get("job_id"), e.get("date")) for e in posted_log}
        for s in pruned:
            key = (s.get("job_id"), s.get("date"))
            if key not in seen:
                posted_log.append({"job_id": s.get("job_id"), "date": s.get("date")})
                seen.add(key)
        with open(LOG_JSON, "w", encoding="utf-8") as f:
            json.dump(posted_log, f, ensure_ascii=False, indent=2)
        print(f"posted 기록 {len(pruned)}건 누적")
    buf["slots"] = [s for s in buf.get("slots", [])
                    if not (s.get("status") == "posted"
                            and s.get("date", "") < days[0])]
    queued_ids = {s.get("job_id") for s in buf["slots"]
                  if s.get("status") in ("pending", "posted")}
    cutoff = (today - datetime.timedelta(days=7)).isoformat()
    recent_posted = {e.get("job_id") for e in posted_log
                     if (e.get("date") or "") >= cutoff}
    art_dir = os.path.join(BASE, "articles")

    def has_article(j):
        p = os.path.join(art_dir, j["id"] + ".html")
        try:
            return "<!-- agent-written -->" in open(p, encoding="utf-8").read()
        except Exception:
            return False

    pool = [j for j in jobs
            if j.get("aw") == 1
            and j.get("type") != "임원"  # 임원 공모 제외 (2026-09-24)
            and not is_specialist_job(j)  # 의사 관련 제외 (2026-09-27)
            and (j.get("deadline") or "") >= days[0]
            and j["id"] not in queued_ids
            and j["id"] not in recent_posted  # 7일 내 발행분 재배정 방지 (2026-09-27)
            and not is_school_job(j)
            and not is_result(j)
            and has_article(j)]
    pool = sorted(pool, key=priority_key)
    # 새 공고 우선 (2026-09-28): posted 최신순을 1순위로. 같은 날짜 안에서는 기존 우선순위 유지 (stable).
    pool = sorted(pool, key=lambda j: j.get("posted") or "", reverse=True)
    # mopy식 선별 (2026-10-08): 기사에 연봉 수치 있는 공고를 최우선. 숫자가 후크가 된다.
    import re as _re
    def _has_salary(j):
        try:
            t = open(os.path.join(art_dir, j["id"] + ".html"), encoding="utf-8").read()
            nums = _re.findall(r"(\d[\d,]*)\s*만원", t)
            return any(int(x.replace(",", "")) >= 100 for x in nums)
        except Exception:
            return False
    pool = sorted(pool, key=_has_salary, reverse=True)
    print(f"배정 후보: {len(pool)}건 (에이전트 작성·진행중)")

    added = 0
    for d in days:
        filled = sum(1 for s in buf["slots"]
                     if s.get("date") == d
                     and s.get("status") in ("pending", "posted"))
        org_day = {s.get("org") for s in buf["slots"]
                   if s.get("date") == d and s.get("status") == "pending"}
        if filled >= MAX_PER_DAY:
            print(f"{d}: 이미 {filled}건, 추가 없음")
            continue
        # 콘텐츠 슬롯 (11:00): 아침 에이전트가 요일 시리즈로 본문 작성. 여기선 자리만 만든다.
        used_now = {s.get("slot") for s in buf["slots"]
                    if s.get("date") == d and s.get("status") in ("pending", "posted")}
        if CONTENT_SLOT in THREAD_SLOTS and CONTENT_SLOT not in used_now and filled < MAX_PER_DAY:
            buf["slots"].append({
                "date": d, "slot": CONTENT_SLOT, "job_id": "editorial",
                "org": "", "text": "", "comment": None,
                "status": "pending", "approved": False})  # 승인 후 발행 (2026-09-26)
            used_now.add(CONTENT_SLOT)
            filled += 1
            print(f"배정: {d} {CONTENT_SLOT} editorial (본문은 아침에 작성)")
        for j in list(pool):
            if filled >= MAX_PER_DAY:
                break
            org = (j.get("org") or "").strip()
            if org and org in org_day:
                continue
            # 빈 슬롯 찾기 (콘텐츠 슬롯 제외)
            used = {s.get("slot") for s in buf["slots"]
                    if s.get("date") == d and s.get("status") == "pending"}
            free = [s for s in THREAD_SLOTS if s not in used and s != CONTENT_SLOT]
            if not free:
                break
            slot = free[0]
            text = thread_text(j)
            pay_label, pay_caveat = article_pay_point(j)
            if pay_label:
                import re as _re2
                lines = text.split("\n")
                if lines and not _re2.search(r"\d", lines[0]):
                    org_short = (org.split()[-1] if org else "") or (j.get("type") or "")
                    if not pay_caveat:
                        lines[0] = f'"{pay_label} {org_short}"'
                        text = "\n".join(lines)
                    elif len(lines) > 2 and not _re2.search(r"\d+\s*만원", text):
                        lines.insert(2, pay_label + " 수준 (참고치, 원문 확인)")
                        text = "\n".join(lines)
            buf["slots"].append({
                "date": d, "slot": slot, "job_id": j["id"], "org": org,
                "text": text,
                "comment": f"자세한 공고 보러 가기 ▽\n{SITE_URL}articles/{j['id']}.html",  # 공고 글 댓글 링크 (2026-10-02 확정)
                "status": "pending", "approved": True})
            if org:
                org_day.add(org)
            pool.remove(j)
            filled += 1
            added += 1
            print(f"배정: {d} {slot} {j['id']}")
    buf["slots"] = sorted(buf.get("slots", []),
                          key=lambda s: (s.get("date", ""), s.get("slot", "")))
    with open(QUEUE_JSON, "w", encoding="utf-8") as f:
        json.dump(buf, f, ensure_ascii=False, indent=2)
    print(f"신규 배정 {added}건 완료.")


if __name__ == "__main__":
    main()
