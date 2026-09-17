# 공취모아 (프로토타입)

공공기관 전체 유지 방향으로 만든 자동화 프로토타입입니다.
전체 목록이 기본이되, 내부에 특화 탭(청년인턴 / 교육청·교사 / 공무직·기간제 / 마감임박 3일)을 넣어 정면승부 + 틈새를 동시에 노립니다.

## 구조
- `index.html` — 목록 + 필터탭 + 검색 + D-day (제목 클릭 → 해설 기사)
- `articles/{id}.html` — 공고별 해설 기사 (한글 1000자+, `gen_articles.py`가 자동생성)
- `jobs.json` — 공고 DB (cron이 갱신, 현재 목업 12건)
- `fetch_jobs.py` — 나라일터 API 연동 스켈레톤
- `gen_articles.py` — jobs.json → 기사 1건씩(한글 2000자+) + 썸네일 + sitemap 갱신
- `thumbnails/{id}.png` — 썸네일 기본옵션: PIL 로컬렌더 1200x630 (카테고리 색상 + 공고제목 텍스트).
  외부 AI 없이 cron 즉시 생성·비용 0원. 목록 카드 + 기사 og:image에 자동 연결.
- `threads_queue.json` — 스레드 자동발행 큐 (신규 발생 시 생성)
- `about/privacy/terms/contact.html`, `robots.txt`, `sitemap.xml`, `ads.txt` — 애드센스 승인 필수 세트

## 1) API 키 발급 (5분, 무료)
1. data.go.kr 접속 → `인사혁신처_공공취업정보 조회 서비스` 검색
2. 활용신청 (개발/운영 모두 자동승인) → 참고문서에서 엔드포인트·파라미터 확인
3. `fetch_jobs.py`의 `API_ENDPOINT` 또는 환경변수 `GOJOBS_API_ENDPOINT`에 입력
4. 환경변수 `DATA_GO_KR_KEY`에 키 설정 후 실행

## 2) 로컬 검증
```powershell
python .\fetch_jobs.py --mock   # 큐 생성 검증
python -c "import json;print(len(json.load(open('jobs.json',encoding='utf-8'))))"
```

## 3) 자동화 (GitHub Actions 예시)
수집과 발송은 분리되어 있습니다. 콘텐츠가 언제 들어와도 정해진 5개 슬롯에 맞춰 나갑니다.

```
나라일터 API (수시 갱신)
  → fetch_jobs.py (2시간 간격): 신규 수집 → jobs.json + 발송 버퍼(threads_queue.json 빈 슬롯에 배정)
  → gen_articles.py (이어서): 하루 5건 기사+썸네일 생성 → push → 자동배포
  → send_queue.py (08/11/14/17/20시 KST): 해당 슬롯 pending 1건 발송 + 댓글에 원문링크
```

- 버퍼가 비어있는 슬롯 시간에는 skip (억지 발송 없음)
- 오늘 5슬롯이 다 차면 내일 슬롯으로 자동 이월, 내일까지 차면 탈락 로그
- 발송 테스트: `python send_queue.py --slot 14:00` (dry-run). 실제 발송만 `--live`

## 4) 수익 자리
- 애드센스: head 자동광고만 유지 (수동 ins 금지 — 승인 전 정책위반 방지)
- 제휴(쿠팡파트너스 등): 애드센스 승인 후 추가 예정. 승인 전에는 링크 없음 (심사 방해 요소 제거)
- 타불라: 월 50만 PV 이후에 추가 검토

## 5) 전체 유지 시 운영 규칙 (정면승부용)
- 하루 수백건이 쌓이면 스레드 도배가 되므로, 스레드는 **마감임박 + 청년인턴 상위 5건만** 발송
- 사이트 내부는 전체 유지 (SEO 볼륨용) + 탭으로 큐레이션 (체류시간용)
- 마감 공고는 삭제 금지, `마감` 뱃지로 전환 (SEO·신뢰용)

## 6) 하루 발행량 조절 (기본값: 5건)
| 채널 | 캡 | 우선순위 | 변경법 |
|---|---|---|---|
| 사이트 기사 | 하루 **5건** | 마감일순 | `ARTICLES_PER_DAY` 환경변수 |
| 스레드 | 하루 **5건** | 마감임박 ≤3일 > 청년인턴 > 마감일순 | `MAX_THREADS_PER_DAY` 환경변수 |
- 날짜 기준(KST)으로 집계하며 `publish_state.json`에 기록. 초과분은 다음날로 자동 이월 (누락 없음)
- cron이 하루 12번 돌아도 일 5건을 넘지 않음. 검증됨: 7건 대기 시 5건 생성+2건 이월 → 당일 재실행 0건 → 다음날 2건 처리
