# work24-scraper

고용24(www.work24.go.kr) 채용공고 스크래이퍼.

관공서 일자리 채용 웹사이트(고용24)의 채용공고를 수집하고 관리하는 CLI 도구입니다.

## 기능

| 명령 | 설명 |
|------|------|
| `init_scrap` | 전체 채용공고 수집 + storage 초기화 |
| `resume_scrap` | 중단된 수집 재개 (기존 데이터 보존, 빠진 공고만 수집) |
| `sync_scrap` | 신규 공고 추가 (최신 페이지 위주 조기 종료) |
| `validate_job` | 마감 공고 검증 및 제거 |

## 설치

```bash
pip install -e .
```

## 사용법

```bash
# 전체 초기 수집
python init_scrap.py

# 중단된 수집 재개
python resume_scrap.py

# 신규 공고 동기화
python sync_scrap.py

# 마감 공고 제거
python validate_job.py

# 테스트 모드 (--dry): 소량만 수집
python init_scrap.py --dry    # 10페이지만 수집
python resume_scrap.py --dry  # 이전 수집 이후 5페이지만 수집
```

## 기술 스택

- Python 3.12+
- requests — HTTP 클라이언트
- beautifulsoup4 + lxml — HTML 파싱
- JSON 파일 기반 스토리지 (POC)

## 아키텍처

```
CLI 스크립트 → usecases(순수 로직) → adapters(외부 의존)
```

단방향 의존 구조. 상세 설계는 [`docs/design-spec.md`](docs/design-spec.md) 참고.

### 스크립트별 동작 흐름

**init / resume — 공유 엔진 (`_collect_missing`)**

```
init:   store.clear() → _collect_missing(existing_ids=빈 set)   # 전체 수집
resume:              → _collect_missing(existing_ids=기존 ID set) # 빠진 것만 수집
```

- 전체 페이지(1 ~ total_pages) 순회, `existing_ids`에 없는 공고만 상세 조회
- `existing_ids`를 in-place 갱신하여 같은 실행 내 중복 방지

**sync — 조기 종료 방식**

```
페이지 1(최신)부터 순회 → 신규 발견 시 수집 → 연속 3페이지 신규 0이면 중단
```

- 초기 수집 완료 후 일상적으로 사용, 최신 페이지만 빠르게 훑음

**validate — 만료 공고 제거**

```
DB 내 모든 공고 순회 → 상세 페이지 접근 → 만료 시 제거
```

- 만료 판별: 응답에 `alert("구인정보를 확인할 수 없습니다")` 포함 여부

### 봇 탐지 우회

`Work24Scraper`에 예방적 방어가 적용되어 있습니다:

- **요청 자연화**: UA 로테이션 (6개 풀), 리얼리스틱 브라우저 헤더, Referer 자동 설정
- **랜덤 딜레이**: 1.0~3.0초 균등 분포 (`random.uniform`)
- **세션 로테이션**: 200건마다 새 세션 생성 (UA 재선택)
- **지수 백오프**: 429/5xx 응답 시 2s→4s→8s 재시도 (최대 3회)
- **차단 감지**: CAPTCHA/보안문자 등 감지 시 60초 대기 후 재시도 (최대 2회)

## 프로젝트 구조

```
work24-scraper/
├── init_scrap.py              # CLI: 전체 초기 수집 + DB 초기화
├── resume_scrap.py            # CLI: 중단된 수집 재개
├── sync_scrap.py              # CLI: 신규 공고 추가 (조기 종료)
├── validate_job.py            # CLI: 마감 공고 검증 및 제거
├── domain/
│   ├── __init__.py
│   └── models.py              # 데이터 모델 (dataclass)
├── adapters/
│   ├── scraper.py             # HTTP 요청 + HTML 파싱
│   └── store.py               # JSON 파일 CRUD
├── usecases/
│   ├── collect.py             # 전체 수집 + 재개 로직
│   ├── sync.py                # 동기화 로직
│   └── validate.py            # 유효성 검증 로직
├── data/
│   └── jobs.json              # JSON DB
├── tests/
└── docs/
```

## 개발

```bash
pip install -e ".[dev]"
pytest
```

## 라이선스

MIT
