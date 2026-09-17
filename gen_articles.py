#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jobs.json -> articles/{id}.html 기사형 페이지 자동생성.
- 목록 복붙이 아니라 '해석 기사'로 만들어 AdSense thin-content 회피 + SEO 롱테일 확보.
- cron(fetch_jobs.py) 뒤에 이어 실행하면 신규 공고도 자동 기사화.
- 분량: 한글 2000자 이상, 고유 서술 (결과 유형명·기관명·마감일·지역을 본문에 녹임).
- 썸네일 기본옵션: PIL 로컬렌더 (카테고리 색상 + 공고제목 텍스트, 1200x630).
  외부 AI 이미지 없이 cron에서 즉시 생성. 비용 0원. thumbnails/{id}.png
"""
import json, os, datetime, hashlib

# 썸네일: PIL 로컬 렌더가 기본값 (외부 API 불필요, cron 즉시 생성, 비용 0원)
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_JSON = os.path.join(BASE, "jobs.json")
ART_DIR = os.path.join(BASE, "articles")
THUMB_DIR = os.path.join(BASE, "thumbnails")
SITE_URL = os.environ.get("SITE_URL", "https://gongchwimoa.org/")
ADSENSE = "ca-pub-3484572882367046"

# ---- 썸네일 기본옵션 (간단형: 카테고리 색상 + 공고제목 텍스트) ----
CAT_COLORS = {
    "청년인턴": "#7C4DFF", "교육청": "#0B8A5F", "공무직": "#B26A00",
    "공기업": "#0B5FFF", "공공기관": "#334155", "지자체": "#0E7490",
    "국가기관": "#1D4ED8",
}
FONT_BOLD = "C:\\Windows\\Fonts\\malgunbd.ttf"
FONT_REG = "C:\\Windows\\Fonts\\malgun.ttf"
# Linux 러너용 나눔폰트 대체 경로 (워크플로우에서 fonts-nanum 설치)
FONT_BOLD_CANDS = [os.environ.get("THUMB_FONT_BOLD", ""), FONT_BOLD,
                   "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"]
FONT_REG_CANDS = [os.environ.get("THUMB_FONT_REG", ""), FONT_REG,
                  "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"]

def _font(cands, size):
    if isinstance(cands, str):
        cands = [cands]
    for path in cands:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur); cur = ch
    if cur:
        lines.append(cur)
    return lines

def make_thumb(job):
    """1200x630 썸네일: 제목만 심플하게 (작은 브랜드명 + 큰 제목). PIL 로컬 생성."""
    os.makedirs(THUMB_DIR, exist_ok=True)
    W, H = 1200, 630
    bar = CAT_COLORS.get(job.get("category", ""), "#0B5FFF")
    img = Image.new("RGB", (W, H), "#ffffff")
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 0, 26, H], fill=bar)  # 카테고리 구분선
    f_brand = _font(FONT_REG_CANDS, 40)
    f_title = _font(FONT_BOLD_CANDS, 66)
    dr.text((100, 90), "공취모아", font=f_brand, fill="#94a3b8")
    lines = _wrap(dr, job["title"], f_title, W - 200)[:3]
    y = (H - len(lines) * 92) // 2 + 20
    for ln in lines:
        dr.text((100, y), ln, font=f_title, fill="#101828")
        y += 92
    out = os.path.join(THUMB_DIR, job["id"] + ".png")
    img.save(out, optimize=True)
    return out

# ---- 직무 이해 가이드 (카테고리별, 기사 분량 확보용) ----
DUTY_GUIDE = {
    "청년인턴": "체험형 인턴의 실제 업무는 행정보조, 자료 정리, 민원 응대 보조가 중심입니다. 거창한 스펙보다 성실함과 기본 OA 활용 능력을 어필하는 게 통과율이 높습니다. 인턴 수료증은 이후 정규직 지원 때 가점으로 이어지는 기관이 많으니, 수료 조건(출근율 등)도 미리 확인해 두세요.",
    "교육청": "학교·교육청 채용의 실무는 학사 지원, 급식·돌봄 보조, 행정실무가 중심입니다. 교원자격증이나 관련 자격증 소지 여부가 서류의 핵심 변수이므로 자격 취득일과 자격번호를 정확히 기재하세요. 방학 중 근무 조건이 평소와 다른 경우가 많아 원문의 근무조건란을 별도로 확인해야 합니다.",
    "공무직": "공무직 실무는 시설·환경·조리·운전 등 현장 업무가 중심입니다. 관련 자격증(기능사 이상)이나 실무 경력이 있으면 서류에서 강하게 어필됩니다. 교대·주말 근무와 실제 수령액(수당 포함)을 원문 보수표에서 대조하고 지원하는 것이 실패를 줄이는 방법입니다.",
    "공기업": "공기업 실무는 직무기술서(NCS) 기반으로 평가됩니다. 지원 분야의 직무기술서를 내려받아 필요 지식·기술·태도 항목을 자기소개서에 그대로 녹이는 것이 가장 확실한 전략입니다. 필기전형이 있는 공고는 NCS 직업기초능력 준비 기간을 마감일에서 역산해 확보하세요.",
    "지자체": "지자체 채용은 해당 지역 이해도와 정주 의지를 봅니다. 거주 요건이 없더라도 지역 연고나 이해를 자기소개서에 담으면 좋은 평가를 받습니다. 임기제·개방형은 민간 경력을 그대로 인정받는 경우가 많으니 경력증명서를 빠짐없이 준비하세요.",
    "국가기관": "국가기관 채용은 법령상 결격사유 심사가 엄격합니다. 병역, 정년, 겸직 금지 조항을 본인 상황에 대입해 먼저 점검하세요. 보안·신원조회가 필요한 직위는 합격 후에도 탈락 사유가 될 수 있어 사전에 결격 여부를 확인하는 것이 시간을 아끼는 길입니다.",
}
DEFAULT_GUIDE = "공공기관 실무의 공통분모는 직무기술서와 성실성입니다. 채용 분야의 직무기술서를 내려받아 필요 역량을 자기소개서에 그대로 녹이세요. 공공 채용은 블라인드 전형이 많아 사진·학교·출신지를 가리는 대신 직무 연관 경험의 구체성이 당락을 가릅니다."

# ---- 문단 로테이션 (섹션별 독립 할당: 전체 콤보 충돌 방지) ----
def _v(job, salt, n=3):
    return int(hashlib.md5((job["id"] + "#" + salt).encode()).hexdigest(), 16) % n

PROCESS_TEXTS = [
    "대부분 서류심사 후 면접심사 순으로 진행됩니다. 서류에서는 지원서·자기소개서의 직무 적합성을 보고, 면접에서는 실무 이해도와 근무 지속 가능성을 봅니다. 마감일({deadline}) 직전에는 접속이 몰려 원서 접수가 막히는 경우가 있으니 최소 하루 전 제출을 권합니다. 제출 후에는 접수번호·수험표 출력 여부를 반드시 확인하세요.",
    "전형은 서류심사로 시작해 면접심사로 끝나는 2단계가 기본입니다. 서류 단계의 평가자는 지원서와 자기소개서에서 직무 적합성을 찾고, 면접 단계에서는 실무 이해도와 오래 근무할 사람인지를 확인합니다. 마감일({deadline}) 당일 접수는 시스템 지연이 잦으니 하루 먼저 끝내 두는 게 안전합니다. 접수번호와 수험표 출력까지 마쳐야 접수가 완료됩니다.",
    "일반적인 순서는 서류심사 통과 후 면접심사입니다. 서류에서는 직무와 연결되는 경험이 있는지, 면접에서는 그 경험을 직접 설명할 수 있는지를 봅니다. 마감일({deadline}) 코앞에 몰리면 원서 접수 자체가 안 될 수 있으니 최소 하루 전에 제출하세요. 제출 뒤에는 접수번호·수험표가 정상 발급됐는지 확인이 필수입니다.",
]
ESSAY_TEXTS = [
    "공공기관 자기소개서 심사는 화려한 문장보다 직무 연관 경험의 구체성을 봅니다. 첫 문단에는 지원 분야({category})와의 연결고리를 한 줄로 선언하고, 본론에는 숫자(기간·규모·성과)가 들어간 경험 두 개를 배치하고, 마무리는 입사 후 1년 안에 해낼 일을 적으세요. {org} 지원서에 흔한 감점 요인은 세 가지입니다. 모집 분야와 무관한 장황한 성장 과정, 증빙 없는 주장(자격·경력), 그리고 마감일 오기재입니다. 특히 {type} 전형은 실무 투입 속도를 보기 때문에 즉시 근무 가능함을 문장으로 명시하면 좋습니다.",
    "자기소개서에서 평가자가 찾는 건 직무와의 연결고리입니다. 서두에 지원 분야({category})를 택한 이유를 한 문장으로 밝히고, 이어서 수치로 증명되는 경험 두 가지를 구체적으로 서술하세요. 마무리는 입사 후 1년의 실행 계획으로 닫습니다. {org} 지원자가 자주 놓치는 감점 포인트는 분야와 동떨어진 성장 배경 나열, 근거 없는 역량 주장, 마감일({deadline}) 착오입니다. {type} 모집은 빠른 실무 적응이 관건이라 출근 가능 시점을 분명히 적는 것이 플러스가 됩니다.",
    "좋은 자기소개서의 공식은 단순합니다. 지원 분야({category})와의 인연 한 줄, 숫자가 박힌 경험 두 개, 입사 후 포부 한 단락입니다. 반대로 {org} 서류 탈락 사유 상위권은 늘 비슷합니다. 직무와 무관한 자서전식 전개, 증빙 자료와 어긋나는 주장, 마감일({deadline}) 실수입니다. {type} 전형 지원자라면 채용 즉시 업무가 가능하다는 점을 글로 못 박아 두세요. 실무 투입 속도가 가산점처럼 작용합니다.",
]
INTERVIEW_TEXTS = [
    "면접은 서류에 쓴 경험의 진위 확인과 조직 적합성 검증이 목적입니다. 자기소개서에 적은 두 가지 경험을 1분 스피치로 말할 수 있게 연습하고, {org}의 최근 보도자료나 경영공시에서 핵심 사업 하나를 골라 지원 분야와 연결해 답변을 준비하세요. 마지막 질문 시간에는 근무지({region})·근무형태({type})를 감당할 수 있다는 의지를 짧게 밝히는 것이 효과적입니다. 복장은 단정하게, 도착은 30분 전에, 질문에는 결론부터 말하는 것이 공공기관 면접의 기본입니다.",
    "면접관의 질문은 두 갈래입니다. 서류 내용의 사실 관계 확인, 그리고 우리 조직에 맞을지에 대한 판단입니다. 자소서의 핵심 경험 두 개를 1분 안에 설명하는 연습을 해두고, {org}의 대표 사업 하나를 지원 분야({category})와 엮은 답변을 준비해 가세요. 마무리 질문에서는 근무지({region})와 {type} 근무가 가능하다는 뜻을 간결하게 전하는 게 좋습니다. 단정한 복장, 30분 전 도착, 결론 우선 답변이 기본 수칙입니다.",
    "면접 준비의 핵심은 자소서 방어와 기관 이해입니다. 적은 경험을 조리 있게 설명할 수 있어야 하고, {org}이 무슨 일을 하는 기관인지 한 가지 사업이라도 말할 수 있어야 합니다. 지원 분야({category}) 지식과 연결 지으면 점수가 오릅니다. 끝인사에서는 근무지({region})·{type} 조건을 수용한다는 의사를 분명히 하세요. 일찍 도착해 여유를 갖고, 두괄식으로 답하는 지원자가 좋은 인상을 남깁니다.",
]
# ---- 일정·급여 2종 로테이션 ----
SCHED_TEXTS = [
    "게시일은 {posted}, 마감은 {deadline}입니다. {left} 공공 채용은 마감일 24시간 전부터 지원자가 몰려 접수 페이지가 느려지거나 증빙 업로드가 실패하는 일이 잦습니다. 일정 운영의 정석은 이렇습니다. 첫날에는 공고문과 직무기술서를 출력해 응시자격·우대사항에 형광펜을 치고, 중간 기간에는 자기소개서 초안과 증빙 스캔을 끝내고, 마감 전날에는 접수 시스템에 미리 입력까지 마쳐 두는 것입니다. 마감 당일에 처음 접속하는 지원자가 가장 많이 탈락합니다. 접수번호가 발급되고 수험표(또는 접수확인서)가 출력돼야 접수가 끝난 것이니, 제출 후 확인증까지 꼭 챙기세요.",
    "이번 공고의 접수 기간은 {posted}부터 {deadline}까지입니다. {left} 원서 접수는 시작일보다 마감일에 몰리는 구조라, 서버가 느려지는 마감 당일은 피하는 게 상책입니다. 권장 스케줄을 짜보면 첫째 날 공고문 정독과 지원자격 체크, 중간 날 자기소개서 작성과 증빙 준비, 마감 전날 접수 시스템 사전 입력입니다. 특히 {org} 채용은 마감 이후 추가 접수를 받지 않으니, 접수번호와 확인증 출력까지 마쳐야 비로소 지원 완료입니다.",
]
PAY_TEXTS = [
    "공고문의 보수 표기는 호봉·수당·상여를 합친 기준이 아니라 기본급 기준인 경우가 많습니다. 실제 수령액은 원문의 보수·복무 조항과 동일 기관 재직자 채용 후기를 함께 봐야 가늠이 됩니다. {type} 공고라면 계약 기간, 연장·전환 조건, 4대 보험과 퇴직금 적용 여부를 원문에서 반드시 확인하세요. 근무지({region})가 도서·산간이거나 교대 근무가 포함된 경우에는 주거 지원·통근버스 조항도 체크리스트에 넣으세요.",
    "급여표를 볼 때는 기본급과 실수령액을 구분해야 합니다. 공고문 수치는 대개 기본급이라 수당·상여가 빠진 금액입니다. {type} 모집에서는 계약 기간과 갱신 조건, 4대 보험·퇴직금 적용이 핵심 체크 항목입니다. {org} 원문의 보수 규정을 펼치고, 근무지({region})가 외곽이거나 야간·주말 근무가 있다면 주거·교통 지원 조항까지 확인한 뒤 지원서를 내세요.",
]
POINT_TEXTS = [
    "이 공고의 관전 포인트는 '{tag}'입니다. {org}이 내건 조건 가운데 '{point}' 대목이 서류의 분수령이 됩니다. 해당되면 주저 없이 지원하고, 애매하면 원문 공고문의 세부 조항을 먼저 대조해 보세요. {dlabel} 일정상 오늘 내로 판단하는 게 좋습니다.",
    "'{tag}' 조건을 눈여겨보세요. 이번 {org} 모집에서 '{point}' 항목이 사실상 1차 필터 역할을 합니다. 본인이 맞는다면 지원 우선순위를 맨 위로 올리고, 아니라면 비슷한 조건의 관련 공고 3개를 함께 검토해 차선을 마련해 두세요.",
    "합격 가능성을 가르는 한 줄은 '{point}'입니다. 태그로 치면 '{tag}'에 해당하는 지원자가 유리한 구조입니다. {org} 공고는 {dlabel}이라 시간이 촉박하니, 해당자는 오늘 지원서를 열고 비해당자는 관련 공고로 눈을 돌리는 결단이 필요합니다.",
]

# ---- 체크리스트 3종 로테이션 ----
CHECKLISTS = [
    ["원문 공고문의 응시자격·결격사유 정독했는가", "자격증·경력증명서 등 증빙 스캔 준비됐는가",
     "마감일({deadline}) 전날까지 접수 가능한가", "근무지({region})·근무형태({type}) 감당 가능한가"],
    ["{org} 원문 공고문 저장했는가(공고 변경 대비)", "지원서 초안과 증빙 파일이 준비됐는가",
     "접수 마감일 {deadline}({dlabel})을 달력에 표시했는가", "{region} 출퇴근·거주 조건이 맞는가"],
    ["응시자격 중 본인 해당 항목에 표시했는가", "가점·우대 증빙 발급 소요일을 확인했는가",
     "마감 당일이 아닌 {deadline} 전날 제출 계획인가", "{type} 계약조건(기간·연장)을 읽었는가"],
]
FAQ_SETS = [
    [
        ("마감일({deadline})을 넘기면 지원할 수 있나요?",
         "없습니다. 공공 채용은 마감 시각 이후 접수를 받지 않습니다. 시스템 마감 1시간 전에는 대기열이 길어지니 {dlabel}을 보고 미리 제출하세요."),
        ("{region} 외 거주자도 지원 가능한가요?",
         "공고에 거주 제한이 별도로 없으면 전국 지원이 가능합니다. 다만 일부 지자체·교육청 공고는 거주·이전 조건이 붙으니 원문 응시자격란을 확인하세요."),
        ("{type} 전형에서 가장 중요한 서류는 무엇인가요?",
         "직무 연관성을 보여주는 자기소개서와 증빙(자격증·경력증명서)입니다. {org} 심사는 정량(자격·경력)과 정성(지원동기·직무이해)을 함께 봅니다."),
    ],
    [
        ("다른 분야와 중복 지원이 가능한가요?",
         "공고문에 별도 금지 조항이 없으면 가능하지만, {org}처럼 분야별 중복지원을 막는 기관이 많습니다. 원문 '지원 시 유의사항'을 먼저 확인하고, 가능하다면 가장 합격 가능성이 높은 한 분야에 집중하세요."),
        ("우대사항에 해당되는지 어떻게 확인하나요?",
         "이번 공고의 핵심 우대 조건은 '{point}'와 '{tag}'입니다. 증빙(자격증·경력증명서·취업지원대상자 증명서) 발급에 시간이 걸리니 마감일({deadline}) 기준 최소 3일 전에는 서류를 손에 쥐고 있어야 합니다."),
        ("서류가 간소화되는 경우도 있나요?",
         "청년인턴·기간제 등 일부 전형은 서류심사를 생략하고 면접만 보기도 합니다. {org} 공고문의 전형절차 표를 확인하세요. 간소화 전형일수록 면접 준비에 시간을 몰아주는 게 유리합니다."),
    ],
    [
        ("경쟁률은 어느 정도로 예상되나요?",
         "인기 기관·{region} 근무 공고는 서류 경쟁률이 10대 1을 넘는 일이 흔합니다. 다만 '{tag}' 같은 조건부 전형은 실질 경쟁률이 낮아지는 경우가 많으니, 본인 조건에 맞는 공고를 고르는 것 자체가 전략입니다."),
        ("합격자 발표는 어디서 확인하나요?",
         "{org} 홈페이지 채용 게시판과 지원 시 등록한 문자·이메일로 안내됩니다. 발표일에는 접속이 폭주하니 접수번호를 미리 메모해 두세요. 예비합격자 운영 여부도 원문에서 함께 확인하는 것이 좋습니다."),
        ("불합격하면 다음 기회는 언제인가요?",
         "공공기관은 상·하반기 정기 채용과 수시·추가 모집이 반복됩니다. 이번 마감일({deadline})을 놓쳐도 같은 기관의 다음 회차가 열리니, 공취모아의 {category} 탭을 구독하듯 수시로 확인하세요."),
    ],
]

HTML_HEAD = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | 공취모아</title>
<meta name="google-site-verification" content="HRs_kROrHp_3v5dVrhW_uaaY28DIA6CQydl-PXb8nt4" />
<meta name="naver-site-verification" content="6f515ee1e418c0993c21b0d3c9c4abfdf9a24046" />
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title} | 공취모아">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{ogimg}">
<meta name="google-adsense-account" content="ca-pub-3484572882367046">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3484572882367046" crossorigin="anonymous"></script>
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:Pretendard,-apple-system,"Noto Sans KR",sans-serif;background:#f3f5fa;color:#101828;max-width:780px;margin:0 auto;padding:0 18px 90px}}article{{background:#fff;border:1px solid #e4e9f2;border-radius:20px;padding:30px 26px;margin-top:16px;box-shadow:0 6px 24px rgba(16,24,40,.07)}}h1{{font-size:1.42rem;line-height:1.5;letter-spacing:-.5px}}h2{{font-size:1.1rem;margin:30px 0 12px;padding-left:12px;border-left:5px solid #0b5fff;letter-spacing:-.3px}}p,li{{line-height:1.85;font-size:.97rem}}table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:.9rem;border-radius:12px;overflow:hidden}}th,td{{border:1px solid #e2e8f2;padding:10px 12px;text-align:left}}th{{background:#eef4ff;width:112px;color:#0a2472}}ul{{margin:8px 0}}li{{margin:0 0 6px 20px}}.lead{{background:linear-gradient(135deg,#eef4ff,#f7faff);border:1px solid #d7e5ff;border-radius:14px;padding:16px 18px;margin:18px 0}}.cta{{display:block;text-align:center;background:linear-gradient(135deg,#0a4fe0,#0b5fff);color:#fff;border-radius:14px;padding:16px;margin:24px 0;text-decoration:none;font-weight:800;box-shadow:0 8px 20px rgba(11,95,255,.3)}}.back{{display:inline-block;margin:20px 0 4px;color:#0b5fff;text-decoration:none;font-weight:700;font-size:.92rem}}.rel a{{display:block;padding:12px 14px;color:#0b5fff;text-decoration:none;border:1px solid #e4e9f2;border-radius:12px;margin-bottom:8px;font-size:.9rem;background:#fbfcff}}.quote{{background:#fbfcff;border-left:5px solid #0a2472;border-radius:0 12px 12px 0;padding:14px 16px;margin:12px 0;font-size:.9rem;color:#344054}}.muted{{color:#98a2b3;font-size:.83rem;margin-top:24px;line-height:1.7}}.hero{{width:100%;border-radius:14px;margin:16px 0 6px;display:block;border:1px solid #e4e9f2}}</style>
</head><body><a class="back" href="../">← 공취모아 홈</a><article>
"""

