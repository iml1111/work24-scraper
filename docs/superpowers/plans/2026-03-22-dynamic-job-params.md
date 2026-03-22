# 공고 유형별 동적 파라미터 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 목록 페이지 링크의 `infoTypeCd`/`infoTypeGroup` 파라미터를 동적으로 추출하여 모든 유형의 공고를 정상 조회한다.

**Architecture:** `JobRef` dataclass 도입으로 ID+파라미터를 묶어 전달. `parse_listing_ids` → `parse_listing_refs`로 전체 파라미터 추출. `fetch_job_detail`과 `parse_job_detail`이 `JobRef`를 받아 동적 파라미터 사용.

**Tech Stack:** Python 3.12+, dataclasses, pytest

**Spec:** `docs/superpowers/specs/2026-03-22-dynamic-job-params-design.md`

---

### Task 1: `domain/models.py` — `JobRef` dataclass 추가

**Files:**
- Modify: `domain/models.py`

- [ ] **Step 1: `JobRef` dataclass 추가**

`domain/models.py`의 `Job` 클래스 위에 추가:

```python
@dataclass
class JobRef:
    wanted_auth_no: str
    info_type_cd: str
    info_type_group: str
```

- [ ] **Step 2: 테스트 확인**

Run: `pytest tests/test_models.py -v`
Expected: 기존 테스트 PASS (Job 모델 변경 없음)

- [ ] **Step 3: 커밋**

```bash
git add domain/models.py
git commit -m "feat: JobRef dataclass 추가"
```

---

### Task 2: `adapters/scraper.py` — 목록 파싱 + 상세 조회 변경

**Files:**
- Modify: `adapters/scraper.py`
- Modify: `tests/test_scraper_parse.py`

- [ ] **Step 1: `parse_listing_ids` → `parse_listing_refs` 변경**

`adapters/scraper.py`에서 `parse_listing_ids` 함수를 `parse_listing_refs`로 교체:

```python
def parse_listing_refs(html: str) -> list[JobRef]:
    """HTML에서 JobRef 목록 추출 (empDetailAuthView 링크의 전체 파라미터)"""
    matches = re.findall(r'empDetailAuthView\.do\?([^"\']+)', html)
    seen: set[str] = set()
    result: list[JobRef] = []
    for param_str in matches:
        params = dict(p.split("=", 1) for p in param_str.split("&") if "=" in p)
        auth_no = params.get("wantedAuthNo", "")
        if not auth_no or auth_no in seen:
            continue
        seen.add(auth_no)
        result.append(JobRef(
            wanted_auth_no=auth_no,
            info_type_cd=params.get("infoTypeCd", ""),
            info_type_group=params.get("infoTypeGroup", ""),
        ))
    return result
```

import에 `JobRef` 추가:

```python
from domain.models import Job, JobRef
```

- [ ] **Step 2: `fetch_listing_page` 반환값 변경**

```python
# 기존
def fetch_listing_page(self, page: int, per_page: int = 50) -> list[str]:
    ...
    return parse_listing_ids(resp.text)

# 변경
def fetch_listing_page(self, page: int, per_page: int = 50) -> list[JobRef]:
    ...
    return parse_listing_refs(resp.text)
```

- [ ] **Step 3: `parse_job_detail` 시그니처 변경**

```python
# 기존
def parse_job_detail(html: str, wanted_auth_no: str) -> Job:
    ...
    detail_url = (
        f"{DETAIL_URL}?wantedAuthNo={wanted_auth_no}"
        "&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet"
    )
    ...
    return Job(wanted_auth_no=wanted_auth_no, ...)

# 변경
def parse_job_detail(html: str, ref: JobRef) -> Job:
    ...
    detail_url = (
        f"{DETAIL_URL}?wantedAuthNo={ref.wanted_auth_no}"
        f"&infoTypeCd={ref.info_type_cd}&infoTypeGroup={ref.info_type_group}"
    )
    ...
    return Job(wanted_auth_no=ref.wanted_auth_no, ...)
```

함수 내부에서 `wanted_auth_no`를 직접 사용하는 모든 곳을 `ref.wanted_auth_no`로 변경.

- [ ] **Step 4: `fetch_job_detail` 시그니처 변경**

