import json, sys, datetime, re
sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter
from fetch_jobs import priority_key, thread_text, short_title, has_salary

d = json.load(open("jobs.json", encoding="utf-8"))
today = datetime.date.today()

cand = [j for j in d if (j.get("deadline") or "9999") >= today.isoformat()]
for j in cand:
    try:
        j["_days"] = (datetime.date.fromisoformat(j["deadline"]) - today).days
    except Exception:
        j["_days"] = 999

# 같은 기관 하루 1건 (대표 1건)
seen = {}
for j in cand:
    org = j.get("org", "").strip()
    if org not in seen or j["_days"] < seen[org]["_days"]:
        seen[org] = j
uniq = list(seen.values())

# 우선순위 정렬 → 상위 10
picks = sorted(uniq, key=priority_key)[:10]

print(f"선별 10건 (기관 중복 제거 {len(cand)}→{len(uniq)}):\n")
for i, j in enumerate(picks, 1):
    print(f"  {i}. [{j['type']}] {j.get('org','')[:22]:22s} | {short_title(j['title'],40)[:42]:42s} | D-{j['_days']}")

# ---- 슬롯 분산 배정 (THREAD_SLOTS) ----
SLOTS = ["07:00", "08:30", "10:00", "11:30", "13:00", "14:30", "16:00", "17:30", "19:00", "20:30"]
print(f"\n=== 예약 발행 분산 (오늘 빈 슬롯 {len(SLOTS)}개) ===")
used_org = set()
for i, j in enumerate(picks):
    slot = SLOTS[i]
    org = j.get("org", "").strip()
    text = thread_text(j)
    print(f"\n[{slot}] {j['id']}")
    print(text)
    print(f"   댓글: 자세한 사항 확인하러 가기 ▽")
    print(f"         https://gongchwimoa.org/articles/{j['id']}.html")