HTML_TAIL = """
<div class="rel"><h2>함께 보면 좋은 공고</h2>{rels}</div>
<p class="muted">출처: {source} 공개정보를 바탕으로 공취모아가 정리한 안내글입니다. 모집 조건·일정은 변경될 수 있으니 지원 전 반드시 원문 공고문을 확인하세요. 본 글은 정보 제공용이며 합격을 보장하지 않습니다.</p>
</article>
<footer style="text-align:center;color:#888;font-size:.82rem;margin:30px 0;line-height:2"><a style="color:#888" href="../about.html">소개</a>·<a style="color:#888" href="../privacy.html">개인정보</a>·<a style="color:#888" href="../terms.html">약관</a>·<a style="color:#888" href="../contact.html">문의</a></footer>
</body></html>"""

CAT_ANGLE = {
    "청년인턴": "이번 공고는 스펙보다 지원 타이밍이 당락을 가릅니다. 체험형 인턴은 서류 간소화 전형이 많아 준비 기간이 짧아도 도전할 만합니다.",
    "교육청": "교육청·학교 채용은 거주지·자격증 요건을 먼저 확인하는 게 시간을 아끼는 지름길입니다. 공고문 1쪽의 응시자격 표를 끝까지 읽어보세요.",
    "공무직": "공무직·기간제 채용은 실무 가능 여부와 근무 조건(교대·주말)이 핵심입니다. 급여·근로시간 표를 원문에서 꼭 대조하세요.",
    "공기업": "공기업 정규직은 필기·서류 배수가 높아 early 지원이 유리합니다. 우대사항(인턴 수료·자격증) 해당 여부를 먼저 체크하세요.",
    "공공기관": "공공기관 채용은 직무기술서를 먼저 보는 게 합격 지름길입니다. 공고문보다 직무기술서에 평가 기준이 숨어 있습니다.",
    "지자체": "지자체 채용은 거주 요건·임용 지역을 먼저 확인하세요. 지역인재 가점이 붙는 경우가 많습니다.",
    "국가기관": "국가기관 채용은 결격사유·병역·정년 조항이 탈락 사유 1순위입니다. 지원 전 체크리스트로 한 번 걸러내세요.",
}