```python
# 기존
def fetch_job_detail(self, wanted_auth_no: str) -> tuple[Job | None, str]:
    try:
        resp = self._request_with_delay(
            "GET", DETAIL_URL,
            params={"wantedAuthNo": wanted_auth_no, "infoTypeCd": "VALIDATION", "infoTypeGroup": "tb_workinfoworknet"},
        )
        ...
        job = parse_job_detail(resp.text, wanted_auth_no)
        ...

# 변경
def fetch_job_detail(self, ref: JobRef) -> tuple[Job | None, str]:
    try:
        resp = self._request_with_delay(
            "GET", DETAIL_URL,
            params={
                "wantedAuthNo": ref.wanted_auth_no,
                "infoTypeCd": ref.info_type_cd,
                "infoTypeGroup": ref.info_type_group,
            },
        )
        ...
        job = parse_job_detail(resp.text, ref)
        ...
```

- [ ] **Step 5: 테스트 업데이트 — `test_scraper_parse.py`**

import 변경:

```python
from adapters.scraper import (
    is_expired_page,
    parse_job_detail,
    parse_listing_refs,
    parse_total_count,
)
from domain.models import JobRef
```

`WANTED_AUTH_NO` 상수를 `TEST_REF`로 변경:

```python
TEST_REF = JobRef(
    wanted_auth_no="Dd04022603180062",
    info_type_cd="VALIDATION",
    info_type_group="tb_workinfoworknet",
)
```

`test_parse_listing_ids` → `test_parse_listing_refs`:

```python
def test_parse_listing_refs():
    html = read_fixture("listing_page.html")
    refs = parse_listing_refs(html)
    assert len(refs) == 10
    assert all(isinstance(ref, JobRef) for ref in refs)
    assert all(len(ref.wanted_auth_no) > 5 for ref in refs)
    assert all(ref.info_type_cd for ref in refs)
    assert all(ref.info_type_group for ref in refs)
    # All IDs should be unique
    auth_nos = [ref.wanted_auth_no for ref in refs]
    assert len(auth_nos) == len(set(auth_nos))
```

`test_parse_job_detail` 및 `test_parse_job_detail_has_required_fields`에서 `WANTED_AUTH_NO` → `TEST_REF`:

```python
def test_parse_job_detail():
    html = read_fixture("detail_page.html")
    job = parse_job_detail(html, TEST_REF)
    ...

def test_parse_job_detail_has_required_fields():
    html = read_fixture("detail_page.html")
    job = parse_job_detail(html, TEST_REF)
    ...
```

- [ ] **Step 6: 테스트 실행**

Run: `pytest tests/test_scraper_parse.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 7: 커밋**

```bash
git add adapters/scraper.py tests/test_scraper_parse.py
git commit -m "refactor: JobRef 기반 동적 파라미터로 목록/상세 조회 변경"
```

---

### Task 3: `usecases/collect.py` — JobRef 기반 순회

**Files:**
- Modify: `usecases/collect.py`
- Modify: `tests/test_collect.py`

- [ ] **Step 1: `_collect_missing`에서 `ids` → `refs` 변경**

`usecases/collect.py`의 `_collect_missing` 함수 변경:

```python
# 기존
ids = scraper.fetch_listing_page(page)
...
new_ids = [id for id in ids if id not in existing_ids]
...
for wanted_auth_no in new_ids:
    job, status = scraper.fetch_job_detail(wanted_auth_no)
    if status == "ok":
        store.add_job(job)
        existing_ids.add(wanted_auth_no)
        collected += 1
        print(f"[{page}/{total_pages}] {wanted_auth_no} {job.title} → 수집")
    elif status == "expired":
        expired += 1
        print(f"[{page}/{total_pages}] {wanted_auth_no} → 만료")
    elif status == "blocked":
        blocked += 1
        print(f"[{page}/{total_pages}] {wanted_auth_no} → 차단")
    else:
        errors += 1
        print(f"[{page}/{total_pages}] {wanted_auth_no} → 에러")
...
    print(f"[{page}/{total_pages}] {wanted_auth_no} → 에러: {e}")

# 변경
refs = scraper.fetch_listing_page(page)
...
new_refs = [ref for ref in refs if ref.wanted_auth_no not in existing_ids]
...
for ref in new_refs:
    job, status = scraper.fetch_job_detail(ref)
    if status == "ok":
        store.add_job(job)
        existing_ids.add(ref.wanted_auth_no)
        collected += 1
        print(f"[{page}/{total_pages}] {ref.wanted_auth_no} {job.title} → 수집")
    elif status == "expired":
        expired += 1
        print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 만료")
    elif status == "blocked":
        blocked += 1
        print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 차단")
    else:
        errors += 1
        print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 에러")
