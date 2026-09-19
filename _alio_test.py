import sys
sys.stdout.reconfigure(encoding="utf-8")
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KEY = "MTBiMDYwZjNhOGQ1ZTM3MDMyNGM0YzI3ZGI3ZDAzODNkYjk4MTVhNjJmZWJjNjdmYjU3NGViYWNlMTIxYmY0Mg=="
url = "https://apis.data.go.kr/1051000/recruitment/list?" + urlencode({
    "serviceKey": KEY,
    "numOfRows": 5,
    "pageNo": 1,
    "resultType": "json",
})
try:
    with urlopen(Request(url), timeout=30) as r:
        body = r.read().decode("utf-8", errors="replace")
    print("HTTP OK, bytes:", len(body))
    print(body[:2000])
except Exception as e:
    print("FAIL:", e)
    try:
        print(e.read().decode("utf-8", errors="replace")[:800])
    except Exception:
        pass