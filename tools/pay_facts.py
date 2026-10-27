# -*- coding: utf-8 -*-
"""기관별 보수 팩트 (출처: 알리오 경영공시 2025년 결산, kbizin 집계 2026.09.28 반영분).
- avg: 일반정규직 1인당 평균보수액
- start: 신입사원 초임(공시값)
- contract: 무기계약직 1인당 평균보수액 (없으면 None)
- note: 산정 범위 주의 문구
"""

SRC = "알리오(공공기관 경영정보 공개시스템) 2025년 결산 경영공시"
BM = ("알리오 2025년 결산 공시 기준 공공기관 전체 일반정규직 1인당 평균보수는 7,376만 9천원, "
      "신입사원 평균초임은 4,031만 6천원입니다(무기계약직 미포함).")

FACTS = [
    (r"한국토지주택공사", dict(avg="8,408만원", start="4,118만원", contract=None)),
    (r"한국개발연구원", dict(avg="8,635만원", start="4,995만원", contract=None)),
    (r"대외경제정책연구원", dict(avg="7,775만원", start="3,855만원", contract=None)),
    (r"건강보험심사평가원", dict(avg="7,334만원", start="4,201만원", contract=None)),
    (r"국립암센터", dict(avg="8,242만원", start="4,324만원", contract=None)),
    (r"독립기념관", dict(avg="6,832만원", start="3,738만원", contract=None)),
    (r"한국기계연구원", dict(avg="8,293만원", start="4,700만원", contract=None)),
    (r"국립부산과학관", dict(avg="6,698만원", start="4,186만원", contract=None)),
    (r"한국환경연구원", dict(avg="8,516만원", start="4,083만원", contract=None)),
    (r"오송첨단의료산업진흥재단", dict(avg="6,283만원", start="3,720만원", contract=None)),
    (r"우체국물류지원단", dict(avg="6,067만원", start="4,353만원", contract=None)),
    (r"한국관광공사", dict(avg="8,335만원", start="3,780만원", contract=None)),
    (r"중소기업은행", dict(avg="1억 1,544만원", start="5,820만원", contract=None)),
    (r"국토안전관리원", dict(avg="7,121만원", start="4,203만원", contract=None)),
    (r"한국보훈복지의료공단", dict(avg="7,172만원", start="4,170만원", contract=None)),
    (r"분당서울대학교병원", dict(avg=None, start="4,459만원", contract=None)),
    (r"한국도로공사", dict(avg="9,069만원", start="4,237만원", contract="5,411만원")),
    (r"국민연금공단", dict(avg="7,646만원", start="4,105만원", contract="3,451만원")),
    (r"국민건강보험공단", dict(avg="7,041만원", start="4,321만원", contract="3,505만원")),
    (r"한국수자원공사", dict(avg="8,229만원", start="4,171만원", contract="5,174만원")),
    (r"한국연구재단", dict(avg="9,576만원", start="5,388만원", contract="3,931만원")),
    (r"한국환경공단", dict(avg="6,572만원", start="3,689만원", contract="3,654만원")),
    (r"한국해양수산연수원", dict(avg="5,989만원", start="2,826만원", contract="2,896만원")),
    (r"서민금융진흥원", dict(avg="7,030만원", start="4,322만원", contract="4,109만원")),
    (r"한국문화예술교육진흥원", dict(avg="5,984만원", start="3,415만원", contract="4,104만원")),
    (r"한국언론진흥재단", dict(avg="7,984만원", start="3,630만원", contract="6,280만원")),
    (r"국립공원공단", dict(avg="6,218만원", start="3,781만원", contract="3,620만원")),
    (r"한국남부발전", dict(avg="1억 127만원", start="4,698만원", contract=None)),
    (r"코레일유통", dict(avg="5,584만원", start="3,403만원", contract="3,682만원")),
    (r"우체국시설관리단", dict(avg="6,949만원", start="3,780만원", contract="3,726만원")),
    (r"한국산업인력공단", dict(avg="6,766만원", start="3,609만원", contract="3,297만원")),
    (r"전북대학교병원", dict(avg="7,729만원", start="4,008만원", contract="3,661만원")),
    (r"한전KPS", dict(avg="8,803만원", start="4,457만원", contract=None)),
    (r"대한적십자사", dict(avg="6,937만원", start="3,869만원", contract="4,017만원")),
    (r"한국청소년상담복지개발원", dict(avg="5,572만원", start="3,536만원", contract=None)),
    (r"한국등산[·\s]?트레킹지원센터", dict(avg="5,170만원", start="3,342만원", contract=None)),
]

# 국립병원군 (알리오 2025년 결산 분석 보도 — 메디파나뉴스)
NATIONAL_HOSPITAL = dict(
    avg="7,632만원", start="4,202만원",
    src="메디파나뉴스가 알리오 2025년 결산보고서를 분석한 13개 국립병원 집계",
)


def lookup(org):
    import re
    for pat, d in FACTS:
        if re.search(pat, org):
            return d, SRC
    if re.search(r"부산대학교병원|전북대학교병원|경북대학교병원|충남대학교병원|전남대학교병원", org):
        return None, None
    if "병원" in org:
        return None, None
    return None, None
