#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스레드 발행 중복 방지 (2026-10-18 확정)

사용자 요구: "스레드 발행한거 겹치지 않게" — 같은 공고가 다른 날/다른 출처로 다시 나가지 않게 한다.

3중 차단:
1) job_id 영구 차단 — posted_log.json + 큐의 posted 이력에 있는 id는 다시 배정·발행하지 않는다.
2) 제목 지문 차단 — 출처(나라일터/잡알리오)가 달라도 같은 공고면 제목을 정규화한 지문이 같다.
   재공고·기간연장처럼 실제로 다시 올라온 공고도 같은 지문이므로 중복 발행되지 않는다.
3) 기관 쿨다운 — 같은 기관은 최근 N일(기본 3일) 안에 발행한 이력이 있으면 제외한다.
"""
import json, os, re, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_JSON = os.path.join(BASE, "jobs.json")
QUEUE_JSON = os.path.join(BASE, "threads_queue.json")
POSTED_LOG = os.path.join(BASE, "posted_log.json")
ORG_COOLDOWN_DAYS = 3


def norm_title(title):
    s = title or ""
    s = re.sub(r"[\[\]()（）·,.\-/〜~]", " ", s)
    s = re.sub(r"20\d{2}\s*년(?:도)?", " ", s)
    s = re.sub(r"제?\s*\d+\s*(?:분기|회|차|호)", " ", s)
    s = re.sub(r"(재공고|기간\s*연장|변경\s*모집|추가\s*모집)", " ", s)
    s = re.sub(r"(채용\s*공고|모집\s*공고|채용공고|모집공고)", " ", s)
    return re.sub(r"\s+", "", s)


def norm_org(org):
    s = org or ""
    s = re.sub(r"[\[\]()（）]", " ", s)
    s = re.sub(r"^(문화체육관광부|과학기술정보통신부|고용노동부|국방부|행정안전부|보건복지부)\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def build_index(extra_jobs=None, exclude_ids=None):
    """발행 이력 인덱스. extra_jobs: 이번 배정에서 이미 고른 공고 목록.
    exclude_ids: 인덱스에서 뺄 job_id (자기 자신 때문에 막히는 것 방지)."""
    jobs = {j["id"]: j for j in load_json(JOBS_JSON, [])}
    if extra_jobs:
        jobs.update({j["id"]: j for j in extra_jobs})
    skip = set(exclude_ids or [])
    entries = []  # (job_id, date)
    for e in load_json(POSTED_LOG, []):
        entries.append((e.get("job_id"), e.get("date") or ""))
    for s in load_json(QUEUE_JSON, {}).get("slots", []):
        if s.get("status") == "posted":
            entries.append((s.get("job_id"), s.get("date") or ""))
    ids, titles, org_dates = set(), set(), {}
    for jid, date in entries:
        if not jid or jid in skip:
            continue
        ids.add(jid)
        j = jobs.get(jid)
        if not j:
            continue
        titles.add(norm_title(j.get("title")))
        org = norm_org(j.get("org"))
        if org:
            org_dates.setdefault(org, []).append(date)
    return {"ids": ids, "titles": titles, "org_dates": org_dates, "jobs": jobs}


def check(job, date, index, cooldown_days=ORG_COOLDOWN_DAYS):
    """발행하면 안 되는 이유를 문자열로 반환. 문제 없으면 None."""
    jid = job.get("id")
    if jid in index["ids"]:
        return "이미 발행한 공고 (job_id)"
    t = norm_title(job.get("title"))
    if t and t in index["titles"]:
        return "이미 발행한 공고 (제목 지문 일치)"
    org = norm_org(job.get("org"))
    if org:
        try:
            d0 = datetime.date.fromisoformat(date)
        except Exception:
            d0 = None
        for d in index["org_dates"].get(org, []):
            try:
                dd = datetime.date.fromisoformat(d)
            except Exception:
                continue
            if d0 and 0 <= (d0 - dd).days <= cooldown_days:
                return f"기관 쿨다운 (최근 {cooldown_days}일 내 발행: {d})"
    return None


def register(job, date, index):
    """이번 배정에서 고른 공고를 인덱스에 즉시 반영 (같은 날 지문 중복 방지)."""
    index["ids"].add(job.get("id"))
    t = norm_title(job.get("title"))
    if t:
        index["titles"].add(t)
    org = norm_org(job.get("org"))
    if org:
        index["org_dates"].setdefault(org, []).append(date)


if __name__ == "__main__":
    import sys
    idx = build_index()
    print(f"발행 이력: id {len(idx['ids'])}건 · 제목 지문 {len(idx['titles'])}건 · 기관 {len(idx['org_dates'])}곳")
    jobs = {j["id"]: j for j in load_json(JOBS_JSON, [])}
    q = load_json(QUEUE_JSON, {})
    n = 0
    for s in q.get("slots", []):
        if s.get("status") != "pending":
            continue
        j = jobs.get(s.get("job_id") or "")
        if not j:
            continue
        r = check(j, s["date"], idx)
        if r:
            n += 1
            print(f"  ⚠ {s['date']} {s['slot']} {s['job_id']} — {r}")
    print(f"겹침 {n}건")
