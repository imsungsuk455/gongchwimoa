#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""최신 공고 해설 12섹션 작성기 (에이전트 리서치 반영판).

- 대상: posted가 KST 오늘/어제이고 articles/{id}.html에 agent-written 마커 없는 공고
- agent_bulk_write의 직무·기관 지식뱅크를 재사용하되,
  ① 기본값으로 떨어지는 직무를 extra_roles로 보강
  ② pay 섹션에 알리오 경영공시 실수치를 출처와 함께 명시
  ③ 유형 오표기(기간제 → 공무직) 정정
- 조립·검증은 agent_sections.build_agent 재사용 (한글 2000자+, 금지표현)
사용: python3 tools/write_articles.py [--dry]
"""
import datetime
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "tools"))

import agent_bulk_write as B  # noqa
import agent_sections as AS  # noqa
import pay_facts as PF  # noqa
import extra_roles as ER  # noqa

# 기본값 직무로 떨어지지 않도록 추가 직무를 앞쪽에 배치
B.ROLES = ER.EXTRA_ROLES + B.ROLES
B.INSTS = ER.EXTRA_INSTS + B.INSTS

MIN_WAGE = B.MIN_WAGE

# 제외: 학교 교원(교수초빙), 면허 전문직(간호) — 사이트·스레드 노출 제외 규칙
SKIP_IDS = {"gojobs-306642", "alio-306328"}

# 유형 오표기 정정 (제목에 '기간제'가 명시된 공고가 공무직/정규직으로 분류된 건)
TYPE_FIX = {
    "gojobs-306635": "기간제",   # 서천우체국 기간제 상시계약집배원(농어촌), 계약기간 2027-01-18까지
    "gojobs-306693": "기간제",   # 경기광주우체국 기간제상시집배원
    "alio-306353": "기간제",     # 도로공사 제설 기간제근로자(운전원)
    "alio-306344": "기간제",
    "alio-306350": "기간제",
    "alio-306329": "기간제",     # 폴리텍 기간제 대학운영직(육아대체_조리원)
    "gojobs-306695": "기간제",   # 국립공주대 학생생활관 기간제근로자(조리원)
}

CONTRACT_NOTE = {
    "공무직": "공무직(무기계약)으로 채용되면 정년까지 근무가 가능해 위 무기계약직 평균보수에 가깝게 형성됩니다.",
    "기간제": "이번 공고는 기간제 채용이라 위 정규직 평균보수는 그대로 적용되지 않습니다. 기간제 보수는 기관의 기간제 임금 기준을 따르며 계약 기간이 함께 정해집니다.",
    "일용직": "이번 공고는 단기·일용 채용이라 위 정규직 평균보수는 적용되지 않습니다. 근무 일수와 일당 기준으로 산정되므로 공고문 처우 항목을 확인해야 합니다.",
    "임기제": "임기제공무원은 공무원 보수규정상 연봉등급제를 적용받아 위 정규직 평균보수와 산정 방식이 다릅니다.",
    "청년인턴(체험형)": "체험형 인턴은 정규직 보수 체계가 아니라 별도 인턴료 기준을 적용받습니다.",
    "정규직": "정규직 신입의 경우 공시된 신입사원 초임이 출발점이 되고, 이후 호봉과 성과급에 따라 평균보수에 접근합니다.",
    "연수/실습": "연수·실습 과정은 정규직 보수 체계와 별개로 수당이 지급됩니다.",
}


def safe_role_label(title):
    """괄호 후보 중 직무로 보이는 것을 고른다 (지역·기관 나열 괄호는 제외)."""
    for m in re.finditer(r"\(([^)]{2,40})\)", title or ""):
        inner = re.sub(r"\d+\s*명", "", m.group(1)).strip(" ,·")
        if not inner:
            continue
        if inner.count(",") >= 2 or inner.count("·") >= 2:
            continue
        if re.match(r"^(19|20)\d\d|^제?\d+회", inner):
            continue
        if not re.search(r"원|사|관|직|수|자|기|공|자막|경비|조리|운전|집배", inner):
            continue
        return inner
    return None


REQ_HINT = re.compile(r"면허|자격|경력|학위|전공|소지|이수|우대|제한|가능한\s*자")


def excerpt_facts(job, limit=3):
    """원문 공고문 발췌에서 응시자격·조건 문구를 뽑아 공고별 고유 문장을 만든다."""
    raw = (job.get("excerpt") or "").replace("\r", "\n")
    cands = []
    for seg in re.split(r"[\n\u2028]|(?<=[.。])\s+|\s{2,}", raw):
        s = seg.strip(" -○ㅇ□*·\t")
        if len(s) < 12 or len(s) > 160:
            continue
        if not REQ_HINT.search(s):
            continue
        if s.count(" ") < 2:
            continue
        cands.append(re.sub(r"\s+", " ", s))
        if len(cands) >= limit:
            break
    if not cands:
        return ""
    joined = " / ".join(f"'{c}'" for c in cands)
    return f"이 공고 원문에 적힌 응시 조건 문구는 {joined}입니다. 문구를 그대로 읽고 본인 해당 여부를 하나씩 표시해 두면 서류 단계에서 탈락하는 일을 줄일 수 있습니다."


def unique_facts(job):
    """공고 제목·발췌에서 이 건에만 해당하는 사실(근무 지사·직무 세부·인원)을 뽑는다."""
    title = job.get("title") or ""
    outs = []
    m = re.search(r"\(([^)]{4,60})\)", title)
    if m and re.search(r"[가-힣]{2,}", m.group(1)):
        inner = re.sub(r"\s+", " ", m.group(1)).strip()
        if not re.match(r"^(19|20)\d\d", inner):
            outs.append(f"이 건의 근무 대상 지역·부서는 원문 기준 '{inner}'입니다")
    m2 = re.search(r"(\d+)\s*명", title)
    if m2:
        outs.append(f"공고 제목에 적힌 모집 인원은 {m2.group(1)}명입니다")
    for key in ("차량", "면허", "자격", "경력"):
        mm = re.search(r"[^.!\n]{0,40}" + key + r"[^.!\n]{0,50}", job.get("excerpt") or "")
        if mm:
            seg = re.sub(r"\s+", " ", mm.group(0)).strip(" -○ㅇ□*·")
            if 15 <= len(seg) <= 120:
                outs.append(f"원문에 '{seg}'라는 조건이 명시되어 있습니다")
                break
    return outs


# 같은 기관 동시 공고에서 문단이 겹치지 않도록 쓰는 추가 문장 풀
EXTRA_DUTY = [
    "이 직무는 담당 구역이 정해져 있어 근무지에 따라 실제 업무 환경이 달라집니다.",
    "근무조는 사업 일정과 기상 상황에 맞춰 편성되므로 면접에서 배치 구역을 확인하는 것이 좋습니다.",
    "업무 도구와 장비는 기관이 지급하며, 지급 품목과 교체 주기는 부서 규정을 따릅니다.",
    "실무는 선임자와 짝을 이뤄 익히는 방식이 일반적이라 첫 달은 교육과 현장 적응에 쓰입니다.",
    "업무 기록은 현장 확인과 사후 점검에 그대로 쓰이므로 기재 누락이 곧 평가 손실로 이어집니다.",
    "동일 직무라도 배치된 본부나 사업소에 따라 교대 방식과 업무량이 달라질 수 있습니다.",
]
EXTRA_QUAL = [
    "응시 자격 판단이 애매하면 접수 전에 채용 담당 부서로 문의하는 편이 안전합니다.",
    "제출서류는 공고문에 적힌 순서대로 정리하면 담당자가 확인하기 쉽습니다.",
    "경력 인정 여부는 증명서 기재 내용으로 결정되므로 직무 기술을 상세히 요청하십시오.",
    "우대 사항은 증빙이 없으면 반영되지 않으므로 해당 여부를 먼저 확인해야 합니다.",
    "자격증 유효 기간과 등록 상태를 접수 전에 점검하십시오.",
    "동점자 처리 기준이 공고문에 있으니 배점 항목을 미리 확인해 두십시오.",
]


CLUSTER_LEAD = [
    "같은 기관에서 여러 건이 동시에 올라온 공고 중 하나입니다. 이 글은 그중 {role} 직무 한 건만 다룹니다.",
    "같은 기관이 여러 직무를 함께 모집하고 있습니다. 이 공고의 모집분야는 {role}입니다.",
    "한 기관에서 여러 직무를 동시에 뽑는 경우, 공고문 한 장에 요건이 직무별로 나뉘어 있습니다. 이 글은 {role} 기준으로 정리했습니다.",
]


def pay_section(job):
    org, jtype = job["org"], job.get("type", "")
    fact, src = PF.lookup(org)
    role_pay = B.find_role(job["title"])["pay"]
    parts = []
    if fact:
        parts.append(
            f"{src} 기준으로 {org} 일반정규직 1인당 평균보수액은 {fact['avg']}, "
            f"공시된 신입사원 초임은 {fact['start']}입니다. "
            + (f"무기계약직 1인당 평균보수액은 {fact['contract']}으로 공시되어 정규직과 차이가 납니다. "
               if fact.get("contract") else "")
            + "평균보수액은 기본급에 고정수당·실적수당·성과상여금·급여성 복리후생비를 모두 합산한 값이라 "
              "월 기본급만 보고 판단하면 실제와 크게 어긋납니다."
        )
        note = CONTRACT_NOTE.get(jtype)
        if note:
            parts.append(note)
    else:
        parts.append(
            f"{org}의 구체적인 보수 수치는 이 공고 원문의 처우 항목과 보수표에서 확인해야 합니다. "
            "공시 자료로 확인되지 않은 금액은 이 글에서 추정해 제시하지 않습니다."
        )
    role_pay = re.sub(r"[^.]*최저임금[^.]*\.\s*", "", role_pay).replace("  ", " ").strip()
    parts.append(role_pay)
    parts.append(MIN_WAGE)
    parts.append(B.PAY_TAIL_V[0])
    return " ".join(parts)


def build(job, peers, cluster_idx=None, cluster_n=1):
    B.parse_role_label = safe_role_label
    sec = B.build_sections(job, peers)
    role = B.find_role(job["title"])
    B_parse = B.parse_role_label
    facts = excerpt_facts(job)
    if facts:
        sec["qual"] = sec["qual"] + " " + facts
    uniq = unique_facts(job)
    if cluster_n > 1:
        # 형제 공고는 문단 풀을 시프트해 문장 구성이 겹치지 않게 한다
        import hashlib
        s = int(hashlib.md5(job["id"].encode()).hexdigest(), 16) + cluster_idx * 7
        sec["proc"] = B.PROC_V[s % len(B.PROC_V)] + " " + B.POOL_PROC[(s >> 5) % len(B.POOL_PROC)]
        sec["sched"] = B.SCHED_V[(s >> 3) % len(B.SCHED_V)].format(
            posted=job["posted"], dl=job["deadline"],
            days=(__import__("datetime").date.fromisoformat(job["deadline"])
                  - __import__("datetime").date.fromisoformat(job["posted"])).days
        ) + " " + B.POOL_SCHED[(s >> 9) % len(B.POOL_SCHED)]
        sec["essay"] = role["essay"] + " " + B.ESSAY_TAIL_V[(s >> 6) % len(B.ESSAY_TAIL_V)].format(org=job["org"])
        sec["iv"] = (role["iv"] + " " + B.POOL_IV[(s >> 11) % len(B.POOL_IV)]
                     + " " + B.POOL_IV[(s >> 17) % len(B.POOL_IV)])
        sec["qual"] = (B.TYPES.get(job["type"], B.TYPES["기간제"])["text"]
                       + f" 이번 공고는 {job['org']}가 직접 진행하는 자체 전형입니다. " + role["qual"]
                       + " " + EXTRA_QUAL[cluster_idx % len(EXTRA_QUAL)]
                       + " " + B.POOL_QUAL[(s >> 13) % len(B.POOL_QUAL)]
                       + " " + B.POOL_QUAL[(s >> 19) % len(B.POOL_QUAL)])
        if facts:
            sec["qual"] = sec["qual"] + " " + facts
        sec["duty"] = (B.find_inst(job) + " " + role["duty"] + " "
                       + EXTRA_DUTY[cluster_idx % len(EXTRA_DUTY)] + " "
                       + B.POOL_DUTY[(s >> 7) % len(B.POOL_DUTY)])
        if uniq:
            sec["duty"] = sec["duty"] + " " + " ".join(uniq) + "."
        sec["pay"] = pay_section(job).replace(
            B.PAY_TAIL_V[0], B.PAY_TAIL_V[(s >> 21) % len(B.PAY_TAIL_V)], 1)
        intro = CLUSTER_LEAD[cluster_idx % len(CLUSTER_LEAD)].format(role=role["label"])
        sec["lead"] = intro + " " + sec["lead"]
        sec["point"] = (f"이 건은 {job['org']}가 같은 시기에 낸 {cluster_n}개 모집분야 가운데 "
                        f"{role['label']} 직무입니다. 다른 직무 공고와 요건이 다르므로 지원 전에 모집분야 표를 대조해야 합니다. "
                        + sec["point"])
    sec["pay"] = pay_section(job)
    return sec


def sitemap_write(jobs, today):
    live = [j for j in jobs if (j.get("deadline") or "") >= today and j.get("aw") == 1
            and j.get("type") != "임원"
            and not any(k in (j.get("title") or "") for k in ("전문의", "의사", "촉탁의", "공보의", "간호"))]
    urls = [f"  <url><loc>https://gongchwimoa.org/</loc><lastmod>{today}</lastmod>"
            "<changefreq>hourly</changefreq><priority>1.0</priority></url>"]
    for j in live:
        urls.append(f"  <url><loc>https://gongchwimoa.org/articles/{j['id']}.html</loc>"
                    f"<lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>")
    with open(os.path.join(BASE, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "\n".join(urls) + "\n</urlset>")
    return len(live)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    dry = "--dry" in sys.argv
    regen = "--regen" in sys.argv
    jobs = json.load(open(AS.JOBS_JSON, encoding="utf-8"))
    by_id = {j["id"]: j for j in jobs}

    fixed = []
    for jid, newtype in TYPE_FIX.items():
        j = by_id.get(jid)
        if j and j.get("type") != newtype:
            fixed.append((jid, j.get("type"), newtype))
            j["type"] = newtype

    tg = [j for j in B.targets(jobs, regen=regen) if j["id"] not in SKIP_IDS]
    role_of = {j["id"]: B.find_role(j["title"])["label"] for j in tg}
    dls = {}
    for j in tg:
        dls.setdefault(role_of[j["id"]], []).append(j["deadline"])

    orgs = {}
    for j in tg:
        orgs.setdefault(j["org"], []).append(j["id"])
    ok, short, bad = [], [], []
    for j in tg:
        peers = dls.get(role_of[j["id"]]) if len(dls.get(role_of[j["id"]], [])) > 1 else None
        grp = orgs[j["org"]]
        sec = build(j, peers, cluster_idx=grp.index(j["id"]), cluster_n=len(grp))
        html = AS.build_agent(j, sec, jobs)
        text = re.sub(r"<[^>]+>", "", html)
        ko = len(re.findall(r"[가-힣]", text))
        banned = [w for w in AS.BANNED if re.search(w, html)]
        if banned:
            bad.append((j["id"], str(banned)))
            continue
        if ko < 2000:
            short.append((j["id"], ko))
            continue
        if not dry:
            with open(os.path.join(AS.ART_DIR, j["id"] + ".html"), "w", encoding="utf-8") as fh:
                fh.write(html)
            j["aw"] = 1
        ok.append((j["id"], ko))

    print(f"대상 {len(tg)}건 · 작성 {len(ok)} · 분량미달 {len(short)} · 금지표현 {len(bad)}")
    print("유형 정정:", fixed if fixed else "없음")
    for x in short:
        print("  SHORT", x)
    for x in bad:
        print("  BANNED", x)
    ks = [k for _, k in ok]
    if ks:
        print(f"한글 평균 {sum(ks)//len(ks)}자 최소 {min(ks)}자 최대 {max(ks)}자")

    if not dry and ok:
        today = datetime.date.today().isoformat()
        json.dump(jobs, open(AS.JOBS_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        n = sitemap_write(jobs, today)
        import gen_articles as GA
        GA.refresh_index_seo(jobs, today)
        print(f"jobs.json aw 반영 · sitemap {n}건 · index SEO 갱신")
        print("OK_IDS=" + ",".join(i for i, _ in ok))


if __name__ == "__main__":
    main()
