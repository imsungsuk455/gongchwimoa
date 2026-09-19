#!/bin/bash
echo "=== 텔레그램 봇 직접 발송 테스트 ==="
python3 -c "
import urllib.request, urllib.parse, json
TOKEN='8748993031:AAHLfc7--dUC4aKmeObFPlsg64G5urOcEpU'
CHAT='5032205044'
msg='공취모아 봇 연결 테스트: 이 메시지가 보이면 텔레그램 정상 동작입니다.'
data=urllib.parse.urlencode({'chat_id':CHAT,'text':msg}).encode()
req=urllib.request.Request(f'https://api.telegram.org/bot{TOKEN}/sendMessage',data=data)
try:
    r=urllib.request.urlopen(req,timeout=20)
    resp=json.loads(r.read().decode())
    print('성공:',resp.get('ok'))
    if not resp.get('ok'):
        print(resp)
except Exception as e:
    print('실패:',e)
    try: print(e.read().decode())
    except: pass
"