...
    print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 에러: {e}")
```

- [ ] **Step 2: 테스트 FakeScraper 변경**

`tests/test_collect.py`:

import에 `JobRef` 추가:

```python
from domain.models import Job, JobRef
```

헬퍼 함수 추가:

```python
def _make_ref(wanted_auth_no: str) -> JobRef:
    return JobRef(wanted_auth_no=wanted_auth_no, info_type_cd="VALIDATION", info_type_group="tb_workinfoworknet")
```

FakeScraper 변경:

```python
class FakeScraper:
    """페이지별 JobRef 목록과 상세 결과를 미리 지정하는 fake scraper"""

    def __init__(self, pages: dict[int, list[str]], details: dict[str, Job | None]):
        self._pages = pages
        self._details = details
        self._total = sum(len(ids) for ids in pages.values())

    def get_total_count(self) -> int:
        return self._total

    def fetch_listing_page(self, page: int, per_page: int = 50) -> list[JobRef]:
        return [_make_ref(id) for id in self._pages.get(page, [])]

    def fetch_job_detail(self, ref: JobRef) -> tuple[Job | None, str]:
        job = self._details.get(ref.wanted_auth_no)
        if job is None:
            return (None, "expired")
        return (job, "ok")
```

핵심: `__init__`의 `pages` 시그니처는 `dict[int, list[str]]`로 유지하여 테스트 코드 변경 최소화. `fetch_listing_page`에서 `_make_ref`로 변환.

- [ ] **Step 3: 테스트 실행**

Run: `pytest tests/test_collect.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 4: 커밋**

```bash
git add usecases/collect.py tests/test_collect.py
git commit -m "refactor: collect에서 JobRef 기반 순회"
```

---

### Task 4: `usecases/sync.py` — JobRef 기반 순회

**Files:**
- Modify: `usecases/sync.py`
- Modify: `tests/test_sync.py`

- [ ] **Step 1: `sync_jobs`에서 `ids` → `refs` 변경**

`usecases/sync.py`에서 동일 패턴 적용:

```python
# 기존
ids = scraper.fetch_listing_page(page)
...
new_ids = [id for id in ids if id not in existing_ids]
...
for wanted_auth_no in new_ids:
    job, status = scraper.fetch_job_detail(wanted_auth_no)
    ...

# 변경
refs = scraper.fetch_listing_page(page)
...
new_refs = [ref for ref in refs if ref.wanted_auth_no not in existing_ids]
...
for ref in new_refs:
    job, status = scraper.fetch_job_detail(ref)
    ...
```

모든 `wanted_auth_no` → `ref.wanted_auth_no`, `new_ids` → `new_refs` 변경.

- [ ] **Step 2: 테스트 FakeScraper 변경**

`tests/test_sync.py`에 Task 3과 동일한 패턴 적용:

```python
from domain.models import Job, JobRef

def _make_ref(wanted_auth_no: str) -> JobRef:
    return JobRef(wanted_auth_no=wanted_auth_no, info_type_cd="VALIDATION", info_type_group="tb_workinfoworknet")
```

FakeScraper 변경:

```python
class FakeScraper:
    def __init__(self, pages: dict[int, list[str]], details: dict[str, Job | None]):
        self._pages = pages
        self._details = details
        self._total = max(pages.keys(), default=0) * 50
        self.fetched_pages: list[int] = []

    def get_total_count(self) -> int:
        return self._total

    def fetch_listing_page(self, page: int, per_page: int = 50) -> list[JobRef]:
        self.fetched_pages.append(page)
        return [_make_ref(id) for id in self._pages.get(page, [])]

    def fetch_job_detail(self, ref: JobRef) -> tuple[Job | None, str]:
        job = self._details.get(ref.wanted_auth_no)
        if job is None:
            return (None, "expired")
        return (job, "ok")
```

- [ ] **Step 3: 테스트 실행**

Run: `pytest tests/test_sync.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 4: 전체 테스트 확인**

Run: `pytest -v`
Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add usecases/sync.py tests/test_sync.py
git commit -m "refactor: sync에서 JobRef 기반 순회"
```

---

### Task 5: 진단 스크립트 정리

**Files:**
- Delete: `scripts/diagnose_listing.py`

- [ ] **Step 1: 삭제**

```bash
rm scripts/diagnose_listing.py
```

- [ ] **Step 2: 커밋**

```bash
git add -u scripts/
git commit -m "chore: 진단 스크립트 정리"
```
