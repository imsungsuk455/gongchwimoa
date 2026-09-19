import json, sys, datetime, re
sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter

d = json.load(open("jobs.json", encoding="utf-8"))
today = datetime.date.today()

# ---- 스킬 2-1 선별 규칙 적용 ----
# 1) 일용직 분류: 단기노무원/한시인력/일용/계절 (스킬 규칙 - "정규직" 오표기 금지)
DAILY_RE = re.compile(r"단기노무원|한시인력|일용직|계절|임시직원|기간제근로자")

def classify(job):
    t = job.get("title", "") + " " + job.get("org", "")
    if DAILY_RE.search(t):
        return "일용직"
    return job.get("type", "정규직")

# 2) 후보: 마감 지나지 않은 것
cand = [j for j in d if (j.get("deadline") or "9999") >= today.isoformat()]
print(f"유효 후보: {len(cand)}건 (전체 {len(d)}건)")

for j in cand:
    j["_type2"] = classify(j)
    try:
        j["_days"] = (datetime.date.fromisoformat(j["deadline"]) - today).days
    except Exception:
        j["_days"] = 999

# 3) 같은 기관 하루 1건: 기관명으로 그룹 → 대표 1건
seen_org = {}
for j in cand:
    org = j.get("org", "").strip()
    if org not in seen_org or j["_days"] < seen_org[org]["_days"]:
        seen_org[org] = j
uniq = list(seen_org.values())
print(f"기관 중복 제거 후: {len(uniq)}건")

# 4) 우선순위: 급여 → 정규직 → 수도권 → 마감임박 → 마감일
CAP = {"서울", "경기", "인천"}
def rank(j):
    pay = 0 if j.get("pay") else 1
    reg = 0 if j["_type2"] == "정규직" else 1
    cap = 0 if j.get("region") in CAP else 1
    urgent = 0 if 0 <= j["_days"] <= 3 else 1
    return (pay, reg, cap, urgent, j["_days"])

picks = sorted(uniq, key=rank)[:10]
print(f"최종 선별: {len(picks)}건\n")

# ---- 스킬 2-2 발행 포맷 적용 ----
def hook(j):
    if j["_type2"] == "정규직":
        return "정규직"
    if j.get("pay"):
        return j["pay"]
    if j.get("region") in CAP:
        return j["region"] + " 근무"
    if j["_days"] <= 0:
        return "오늘 마감"
    if j["_days"] == 1:
        return "내일 마감"
    if j["_days"] <= 3:
        return f"마감 D-{j['_days']}"
    return None

def short_title(t, limit=44):
    t = re.sub(r"\([^)]*(모집분야|모집인원|분야\s*:|직급|직위)[^)]*\)", "", t)
    t = re.sub(r"\((나급|다급|라급|마급|가급)\)", "", t)
    t = t.replace("경력경쟁채용시험 공고", "채용 공고").replace("경력경쟁채용시험", "채용")
    t = t.replace("경력경쟁임용시험", "임용시험").replace("공개모집 공고", "공개모집")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        cut = t[:limit]
        sp = cut.rfind(" ")
        t = (cut[:sp] if sp > 20 else cut).rstrip() + "…"
    return t

for i, j in enumerate(picks, 1):
    h = hook(j)
    days = j["_days"]
    urgent = "오늘 마감" if days <= 0 else ("내일 마감" if days == 1 else (f"마감 D-{days}" if days <= 3 else None))
    ending = "모집중" if (h == urgent and urgent) else (urgent or "모집중")
    title = short_title(j["title"])
    body = f"{title} {ending}"
    text = f"\"{h}\"\n\n{body}" if h else body
    print(f"───── {i}. [{j['id']}] {j.get('org','')} | 분류: {j['_type2']} | 마감 D-{days} ─────")
    print(text)
    print(f"댓글: 자세한 사항 확인하러 가기 ▽")
    print(f"     https://gongchwimoa.org/articles/{j['id']}.html")
    print()