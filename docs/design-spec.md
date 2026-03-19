# work24-scraper 설계 문서

> 작성일: 2026-03-18
> 상태: 승인됨

## 1. 개요

고용24(www.work24.go.kr) 채용공고를 수집/관리하는 CLI 기반 스크래이퍼.
HTTP 요청 + HTML 파싱으로 동작하며, 헤드리스 브라우저 불필요.

### 기술적 근거

리서치 결과(`docs/research-site-analysis.md`) 참고.
- 목록/상세 페이지 모두 SSR → `requests` + `BeautifulSoup`으로 수집 가능
- 세션/쿠키 불필요 (stateless)
- 만료 공고는 `alert("구인정보를 확인할 수 없습니다")` 패턴으로 판별

---

## 2. 프로젝트 구조

```
work24-scraper/
├── init_scrap.py              # CLI: 전체 초기 수집 + DB 초기화
├── resume_scrap.py            # CLI: 중단된 수집 재개
├── sync_scrap.py              # CLI: 신규 공고 추가 (조기 종료)
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
├── pyproject.toml
└── CLAUDE.md
```

### 의존 방향

```
CLI 스크립트 (root) → usecases (순수 로직) → adapters (외부 의존)
                                              ↑
                              models.py (전 계층 공유)
```

- CLI → usecases → adapters 단방향 의존
- adapters 간 상호 의존 없음
- models.py는 모든 계층에서 import

---

## 3. 데이터 모델

### Job dataclass (`models.py`)

```python
@dataclass
class Job:
    # 식별/메타
    wanted_auth_no: str          # 공고 고유 ID ("KF10882603180014")
    scraped_at: str              # 수집 시각 (ISO 8601)

    # 필수 수집 필드
    title: str                   # 제목
    job_description: str         # 업무 내용
    qualification: str           # 지원 자격 (학력 + 자격면허)
    experience: str              # 연차 (경력무관/경력2년 등)
    preferences: str | None      # 우대 사항 (전공/외국어/컴퓨터/기타)
    location: str                # 지역 (전체 주소)
    detail_url: str              # 공고 링크
    hiring_process: str          # 채용 프로세스 (서류/면접/필기/기타)
    employment_conditions: str   # 채용 조건 (고용형태+임금+근무시간+근무형태)
    company: str                 # 회사 (기업명/업종/규모/근로자수)
    benefits: str | None         # 복지 (복리후생 목록)
    application_method: str      # 지원 방법 (접수방법+제출서류+마감일)

    # 동기화/검증용
    deadline_date: str           # 마감일 ("2026-04-01")
    registration_date: str       # 등록일 ("2026-03-18")
```

### 필드 매핑

| 요구 필드 | 모델 필드 | 상세 페이지 소스 |
|-----------|----------|-----------------|
| 제목 | `title` | 공고 제목 |
| 업무 내용 | `job_description` | 모집요강 > 직무내용 |
| 지원 자격 | `qualification` | 학력 + 자격면허 |
| 연차 | `experience` | 경력 조건 |
| 우대 사항 | `preferences` | 우대사항 탭 (전공/외국어/컴퓨터/기타) |
| 지역 | `location` | 근무예정지 주소 |
| 공고 링크 | `detail_url` | 상세 페이지 URL |
| 채용 프로세스 | `hiring_process` | 전형방법 탭 (서류/면접/필기/기타) |
| 채용 조건 | `employment_conditions` | 고용형태 + 임금 + 근무시간 + 근무형태 |
| 회사 | `company` | 기업정보 탭 (기업명/업종/규모/근로자수) |
| 복지 | `benefits` | 복리후생 탭 |
| 지원 방법 | `application_method` | 접수방법 + 제출서류 + 마감일 |

---

## 4. Adapter 계층

### `adapters/scraper.py` — Work24Scraper

```python
class Work24Scraper:
    """고용24 HTTP 요청 + HTML 파싱"""

    def get_total_count() -> int
    def fetch_listing_page(page: int, per_page: int = 50) -> list[str]
    def fetch_job_detail(wanted_auth_no: str) -> Job | None
    def is_job_active(wanted_auth_no: str) -> bool
```

| 메서드 | HTTP 요청 | 설명 |
|--------|----------|------|
| `get_total_count` | POST listing → HTML | `totalRecordCount` JS 변수 파싱 |
| `fetch_listing_page` | POST listing → HTML | `wantedAuthNo` 목록 추출 |
| `fetch_job_detail` | GET detail → HTML | 전체 필드 파싱 → Job 반환. 만료 시 None |
| `is_job_active` | GET detail → HTML | `fetch_job_detail` 결과가 None이면 False |

**HTTP 설정:**
- `requests.Session` (커넥션 재사용)
- 요청 간 딜레이: `time.sleep(0.5)`
- User-Agent: Chrome UA 문자열

**목록 요청:**
```
POST /wk/a/b/1200/retriveDtlEmpSrchListInPost.do
Body: sortField=DATE&sortOrderBy=DESC&pageIndex={page}&resultCnt={per_page}
→ 302 리다이렉트 → GET 응답 (HTML)
```

**상세 요청:**
```
GET /wk/a/b/1500/empDetailAuthView.do
  ?wantedAuthNo={id}&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet
```

**만료 판별:**
- 응답 HTML에 `alert("구인정보를 확인할 수 없습니다")` 포함 시 만료

