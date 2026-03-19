# work24-scraper

고용24(www.work24.go.kr) 채용공고 스크래이퍼. POC 단계.

## 프로젝트 개요

관공서 일자리 채용 웹사이트(고용24)의 채용공고를 수집/관리하는 CLI 기반 스크래이퍼.

## CLI 스크립트

| 명령 | 설명 |
|------|------|
| `init_scrap` | 고용24 전체 채용공고 수집 + storage 초기화 |
| `resume_scrap` | 중단된 수집 재개 (기존 데이터 보존, 빠진 공고만 수집) |
| `sync_scrap` | 신규 공고 추가 (최신 페이지 위주 조기 종료) |
| `validate_job` | 수집된 공고의 유효성 검증, 마감 공고 제거 |

## 기술 스택

- **언어**: Python
- **HTTP**: requests
- **HTML 파싱**: beautifulsoup4 + lxml
- **Storage**: JSON 파일 기반 (POC)
- **실행 방식**: CLI

## 아키텍처

CLI 스크립트(root) → usecases(순수 로직) → adapters(외부 의존) 단방향 의존.
상세 설계: `docs/design-spec.md` 참고.

### 스크립트별 동작 흐름

- **init / resume**: 공유 엔진 `_collect_missing(scraper, store, existing_ids)` 사용. init은 `store.clear()` 후 빈 set 전달, resume은 기존 ID set 전달. 전체 페이지 순회.
- **sync**: 페이지 1(최신)부터 순회, 연속 3페이지 신규 없으면 조기 종료. 별도 로직 (`sync_jobs`).
- **validate**: DB 내 모든 공고의 상세 페이지 접근, 만료(`alert` 패턴) 시 제거. 별도 로직 (`validate_all_jobs`).

### 봇 탐지 우회

`Work24Scraper`에 적용된 예방적 방어 (상세: `docs/superpowers/specs/2026-03-19-anti-bot-design.md`):
- UA 로테이션 (6개 풀), 리얼리스틱 브라우저 헤더, Referer 자동 설정
- 랜덤 딜레이 (0.3~1.5s), 세션 로테이션 (200건마다)
- 지수 백오프 재시도 (429/5xx), 차단 신호 감지 + 60s 대기 재시도

## 사용법

```bash
pip install -e ".[dev]"
python init_scrap.py      # 전체 초기 수집
python resume_scrap.py    # 중단된 수집 재개
python sync_scrap.py      # 신규 공고 동기화
python validate_job.py    # 마감 공고 제거

# 테스트 모드 (--dry)
python init_scrap.py --dry    # 10페이지만 수집
python resume_scrap.py --dry  # 이전 수집 이후 5페이지만 수집
```

## 참고 문서

- `docs/research-site-analysis.md` — 고용24 사이트 구조 분석
- `docs/design-spec.md` — 설계 문서
- `docs/implementation-plan.md` — 구현 계획

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
│   ├── __init__.py
│   ├── scraper.py             # HTTP 요청 + HTML 파싱
│   └── store.py               # JSON 파일 CRUD
├── usecases/
│   ├── __init__.py
│   ├── collect.py             # 전체 수집 + 재개 로직
│   ├── sync.py                # 동기화 로직
│   └── validate.py            # 유효성 검증 로직
├── data/
│   └── jobs.json              # JSON DB
├── docs/
├── tests/
├── pyproject.toml
└── CLAUDE.md
```

## 컨벤션

- Python 3.12+
- snake_case 네이밍
- from, import 구문은 파일 최상단 배치
- 타입 힌트 사용
