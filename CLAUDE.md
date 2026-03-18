# work24-scraper

고용24(www.work24.go.kr) 채용공고 스크래이퍼. POC 단계.

## 프로젝트 개요

관공서 일자리 채용 웹사이트(고용24)의 채용공고를 수집/관리하는 CLI 기반 스크래이퍼.

## CLI 스크립트

| 명령 | 설명 |
|------|------|
| `init_scrap` | 고용24 전체 채용공고 수집 + storage 초기화 |
| `sync_scrap` | 신규/변경 공고 추가 및 업데이트 (증분 동기화) |
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

## 사용법

```bash
pip install -e ".[dev]"
python init_scrap.py      # 전체 초기 수집
python sync_scrap.py      # 신규 공고 동기화
python validate_job.py    # 마감 공고 제거
```

## 참고 문서

- `docs/research-site-analysis.md` — 고용24 사이트 구조 분석
- `docs/design-spec.md` — 설계 문서
- `docs/implementation-plan.md` — 구현 계획

## 프로젝트 구조

```
work24-scraper/
├── init_scrap.py              # CLI: 전체 초기 수집 + DB 초기화
├── sync_scrap.py              # CLI: 증분 동기화 (신규 추가 + 갭 메우기)
├── validate_job.py            # CLI: 마감 공고 검증 및 제거
├── models.py                  # 데이터 모델 (dataclass)
├── adapters/
│   ├── __init__.py
│   ├── scraper.py             # HTTP 요청 + HTML 파싱
│   └── store.py               # JSON 파일 CRUD
├── usecases/
│   ├── __init__.py
│   ├── collect.py             # 전체 수집 로직
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
