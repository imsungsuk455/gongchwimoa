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
import role_fixes as RF  # noqa

# 기본값 직무로 떨어지지 않도록 추가 직무를 앞쪽에 배치
B.ROLES = ER.EXTRA_ROLES + B.ROLES
B.INSTS = ER.EXTRA_INSTS + B.INSTS
B.INSTS = RF.INST_FIX + B.INSTS

MIN_WAGE = B.MIN_WAGE

# 제외: 학교 교원(교수초빙), 면허 전문직(간호) — 사이트·스레드 노출 제외 규칙
SKIP_IDS = {
    "gojobs-306642", "alio-306328",
    "gojobs-306808",  # 화성동탄우체국 서류전형 결과·면접 안내(결과성 공고)
    # 2026-10-29 추가
    "gojobs-306921",  # 충청지방데이터청 통계조사관 최종결과 공고(적격자 없음) — 결과성
    "alio-306461",    # 분당서울대병원 진료교수요원(핵의학과) — 의사면허·전문의 필수
    "alio-306441",    # 국립암센터 업무직 — 간호조무사 직종 포함(간호 제외 규칙)
    # 나라일터·잡알리오 중복 게시 → 나라일터 원문(발췌 풍부)만 작성
    "alio-306463",    # 북한산도봉 녹색순찰대(6차) ↔ gojobs-306962
    "alio-306453",    # 한국교통안전공단 실무직 ↔ gojobs-306941
    "alio-306454",    # 지리산경남 국립공원지킴이 2차 ↔ gojobs-306938
    "alio-306451",    # 북한산 국립공원지킴이(6차) ↔ gojobs-306937
    "alio-306442",    # 다도해서부 한시인력 환경관리 ↔ gojobs-306935
    "alio-306446",    # 지리산경남 산불감시원 ↔ gojobs-306931
    "alio-306432",    # 월악산 국립공원지킴이 ↔ gojobs-306891
    # 2026-10-30 추가: 면허 전문직(의사·간호) 제외 + 나라일터/잡알리오 중복 정리
    "gojobs-307006",  # 법원행정처 한시임기제(의료업무담당 5호) — 의료 면허 직위, 취준생 대상 아님
    "alio-306510",    # JDC 육아휴직 대체(보건관리) — 간호사 면허 필수 명시 ↔ gojobs-307016
    "gojobs-307016",  # 위 건과 동일 공고(나라일터)
    "alio-306515",    # 의료분쟁조정중재원 4차 ↔ gojobs-307017 (나라일터 원문 사용)
    "alio-306508",    # JDC 정규직 ↔ gojobs-307015
    "alio-306511",    # 소백산 국립공원지킴이 ↔ gojobs-307027
    "alio-306493",    # 창원경상국립대병원 장애인근로자(요약본) ↔ alio-306509
    "alio-306492",    # 창원경상국립대병원 계약직(요약본) ↔ alio-306507, 간호 직종 포함
    "alio-306487",    # 창원경상국립대병원 업무지원직(요약본) ↔ alio-306505
    "alio-306471",    # 농어촌공사 금강사업단 청소원 ↔ gojobs-306685
    "alio-306507",    # 창원경상국립대병원 계약직 — 뇌졸중코디네이터 등 간호면허 직종 포함
    # 2026-10-31 추가: 테스트 공고·학교 교직·면허 전문직·결과성·중복 정리
    "gojobs-307120",  # 제목 '테스트' — 수집 오류 잡음 공고
    "gojobs-307177",  # 양정고 정교사(국어·미술·일반사회) — 학교 교직 제외 규칙
    "gojobs-307079",  # 경찰병원 채용분야 의무직·약무직·간호직·간호조무직 — 면허 전문직 제외
    "gojobs-307159",  # 국립소방연구원 조리원 '원서접수 결과 공고' — 결과성
    "gojobs-307113",  # 국립현대미술관 장애인 제한경쟁 '서류전형 결과 공고' — 결과성
    "gojobs-307089",  # 국무조정실 전문임기제 원공고 → 변경공고(gojobs-307191)로 대체
    "alio-306547",    # 북한산도봉 산불감시원 ↔ gojobs-307166
    "alio-306534",    # 팔공산서부 국립공원지킴이 ↔ gojobs-307135
    "alio-306533",    # 지리산전남 산불감시원 ↔ gojobs-307119
    "alio-306530",    # 경주 국립공원 산불감시 ↔ gojobs-307111
    "alio-306528",    # 덕유산 산불감시원 ↔ gojobs-307104
    "alio-306526",    # 안전보건공단 개방형 직위 ↔ gojobs-307106
}


