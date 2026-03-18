# work24-scraper

고용24(www.work24.go.kr) 채용공고 스크래이퍼.

관공서 일자리 채용 웹사이트(고용24)의 채용공고를 수집하고 관리하는 CLI 도구입니다.

## 기능

| 명령 | 설명 |
|------|------|
| `init_scrap` | 전체 채용공고 수집 + storage 초기화 |
| `sync_scrap` | 신규/변경 공고 증분 동기화 |
| `validate_job` | 마감 공고 검증 및 제거 |

## 설치

```bash
pip install -e .
```

## 사용법

```bash
# 전체 초기 수집
python init_scrap.py

# 신규 공고 동기화
python sync_scrap.py

# 마감 공고 제거
python validate_job.py
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

## 프로젝트 구조

```
work24-scraper/
├── init_scrap.py              # CLI: 전체 초기 수집
├── sync_scrap.py              # CLI: 증분 동기화
├── validate_job.py            # CLI: 마감 공고 검증
├── models.py                  # 데이터 모델 (dataclass)
├── adapters/
│   ├── scraper.py             # HTTP 요청 + HTML 파싱
│   └── store.py               # JSON 파일 CRUD
├── usecases/
│   ├── collect.py             # 전체 수집 로직
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
