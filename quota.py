#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""하루 발행량 쿼터 (날짜 기준, KST). 사이트 기사·스레드가 같은 파일을 공유."""
import json, os, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, "publish_state.json")
KST = datetime.timezone(datetime.timedelta(hours=9))

def _today():
    return datetime.datetime.now(KST).date().isoformat()

def _load():
    try:
        s = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        s = {}
    if s.get("date") != _today():
        s = {"date": _today(), "articles": 0, "threads": 0}
    return s

def remaining(kind, cap):
    s = _load()
    return max(cap - int(s.get(kind, 0)), 0)

def consume(kind, n):
    if n <= 0:
        return
    s = _load()
    s[kind] = int(s.get(kind, 0)) + n
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def next_round_robin(key, size):
    """에디토리얼 순환 인덱스. 0..size-1 순환."""
    s = _load()
    i = int(s.get(key, 0)) % max(size, 1)
    s[key] = i + 1
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    return i