# 여러 분야를 한 공고로 묶은 모집 (임기제·공무직 등) — 단일 직무 블록을 쓰면 오해를 만든다
GENERIC_LABELS = ("일반 사무·운영", "현장 실무")

W_POOL = [
    "묶음 공고는 분야별 경쟁률 차이가 커서, 지원자가 적은 분야를 고르는 것도 전략이 됩니다.",
    "접수는 분야를 골라야 진행되므로 원서 작성 전에 지원 분야 코드를 확인해 두십시오.",
    "분야별 전형 일정이 다를 수 있어 서류 합격 발표일을 분야 기준으로 확인해야 합니다.",
    "같은 공고 안에서도 분야별 처우가 다르므로 보수는 본인 분야 기준으로 계산하십시오.",
]

MULTI_PAT = re.compile(r"외\s*\d+\s*개\s*분야|\d+\s*개\s*분야|분야\s*등|등\s*모집|,\s*[가-힣]+\s*(관리자|연구사|상담|지도자|편집원)")
MULTI_ROLE = {
    "label": "모집분야 묶음",
    "duty": "이 공고는 한 장의 공고문에 여러 모집분야를 함께 담은 형태입니다. 분야마다 담당 업무가 완전히 달라서, 같은 공고에 지원해도 배치되는 부서와 하는 일이 전혀 다를 수 있습니다. 공고문에는 보통 분야별 인원·직급·자격요건이 표로 정리되어 있고, 원서접수도 분야를 골라야 진행됩니다. 따라서 먼저 본인이 지원할 분야를 하나로 정하고, 그 분야의 자격요건과 근무기간만 따로 읽는 방식이 안전합니다. 여러 분야를 동시에 지원할 수 있는지는 공고문의 중복지원 제한 조항으로 확인해야 합니다.",
    "qual": "묶음 모집 공고는 분야별 요건이 서로 다르므로 한 분야의 요건을 다른 분야에 적용하면 안 됩니다. 학위·자격증·경력 요건이 분야마다 다르게 붙고, 직급도 5급 상당부터 9급 상당까지 섞여 있는 경우가 흔합니다. 시간선택제 분야는 주당 근무 시간이 따로 정해져 보수도 비례해 달라집니다. 공고문의 모집분야 표에서 본인 분야의 행만 확인하고, 우대 사항과 제출서류도 그 분야 기준으로 준비하십시오.",
    "iv": "면접은 지원한 분야의 직무를 기준으로 진행됩니다. 왜 여러 분야 중 그 분야를 골랐는지, 그 분야의 실무를 어느 정도 이해하는지 묻습니다. 다른 분야로 배치될 수 있다는 질문이 나오면 솔직하게 답하고, 본인 경험과 맞는 분야를 근거와 함께 설명하십시오.",
    "essay": "지원서 첫 문단에서 지원 분야를 명확히 밝히는 것이 가장 중요합니다. 묶음 공고는 같은 기관에 여러 지원자가 몰리므로, 어떤 분야에 왜 지원했는지가 드러나지 않으면 준비도가 낮게 평가됩니다. 그 분야의 실무 경험과 자격을 앞세우고, 다른 분야의 경험을 섞어 나열하지 마십시오.",
    "rec": ["공고 모집분야 중 하나의 요건을 충족하는 분", "분야별 근무기간·근무시간 차이를 확인한 분", "배치 분야를 수용할 수 있는 분"],
    "pay": "묶음 모집의 보수는 분야별 직급과 근무 형태에 따라 각각 다르게 정해집니다. 일반임기제는 연봉등급제, 시간선택제임기제는 주당 근무 시간에 비례한 보수, 공무직은 기관 임금표를 적용받습니다. 같은 공고 안에서도 총보수 차이가 크므로 본인 분야의 직급과 근무 시간을 기준으로 계산해야 합니다. 구체적 금액은 공고문의 분야별 처우표에서 확인하십시오.",
}

