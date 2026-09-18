import sys, re
sys.stdout.reconfigure(encoding="utf-8")
from fetch_gojobs_html import get

# 첨부 다운로드 링크 구조 파악 (3건)
for seq in ("303918", "303914", "303895"):
    html = get(f"https://www.gojobs.go.kr/apmView.do?empmnsn={seq}&menuNo=401&selMenuNo=400", timeout=15)
    print("=====", seq, "=====")
    for m in re.finditer(r"(fn_[a-zA-Z_0-9]*file[a-zA-Z_0-9]*|fileDown[a-zA-Z_0-9]*|fn_down[a-zA-Z_0-9]*)[^;]{0,120}", html, re.I):
        print("  FN:", m.group(0)[:110])
    for m in re.finditer(r"href=\"([^\"]*(?:down|file|attach)[^\"]*)\"", html, re.I):
        print("  HREF:", m.group(1)[:130])
    for m in re.finditer(r"([\w가-힣]+\.(?:hwp|hwpx|pdf|doc))", html):
        print("  FILE:", m.group(1)[:80])
    print()