def angle(job):
    for k, v in CAT_ANGLE.items():
        if k in job.get("category", "") or k in job.get("title", ""):
            return v
    return CAT_ANGLE["공공기관"]

def dday(deadline):
    try:
        t = datetime.datetime.strptime(deadline, "%Y-%m-%d").date()
        return (t - datetime.date.today()).days
    except Exception:
        return 999

def build(job, all_jobs):
    d = dday(job["deadline"])
    dlabel = "마감" if d < 0 else ("D-DAY" if d == 0 else f"D-{d}")
    guide = DUTY_GUIDE.get(job.get("category", ""), DEFAULT_GUIDE)
    left = "이미 마감된 공고입니다. 다음 회차를 노리세요." if d < 0 else (
        "오늘이 마감일입니다. 접수 시스템이 혼잡하니 오전 중에 제출하세요." if d == 0 else
        f"남은 기간은 약 {d}일입니다. 서류 준비에 {max(d - 1, 1)}일을 쓰고 마지막 하루는 접수·확인용으로 남겨두세요.")
    vproc = _v(job, "proc")
    vessay = _v(job, "essay")
    viv = _v(job, "iv")
    vfaq = _v(job, "faq")
    vchk = _v(job, "chk")
    vpoint = _v(job, "point")
    proc = PROCESS_TEXTS[vproc].format(deadline=job["deadline"])
    essay = ESSAY_TEXTS[vessay].format(category=job["category"], org=job["org"],
                                       type=job["type"], deadline=job["deadline"])
    iv = INTERVIEW_TEXTS[viv].format(org=job["org"], category=job["category"],
                                     region=job["region"], type=job["type"])
    tag0 = (job.get("tags") or [""])[0]
    sum0 = (job.get("summary") or ["지원자격"])[0]
    point = POINT_TEXTS[vpoint].format(tag=tag0, point=sum0, org=job["org"], dlabel=dlabel)
    sched = SCHED_TEXTS[_v(job, "sched", 2)].format(posted=job["posted"], deadline=job["deadline"],
                                                    left=left, org=job["org"])
    pay = PAY_TEXTS[_v(job, "pay", 2)].format(type=job["type"], region=job["region"], org=job["org"])
    checklist = "".join(
        f"<li>{c.format(deadline=job['deadline'], dlabel=dlabel, region=job['region'], type=job['type'], org=job['org'])}</li>"
        for c in CHECKLISTS[vchk]
    )
    if job.get("excerpt"):
        excerpt_block = (
            "<h2>원문에서 확인한 전형 방식</h2>"
            f"<p class=\"quote\">{job['excerpt']}</p>"
            f"<p>위 내용은 {job['org']} 원문 공고의 전형 항목을 그대로 옮긴 것입니다. "
            "단계별 배수와 평가 요소가 적혀 있으니 본인 강점과 맞는 단계에 맞춰 준비 순서를 정하세요. "
            "전형별 합격자 발표일도 원문에서 함께 확인하는 것이 좋습니다.</p>"
        )
    else:
        excerpt_block = ""
    faq = "".join(
        f"<li><b>{q.format(deadline=job['deadline'], dlabel=dlabel, region=job['region'], type=job['type'], org=job['org'], point=sum0, tag=tag0, category=job['category'])}</b><br>"
        f"{a.format(deadline=job['deadline'], dlabel=dlabel, region=job['region'], type=job['type'], org=job['org'], point=sum0, tag=tag0, category=job['category'])}</li>"
        for q, a in FAQ_SETS[vfaq]
    )
    desc = f"{job['org']} {job['title']} 정리. 마감 {job['deadline']}({dlabel}), {job['region']}·{job['type']}. 지원자격·전형·추천대상 해설과 원문 링크."
    # 관련 공고 3개: 같은 카테고리 우선, 모자라면 마감 임박순
    cands = [j for j in all_jobs if j["id"] != job["id"]]
    same = [j for j in cands if j["category"] == job["category"]]
    rest = sorted([j for j in cands if j["category"] != job["category"]], key=lambda x: x["deadline"])
    rels = (same + rest)[:3]
    rel_html = "".join(f"<a href=\"{r['id']}.html\">[{r['category']}] {r['title']} — 마감 {r['deadline']}</a>" for r in rels)
    summ = "".join(f"<li>{s}</li>" for s in job["summary"])
    body = f"""
<h1>[{job['category']}] {job['title']}</h1>
<p style="color:#666;font-size:.9rem;margin-top:8px">{job['org']} · {job['region']} · 마감 {job['deadline']} <b>({dlabel})</b> · 출처 {job['source']}</p>
<img class="hero" src="../thumbnails/{job['id']}.png" alt="{job['title']} 썸네일" loading="lazy">
<div class="lead">핵심만 먼저: <b>{job['org']}</b>에서 <b>{job['type']}</b>을 뽑습니다. 마감이 <b>{job['deadline']}({dlabel})</b>이라 서두르는 게 좋습니다. {angle(job)}</div>
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
<p>공고문의 응시자격은 짧게 쓰여 있지만 실제로는 세 가지를 봅니다. 첫째 결격사유 해당 여부, 둘째 자격·경력의 직무 연관성, 셋째 근무 시작 가능일입니다. 셋 중 하나라도 애매하면 원문 공고문의 세부 조항을 먼저 확인하고 지원서를 쓰세요. 특히 {job['org']} 공고는 {job['type']} 전형이라 서류에서 직무 연관 키워드({job['category']})를 명시하는 게 유리합니다.</p>
<h2>이 공고의 포인트</h2>
<p>{point}</p>
<h2>전형은 어떻게 진행되나</h2>
<p>{proc}</p>
{excerpt_block}
<h2>이런 분께 추천해요</h2>
<ul>
<li>{job['region']} 근무가 가능한 분 — 통근·거주 조건이 맞는지가 1순위입니다</li>
<li>{job['type']} 전형을 찾는 분 — {job['category']} 분야 관심자라면 우선 검토 대상입니다</li>
<li>마감({job['deadline']}) 안에 서류를 낼 수 있는 분 — {dlabel}이니 오늘 지원서 초안부터 잡으세요</li>
</ul>
<h2>지원 전 체크리스트</h2>
<ul>
{checklist}
</ul>
<h2>모집 일정과 제출 타이밍</h2>
<p>{sched}</p>
<h2>직무 이해하기: {job['category']}</h2>
<p>{guide} {job['org']}의 이번 채용({job['type']})도 같은 잣대로 보면 됩니다. 공고 제목에 적힌 분야명과 직무기술서의 필요역량을 나란히 놓고, 본인 경험에서 겹치는 키워드를 세 개 이상 뽑아보세요. 그 세 개가 자기소개서와 면접 답변의 뼈대가 됩니다.</p>
<h2>자기소개서 작성 팁</h2>
<p>{essay}</p>
<h2>면접 준비 포인트</h2>
<p>{iv}</p>
<h2>급여·근무조건 읽는 법</h2>
<p>{pay}</p>
<h2>자주 묻는 질문</h2>
<ul>
{faq}
</ul>
<a class="cta" href="{job['url']}" target="_blank" rel="noopener">원문 공고문 확인하고 지원하기 ↗</a>
"""
    html = HTML_HEAD.format(title=f"[{job['category']}] {job['title']}", desc=desc,
                            canon=f"{SITE_URL}articles/{job['id']}.html",
                            ogimg=f"{SITE_URL}thumbnails/{job['id']}.png")
    html += body + HTML_TAIL.format(rels=rel_html, source=job["source"])
    return html