# 유형 오표기 정정 (제목에 '기간제'가 명시된 공고가 공무직/정규직으로 분류된 건)
TYPE_FIX = {
    "gojobs-306635": "기간제",   # 서천우체국 기간제 상시계약집배원(농어촌), 계약기간 2027-01-18까지
    "gojobs-306693": "기간제",   # 경기광주우체국 기간제상시집배원
    "alio-306353": "기간제",     # 도로공사 제설 기간제근로자(운전원)
    "alio-306344": "기간제",
    "alio-306350": "기간제",
    "alio-306329": "기간제",     # 폴리텍 기간제 대학운영직(육아대체_조리원)
    "gojobs-306695": "기간제",   # 국립공주대 학생생활관 기간제근로자(조리원)
    # 2026-10-28 정정: 제목·원문에 기간제/휴직대체/한시인력/계약·위촉이 명시된 건
    "alio-306404": "기간제",     # 폴리텍 전남캠퍼스 행정지원직(휴직대체)
    "alio-306368": "기간제",     # 폴리텍 부산캠퍼스 행정지원직(휴직대체_냉난방원)
    "alio-306391": "기간제",     # 도로공사 부산경남본부 제설 기간제근로자(운전원)
    "alio-306384": "기간제",     # 도로공사 강원본부 제설 기간제근로자(운전원)
    "alio-306360": "기간제",     # 도로공사 충북본부 제설 기간제근로자(운전원)
    "gojobs-306763": "기간제",   # 영동우체국 상시계약집배원(기간제)
    "gojobs-306785": "기간제",   # 인천송현초 사서(대체), 계약 2026.11.16~2027.2.13
    "gojobs-306749": "기간제",   # 충남대 기간제계약직 미화(장애인 제한경쟁)
    "gojobs-306757": "일용직",   # 지리산전남 국립공원지킴이(한시인력)
    "alio-306363": "일용직",     # 지리산전남 국립공원지킴이(한시인력)
    "alio-306398": "기간제",     # 분당서울대병원 계약업무지원직
    "alio-306397": "기간제",     # 분당서울대병원 계약보건·계약기술직
    "alio-306395": "기간제",     # 국토안전관리원 위촉 1~3급 수시채용
    # 2026-10-29 정정: 제목·원문에 기간제/한시인력/대체/계약기간이 명시된 건
    "alio-306456": "기간제",     # KISTEP 육아휴직 대체인력
    "alio-306450": "기간제",     # 도로공사 수도권본부 제설 기간제(운전원)
    "alio-306429": "기간제",     # 도로공사 서울경기본부 제설 기간제(운전원)
    "alio-306413": "기간제",     # 도로공사 광주전남본부 제설 기간제(운전원)
    "gojobs-306950": "기간제",   # 화천우체국 상시계약집배원(기간제), 채용시~11.30
    "gojobs-306937": "기간제",   # 북한산 국립공원지킴이, 2026.12.1~12.31 기간제근로자
    "gojobs-306938": "기간제",   # 지리산경남 국립공원지킴이 2차, 2026.12.1~12.31
    "gojobs-306868": "기간제",   # 석포초 통학차량안전도우미, 2026.12.1~2027.2.28
    "gojobs-306892": "기간제",   # 두원공고 사무직원 결원 대체
    "gojobs-306965": "임기제",   # 화천군 전문임기제 나급·시간선택제임기제 가급·다급만 모집
    # 2026-10-30 정정: 원문에 계약기간·대체·기간제가 명시된 건
    "gojobs-307023": "기간제",   # 보령시 유도팀 감독, 계약기간 2027.1.1~2028.12.31(2년)
    "gojobs-307027": "기간제",   # 소백산 국립공원지킴이, 계약기간 2026.12.1~12.31
    "gojobs-306997": "기간제",   # 덕산중 교육행정 대체직원
    "gojobs-306998": "기간제",   # 서울마포초 조리실무사 대체직원
    "gojobs-306999": "기간제",   # 서울성원초 기간제 교육실무사(늘봄)
    "gojobs-307004": "기간제",   # 서울인왕초 시간제 돌봄전담사 대체직원
    "gojobs-307037": "기간제",   # 휘문중 미화원 단시간, 원문 고용형태 '계약직'
    "gojobs-307038": "기간제",   # 명지중 조리사 휴직 대체
    "gojobs-307048": "기간제",   # 부산대 산학협력단 사무원(계약직)
    "alio-306494": "기간제",     # 경상국립대병원 단시간제 편의점 점원(계약직)
    "alio-306513": "공무직",     # 청소년상담복지개발원 공무직 일반직 4·5급
    # 2026-10-31 정정: 원문에 기간제·한시적·무기계약이 명시된 건
    "gojobs-307125": "기간제",   # 울산북부경찰서 구내식당 영양사, 원문 고용형태 '기간제'
    "gojobs-307144": "기간제",   # 양주우체국 별정우체국 기간제 집배원
    "gojobs-307115": "기간제",   # 서울연신초 기간제 교육실무사(늘봄)
    "gojobs-307135": "기간제",   # 팔공산서부 국립공원지킴이(4차), 한시인력 사업
    "gojobs-307178": "공무직",   # 육군 BCTP 예비역 장성관찰관, 원문 공고유형 '공무직근로자'
    "alio-306551": "기간제",     # 대한적십자사 비정규직(한시적) 장애인 에스코트
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
    """괄호 후보 중 직무로 보이는 것을 고른다 (지역·기관·재공고·직급 나열 괄호는 제외)."""
    BAD = re.compile(
        r"재공고|^공고$|채용$|임용$|^개방형|^국립대학|^기술팀$|^계약직$|^기간제$"
        r"|제\d+-\d+호|학교$|대학교|고등학교|포함_|^\d+급$|^\d+호$|임시계약직$"
        r"|^(기간제|기간제근로자|계약직근로자|일반임기제|전문임기제|한시임기제|시간선택제|임기제)$"
        r"|^(공업|전산|행정|시설|기계|전기|토목|건축|화공|농업|보건|간호|위생|환경|통계|사서|전송기술)$"
    )
    GOOD = re.compile(r"원|사|관|직|수|자|기|공|경비|조리|운전|집배|감호|통역|사감|청원")
    for m in re.finditer(r"\(([^)]{2,60})\)", title or ""):
        parts = [x.strip(" ,·") for x in re.split(r"[,·]", m.group(1))]
        for inner in parts:
            inner = re.sub(r"\d+\s*명", "", inner).strip(" ,·")
            if not inner or len(inner) < 2:
                continue
            if inner.count(",") >= 2:
                continue
            if re.match(r"^(19|20)\d\d|^제?\d+회", inner):
                continue
            if BAD.search(inner):
                continue
            if not GOOD.search(inner):
                continue
            if inner.count(" ") > 3:
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
        if re.search(r"바랍니다|참고하시기|첨부파일|붙임|문의|안내드립니다", s):
            continue
        if not re.search(r"명|면허|자격|경력|학위|소지|이수|우대|제한", s):
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


GENERIC_SUMMARY = ("공공기관 채용공시", "세부 조건은 원문 공고문 확인", "원문 공고문 확인 필수")


def enrich_summary(job):
    """알리오 요약이 껍데기인 공고는 원문 발췌에서 모집분야·요건 문구를 뽑아 채운다."""
    summ = [x for x in (job.get("summary") or []) if x and x not in GENERIC_SUMMARY]
    if len(summ) >= 2:
        return job
    raw = (job.get("excerpt") or "").replace("\r", "\n")
    picked = []
    for seg in re.split(r"[\n\u2028]|(?<=[.。])\s+", raw):
        cand = seg.strip(" -○ㅇ□*·\t")
        cand = re.sub(r"\s+", " ", cand)
        if not (10 <= len(cand) <= 90):
            continue
        if not (re.search(r"명|자격|면허|경력|학위|소지|기간|근무", cand)):
            continue
        picked.append(cand)
        if len(picked) >= 3:
            break
    if not picked:
        return job
    new = dict(job)
    new["summary"] = picked
    return new


def pay_section(job):
    org, jtype = job["org"], job.get("type", "")
    fact, src = PF.lookup(org)
    role_pay = B.find_role(job["title"])["pay"]
    parts = []
    if fact:
        bits = []
        if fact.get("avg"):
            bits.append(f"일반정규직 1인당 평균보수액은 {fact['avg']}")
        if fact.get("start"):
            bits.append(f"공시된 신입사원 초임은 {fact['start']}")
        lead_txt = f"{src} 기준으로 {org} " + ", ".join(bits) + "입니다. " if bits else ""
        parts.append(
            lead_txt
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
            "공시 자료로 확인되지 않은 금액은 이 글에서 추정해 제시하지 않습니다. "
            + PF.BM
        )
    role_pay = re.sub(r"[^.]*최저임금[^.]*\.\s*", "", role_pay)
    role_pay = re.sub(r"([가-힣])\.([가-힣])", r"\1. \2", role_pay).replace("  ", " ").strip()
    parts.append(role_pay)
    parts.append(MIN_WAGE)
    parts.append(B.PAY_TAIL_V[0])
    return " ".join(parts)



def dedupe_sections(sec):
    """같은 문장이 두 번 들어간 섹션을 정리한다 (풀 조합 충돌 방지)."""
    out = {}
    for k, v in sec.items():
        if isinstance(v, str):
            parts = [x.strip() for x in re.split(r"(?<=[.!?다])\s+", v) if x.strip()]
            seen, keep = set(), []
            for p in parts:
                key = re.sub(r"\s+", "", p)[:60]
                if key in seen:
                    continue
                seen.add(key)
                keep.append(p)
            out[k] = " ".join(keep)
        else:
            out[k] = v
    return out


def build(job, peers, cluster_idx=None, cluster_n=1):
    B.parse_role_label = safe_role_label
    multi = bool(MULTI_PAT.search(job["title"] or "")) and job.get("type") in (
        "임기제", "공무직", "기간제", "정규직")
    if multi:
        _orig = B.find_role
        B.find_role = lambda t: MULTI_ROLE
        try:
            sec = B.build_sections(job, peers)
        finally:
            B.find_role = _orig
        role = MULTI_ROLE
        # 묶음 공고는 단일 직무 전제 문장이 어긋나므로 lead·point를 다시 쓴다
        sec["lead"] = (
            f"핵심만 먼저: {job['org']}가 한 장의 공고문에 여러 모집분야를 담아 채용을 진행합니다. "
            f"접수 마감은 {job['deadline']}이고 근무지는 {job['region']}입니다. "
            f"고용형태는 {B.TYPES.get(job['type'], B.TYPES['기간제'])['label']}이며 공고는 {job['posted']}에 게시되었습니다."
        )
        sec["point"] = (
            f"이 공고의 첫 번째 포인트는 분야가 나뉘어 있다는 점입니다. 같은 공고라도 지원하는 분야에 따라 "
            f"직급·자격요건·근무기간이 모두 달라지므로, 공고문의 모집분야 표에서 본인 분야 행을 먼저 확정해야 합니다. "
            f"두 번째는 고용 형태입니다. {B.SHORT_STAB.get(job['type'], B.SHORT_STAB['기간제'])} "
            f"세 번째는 근무지입니다. {job['region']} 지역 근무로, 분야에 따라 전국 단위 근무가 가능한 경우도 있으니 "
            f"공고문의 근무예정지를 분야별로 확인하십시오. "
            + W_POOL[(cluster_idx or 0) % len(W_POOL)]
        )
    else:
        role = RF.OVERRIDE.get(job["id"]) or B.find_role(job["title"])
        if role is B.DEFAULT_ROLE or role["label"] in GENERIC_LABELS:
            # 제목에 직무가 없거나 일반 사무로 떨어지면 원문 발췌에서 직무를 찾는다
            # (예: '(강진) 대체 기간제근로자' → 발췌의 '통계조사원')
            hay = (job.get("excerpt") or "")[:1200]
            for pat, d in B.ROLES:
                if d["label"] in GENERIC_LABELS:
                    continue
                if re.search(pat, hay):
                    role = d
                    break
        if role is not B.DEFAULT_ROLE:
            _orig = B.find_role
            B.find_role = lambda t, _r=role: _r
            try:
                sec = B.build_sections(job, peers)
            finally:
                B.find_role = _orig
        else:
            sec = B.build_sections(job, peers)
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
                       + f" 이번 공고는 {job['org']}{B.josa(job['org'], '이', '가')} 직접 진행하는 자체 전형입니다. " + role["qual"]
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
        sec["point"] = (f"이 건은 {job['org']}{B.josa(job['org'], '이', '가')} 같은 시기에 낸 {cluster_n}개 모집분야 가운데 "
                        f"{role['label']} 직무입니다. 다른 직무 공고와 요건이 다르므로 지원 전에 모집분야 표를 대조해야 합니다. "
                        + sec["point"])
    if job["id"] in RF.LEAD_FIX:
        sec["lead"] = "핵심만 먼저: " + RF.LEAD_FIX[job["id"]].format(
            dl=job["deadline"], region=job["region"], posted=job["posted"])
    sec["pay"] = pay_section(job)
    return dedupe_sections(sec)


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

    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    tg = [j for j in B.targets(jobs, regen=regen) if j["id"] not in SKIP_IDS]
    if only:
        tg = [j for j in tg if j["id"] in only]
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
        jj = enrich_summary(j)
        sec = build(j, peers, cluster_idx=grp.index(j["id"]), cluster_n=len(grp))
        html = AS.build_agent(jj, sec, jobs)
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