### `adapters/store.py` — JsonJobStore

```python
class JsonJobStore:
    """JSON 파일 기반 CRUD"""

    def __init__(self, path: str = "data/jobs.json")
    def load_all() -> dict[str, Job]
    def save_all(jobs: dict[str, Job]) -> None
    def get_all_ids() -> set[str]
    def add_job(job: Job) -> None
    def remove_job(wanted_auth_no: str) -> None
    def clear() -> None
```

**저장 형식:**
```json
{
  "KF10882603180014": { "wanted_auth_no": "...", "title": "...", ... },
  "KJKB002603180001": { ... }
}
```

- key: `wanted_auth_no`
- value: Job을 dict로 직렬화
- 원자적 쓰기: 임시파일 작성 → `os.replace()` (데이터 손실 방지)

---

## 5. Usecase 계층

### `usecases/collect.py` — 전체 수집 / 중단 재개

```
_collect_missing(scraper, store, existing_ids) -> CollectResult:
  # 공유 엔진 — 전체 페이지 순회, existing_ids에 없는 공고만 수집
  1. total = scraper.get_total_count()
  2. total_pages = ceil(total / 50)
  3. for page in 1..total_pages:
       ids = scraper.fetch_listing_page(page)
       new_ids = [id for id in ids if id not in existing_ids]
       if not new_ids: continue
       for id in new_ids:
         job = scraper.fetch_job_detail(id)
         if job: store.add_job(job); existing_ids.add(id)
       print progress
  4. return CollectResult(total, collected, failed)

collect_all_jobs(scraper, store) -> CollectResult:
  1. store.clear()
  2. return _collect_missing(scraper, store, existing_ids=set())

resume_collect(scraper, store) -> CollectResult:
  1. existing_ids = store.get_all_ids()
  2. return _collect_missing(scraper, store, existing_ids)
```

- `_collect_missing`은 공유 엔진. init과 resume의 차이는 clear 여부와 초기 existing_ids뿐
- `existing_ids`는 in-place mutate되어 같은 실행 내 중복 요청 방지

### `usecases/sync.py` — 증분 동기화 (sync_scrap)

```
sync_jobs(scraper, store, early_stop=3) -> SyncResult:
  1. existing_ids = store.get_all_ids()
  2. total_pages = ceil(scraper.get_total_count() / 50)
  3. consecutive_empty = 0
  4. for page in 1..total_pages:
       ids = scraper.fetch_listing_page(page)
       new_ids = [id for id in ids if id not in existing_ids]
       if not new_ids:
         consecutive_empty += 1
         if consecutive_empty >= early_stop: break
       else:
         consecutive_empty = 0
         for id in new_ids:
           job = scraper.fetch_job_detail(id)
           if job: store.add_job(job); new_count += 1
       print progress
  5. return SyncResult(scanned_pages, new_count, failed)
```

- 조기 종료: 연속 `early_stop`(기본 3) 페이지 동안 신규 0이면 중단
- init 완료 후 일상 동기화용 — 수십 초에 완료
- `scanned_pages`는 실제 스캔한 페이지 수 (조기 종료 시 전체보다 작음)

### `usecases/validate.py` — 유효성 검증 (validate_job)

```
validate_all_jobs(scraper, store) -> ValidateResult:
  1. jobs = store.load_all()
  2. for wanted_auth_no in jobs:
       if not scraper.is_job_active(wanted_auth_no):
         store.remove_job(wanted_auth_no)
         removed += 1
       print progress
  3. return ValidateResult(total_checked, removed, still_active)
```

---

## 6. CLI 스크립트

각 스크립트는 얇은 진입점. adapter 생성 → usecase 호출 → 결과 출력.

```python
# init_scrap.py
if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()
    result = collect_all_jobs(scraper, store)
    print(result)
```

`sync_scrap.py`, `validate_job.py`도 동일 패턴.
CLI 인자 파싱 없음 (POC).

---

## 7. 기술 스택

| 구분 | 선택 |
|------|------|
| Python | 3.12+ |
| HTTP | `requests` |
| HTML 파싱 | `beautifulsoup4` + `lxml` |
| 직렬화 | `dataclasses` + `json` (stdlib) |
| CLI | `if __name__ == "__main__"` (POC) |

### 의존성 (`pyproject.toml`)

```
requests
beautifulsoup4
lxml
```

---

## 8. 에러 처리

| 상황 | 처리 |
|------|------|
| HTTP 요청 실패 (5xx, timeout) | 로그 출력 후 skip, failed 카운트 증가 |
| HTML 파싱 실패 | 로그 출력 후 skip |
| 만료 공고 상세 접근 | None 반환 (정상 흐름) |
| JSON 파일 없음 | 빈 dict로 초기화 |
| JSON 파일 손상 | 에러 출력 후 종료 |

---

## 9. 성능 추정

| 작업 | 요청 수 | 예상 시간 (0.5s/req) |
|------|---------|---------------------|
| init_scrap 목록 스캔 | ~2,600 pages | ~22분 |
| init_scrap 상세 수집 | ~130,000 jobs | ~18시간 |
| sync_scrap 목록 스캔 | ~2,600 pages | ~22분 |
| sync_scrap 신규 상세 | 신규 건수만큼 | 변동 |
| validate_job | DB 내 전체 건수 | ~18시간 (전체) |
