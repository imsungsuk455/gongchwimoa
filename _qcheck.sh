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