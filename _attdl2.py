import sys, re
sys.stdout.reconfigure(encoding="utf-8")
from fetch_gojobs_html import get

html = get("https://www.gojobs.go.kr/apmView.do?empmnsn=303918&menuNo=401&selMenuNo=400", timeout=15)
i = html.find("function gfn_fileDown")
print(html[i:i+900] if i >= 0 else "gfn_fileDown 정의 없음")
print("=====")
i2 = html.find("function fn_fileDown")
print(html[i2:i2+900] if i2 >= 0 else "fn_fileDown 정의 없음")