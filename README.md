# HiMart Price Intelligence Dashboard

롯데하이마트 온라인몰 가격을 수집해서 카테고리별 추천 상품을 보여주고, 매장용 POP 출력까지 지원하는 Flask 기반 대시보드입니다.

---

## 설치

```bash
pip install -r requirements.txt
```

환경 변수는 `.env.example`을 참고해서 `.env`로 복사한 뒤 필요하면 `STORE_NAME` 등을 수정하면 됩니다.

---

## 로컬 실행

```bash
python app.py
```

브라우저에서 `http://localhost:5000`으로 접속합니다.

---

## 수동 크롤링

전체 크롤링:

```bash
python crawler.py
```

특정 카테고리만 크롤링:

```bash
python crawler.py tv refrigerator
```

지원 카테고리:
`tv`, `refrigerator`, `washer`, `dryer`, `kimchi`, `aircon`, `airpurifier`, `vacuum`, `dishwasher`, `range`, `laptop`, `tablet`

---

## 프로젝트 구조

```text
onlineshop/
├─ app.py                       # Flask 앱 진입점
├─ crawler.py                   # 하이마트 상품/구독상품 크롤러
├─ ranker.py                    # 추천 점수 계산
├─ scheduler.py                 # 로컬 상주 환경용 APScheduler
├─ database.py                  # SQLite CRUD
├─ config.py                    # 환경설정, 카테고리, 필터 정의
├─ badge_calculator.py          # 뱃지 계산
├─ spec_extractor.py            # 상품명/모델명 기반 스펙 추출
├─ templates/
│  ├─ intro.html                # 인트로 화면
│  └─ index.html                # 메인 대시보드
├─ data/
│  └─ himart.db                 # 서비스에 사용되는 SQLite DB
├─ logs/
│  └─ crawler.log               # 크롤링 로그
├─ scripts/
│  └─ run_daily_crawl.py        # GitHub Actions용 일일 크롤링 실행 스크립트
└─ .github/workflows/
   └─ daily-crawl.yml           # GitHub Actions 자동 크롤링 워크플로
```

---

## 주요 API

| Method | URL | 설명 |
|---|---|---|
| GET | `/` | 인트로 화면 |
| GET | `/main` | 메인 대시보드 |
| GET | `/api/recommendations` | 전체 추천 조회 |
| GET | `/api/recommendations?category=tv` | 특정 카테고리 추천 조회 |
| GET | `/api/filters` | 카테고리별 필터 정의 |
| GET | `/api/status` | 마지막 크롤링 시각, 상품 수 |
| POST | `/api/crawl` | 수동 일반 크롤링 시작 |
| GET | `/api/subscription/recommended` | 구독상품 추천 조회 |
| POST | `/api/subscription/crawl` | 수동 구독상품 크롤링 시작 |
| GET | `/api/history/<model_no>` | 가격 히스토리 조회 |
| GET | `/proxy/image` | 외부 이미지 프록시 |

---

## 운영 방식

현재 권장 운영 기준은 아래와 같습니다.

- `Vercel`: 화면과 Flask API 서빙
- `GitHub Actions`: 매일 크롤링 실행 후 `data/himart.db` 갱신

이 프로젝트는 서버리스 환경에서는 백그라운드 스케줄러와 스레드 기반 장시간 작업이 안정적으로 유지되지 않을 수 있으므로, 운영 크롤링은 GitHub Actions 기준으로 돌리는 것을 권장합니다.

---

## GitHub Actions 자동 크롤링

- 워크플로 파일: `.github/workflows/daily-crawl.yml`
- 실행 스크립트: `scripts/run_daily_crawl.py`
- 스케줄 기준: 매일 오전 8시 `Asia/Seoul`
- 수동 실행: GitHub 저장소 `Actions` 탭 -> `Daily Crawl` -> `Run workflow`

동작 순서:

1. GitHub Actions가 일반 상품 크롤링과 구독상품 크롤링을 실행합니다.
2. 결과가 `data/himart.db`에 반영됩니다.
3. DB 변경이 있으면 Actions가 자동으로 커밋하고 `main`에 push 합니다.
4. Vercel은 최신 저장소 상태를 기준으로 다시 배포됩니다.

필수 확인 사항:

1. 저장소 `Actions permissions`에서 워크플로의 쓰기 권한이 허용되어 있어야 합니다.
2. `data/himart.db`가 저장소에 포함되어 있어야 합니다.
3. 첫 실행은 `Run workflow`로 수동 실행해서 로그를 확인하는 것을 권장합니다.

---

## 첫 실행 체크리스트

1. GitHub `Actions` 탭에서 `Daily Crawl`을 수동 실행합니다.
2. `Run product and subscription crawlers` 단계가 성공하는지 확인합니다.
3. `Commit updated database` 단계가 성공하는지 확인합니다.
4. 새 커밋이 생성되면 Vercel 배포 후 사이트에서 최신 수집 시각이 갱신됐는지 확인합니다.

---

## 참고

- 로컬에서 `scheduler.py`는 상주 프로세스 환경에서는 사용할 수 있지만, Vercel 운영에서는 GitHub Actions 스케줄이 기준입니다.
- 페이지 진입 시마다 전체 크롤링을 실행하는 방식은 응답 지연이 크고 서버리스 환경과도 잘 맞지 않아 권장하지 않습니다.
