#!/bin/bash
cd /root/public-jobs
python3 -c "
import json,sys
sys.stdout.reconfigure(encoding='utf-8')
q=json.load(open('threads_queue.json',encoding='utf-8'))
for s in q['slots']:
    if s.get('date')=='2026-09-19':
        print(s.get('slot'),s.get('status'),s.get('job_id'))
"
echo "=== claiming → pending 복구 ==="
python3 -c "
import json
q=json.load(open('threads_queue.json',encoding='utf-8'))
n=0
for s in q['slots']:
    if s.get('status')=='claiming':
        s['status']='pending'; n+=1
json.dump(q,open('threads_queue.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
print('복구:',n)
"
git add threads_queue.json
git commit -m "revert claiming pending (debug)" 2>&1 | tail -1
timeout 30 git push origin main 2>&1 | tail -1