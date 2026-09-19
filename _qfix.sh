#!/bin/bash
cd /root/public-jobs
python3 -c "
import json,sys
sys.stdout.reconfigure(encoding='utf-8')
q=json.load(open('threads_queue.json',encoding='utf-8'))
n=0
for s in q['slots']:
    if s.get('status')=='claiming':
        s['status']='pending'; n+=1
json.dump(q,open('threads_queue.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('claiming->pending 복구:',n,'건')
"
git add threads_queue.json
git commit -m "revert claiming to pending" 2>&1 | tail -1
timeout 30 git push origin main 2>&1 | tail -1