def main():
    import sys
    sys.path.insert(0, BASE)
    import quota
    max_run = int(os.environ.get("MAX_NEW_PER_RUN", "15"))
    per_day = int(os.environ.get("ARTICLES_PER_DAY", "5"))
    allow = min(quota.remaining("articles", per_day), max_run)
    jobs = json.load(open(JOBS_JSON, encoding="utf-8"))
    os.makedirs(ART_DIR, exist_ok=True)
    if os.environ.get("RETHUMB", "") == "1":
        n = 0
        for j in jobs:
            make_thumb(j)
            n += 1
        print(f"썸네일 재생성 {n}건")
        return
    # 하루 발행량: 날짜 기준 5건. 초과분은 다음날로 자동 이월. 마감분은 신규 기사화 안 함(기존 유지).
    # 단 ALLOW_EXPIRED_ARTICLES=1이면 복구 등 일회성으로 마감분도 생성.
    today = datetime.date.today().isoformat()
    allow_exp = os.environ.get("ALLOW_EXPIRED_ARTICLES", "") == "1"
    missing = sorted(
        [j for j in jobs
         if not os.path.exists(os.path.join(ART_DIR, j["id"] + ".html"))
         and (allow_exp or (j.get("deadline") or "") >= today)],
        key=lambda x: x["deadline"],
    )
    targets, deferred = missing[:allow], missing[allow:]
    for j in targets:
        make_thumb(j)
        p = os.path.join(ART_DIR, j["id"] + ".html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(build(j, jobs))
    quota.consume("articles", len(targets))
    # sitemap 갱신
    today = datetime.date.today().isoformat()
    urls = [f"  <url><loc>{SITE_URL}</loc><lastmod>{today}</lastmod><changefreq>hourly</changefreq><priority>1.0</priority></url>"]
    for j in jobs:
        urls.append(f"  <url><loc>{SITE_URL}articles/{j['id']}.html</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>")
    with open(os.path.join(BASE, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>")
    print(f"신규 기사 {len(targets)}건 + 썸네일 {len(targets)}건 + sitemap 갱신 완료." + (f" (이월 {len(deferred)}건)" if deferred else ""))

if __name__ == "__main__":
    main()
