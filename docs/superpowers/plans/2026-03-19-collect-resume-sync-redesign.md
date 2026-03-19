# collect/resume/sync 역할 분리 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** init(초기화+전체수집), resume(중단재개), sync(조기종료 신규수집)로 역할을 분리하여 각 시나리오에 최적화된 동작을 제공한다.

**Architecture:** `usecases/collect.py`에서 공유 엔진 `_collect_missing()`을 추출하고, `collect_all_jobs()`와 `resume_collect()`가 이를 호출. `usecases/sync.py`에 조기 종료 로직 추가. 새 CLI 진입점 `resume_scrap.py` 추가.

**Tech Stack:** Python 3.12+, pytest, dataclasses

**Spec:** `docs/superpowers/specs/2026-03-19-collect-resume-sync-redesign.md`

---

## File Structure

| 파일 | 역할 | 변경 유형 |
|------|------|----------|
| `usecases/collect.py` | `_collect_missing` 공유 엔진, `collect_all_jobs`, `resume_collect` | 수정 |
| `usecases/sync.py` | `sync_jobs` 조기 종료 추가 | 수정 |
| `resume_scrap.py` | CLI 진입점: 중단 재개 | 신규 |
| `tests/test_collect.py` | collect/resume usecase 단위 테스트 | 신규 |
| `tests/test_sync.py` | sync 조기 종료 단위 테스트 | 신규 |
| `CLAUDE.md` | CLI 명령 표, 프로젝트 구조 갱신 | 수정 |
| `docs/design-spec.md` | usecase 섹션 갱신 | 수정 |

---

### Task 1: collect.py 리팩토링 — 테스트 작성

**Files:**
- Create: `tests/test_collect.py`

테스트에서 scraper/store를 실제 HTTP 없이 검증하기 위해 간단한 fake 객체를 사용한다.

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_collect.py
from models import Job
from usecases.collect import CollectResult, collect_all_jobs, resume_collect


def _make_job(wanted_auth_no: str) -> Job:
    return Job(
        wanted_auth_no=wanted_auth_no,
        scraped_at="2026-03-19T00:00:00",
        title=f"공고 {wanted_auth_no}",
        job_description="테스트",
        qualification="학력무관",
        experience="경력무관",
        preferences=None,
        location="서울",
        detail_url="https://example.com",
        hiring_process="면접",
        employment_conditions="월급 300만원",
        company="테스트회사",
        benefits=None,
        application_method="이메일",
        deadline_date="2026-04-01",
        registration_date="2026-03-19",
    )


class FakeScraper:
    """페이지별 ID 목록과 상세 결과를 미리 지정하는 fake scraper"""

    def __init__(self, pages: dict[int, list[str]], details: dict[str, Job | None]):
        self._pages = pages  # {page_num: [id, ...]}
        self._details = details  # {id: Job | None}
        self._total = sum(len(ids) for ids in pages.values())

    def get_total_count(self) -> int:
        return self._total

    def fetch_listing_page(self, page: int, per_page: int = 50) -> list[str]:
        return self._pages.get(page, [])

    def fetch_job_detail(self, wanted_auth_no: str) -> Job | None:
        return self._details.get(wanted_auth_no)


class FakeStore:
    """in-memory store for testing"""

    def __init__(self, initial: dict[str, Job] | None = None):
        self._jobs: dict[str, Job] = dict(initial) if initial else {}
        self.clear_called = False

    def clear(self) -> None:
        self._jobs.clear()
        self.clear_called = True

    def get_all_ids(self) -> set[str]:
        return set(self._jobs.keys())

    def add_job(self, job: Job) -> None:
        self._jobs[job.wanted_auth_no] = job

    def load_all(self) -> dict[str, Job]:
        return dict(self._jobs)


def test_collect_all_clears_and_collects():
    """collect_all_jobs는 store를 clear한 뒤 전체 수집"""
    job_a = _make_job("A001")
    job_b = _make_job("A002")
    scraper = FakeScraper(
        pages={1: ["A001", "A002"]},
        details={"A001": job_a, "A002": job_b},
    )
    store = FakeStore(initial={"OLD001": _make_job("OLD001")})

    result = collect_all_jobs(scraper, store)

    assert store.clear_called is True
    assert result.collected == 2
    assert result.failed == 0
    assert store.get_all_ids() == {"A001", "A002"}
    assert "OLD001" not in store.get_all_ids()


def test_resume_preserves_existing_and_fills_gaps():
    """resume_collect는 기존 데이터를 보존하고 빠진 공고만 수집"""
    existing_job = _make_job("A001")
    new_job = _make_job("A002")
    scraper = FakeScraper(
        pages={1: ["A001", "A002"]},
        details={"A001": existing_job, "A002": new_job},
    )
    store = FakeStore(initial={"A001": existing_job})

    result = resume_collect(scraper, store)

    assert store.clear_called is False
    assert result.collected == 1  # A002만 신규
    assert store.get_all_ids() == {"A001", "A002"}


def test_resume_on_empty_db_collects_all():
    """빈 DB에서 resume 실행 시 전체 수집 (clear 없이)"""
    job_a = _make_job("A001")
    scraper = FakeScraper(
        pages={1: ["A001"]},
        details={"A001": job_a},
    )
    store = FakeStore()

    result = resume_collect(scraper, store)

    assert store.clear_called is False
    assert result.collected == 1
    assert store.get_all_ids() == {"A001"}


def test_collect_counts_failed_details():
    """상세 조회가 None을 반환하면 failed 카운트 증가"""
    scraper = FakeScraper(
        pages={1: ["A001", "A002"]},
        details={"A001": _make_job("A001"), "A002": None},
    )
    store = FakeStore()

    result = collect_all_jobs(scraper, store)

    assert result.collected == 1
    assert result.failed == 1
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_collect.py -v`
Expected: FAIL — `resume_collect` 함수가 아직 없음

- [ ] **Step 3: 커밋 (테스트만)**

```bash
git add tests/test_collect.py
git commit -m "test: collect/resume usecase 단위 테스트 작성"
```

---

### Task 2: collect.py 리팩토링 — 구현

**Files:**
- Modify: `usecases/collect.py`

- [ ] **Step 1: collect.py를 스펙대로 리팩토링**

`usecases/collect.py` 전체를 다음으로 교체:

```python
from dataclasses import dataclass
from math import ceil


@dataclass
class CollectResult:
    total: int
    collected: int
    failed: int


def _collect_missing(scraper, store, existing_ids: set[str]) -> CollectResult:
    """전체 페이지를 순회하며 existing_ids에 없는 공고만 수집.
    existing_ids는 in-place로 갱신되어 같은 실행 내 중복 요청을 방지한다."""
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    collected = 0
    failed = 0

    for page in range(1, total_pages + 1):
        try:
            ids = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            failed += 50
            continue

        new_ids = [id for id in ids if id not in existing_ids]
        if not new_ids:
            continue

        for wanted_auth_no in new_ids:
            try:
                job = scraper.fetch_job_detail(wanted_auth_no)
                if job:
                    store.add_job(job)
                    existing_ids.add(wanted_auth_no)
                    collected += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[ERROR] 상세 조회 실패 ({wanted_auth_no}): {e}")
                failed += 1

        print(f"[{page}/{total_pages}] 신규: {collected}, 실패: {failed}")

    return CollectResult(total=total, collected=collected, failed=failed)


def collect_all_jobs(scraper, store) -> CollectResult:
    """완전 초기 수집 — DB 초기화 후 전체 수집"""
    store.clear()
    return _collect_missing(scraper, store, existing_ids=set())


def resume_collect(scraper, store) -> CollectResult:
    """중단 재개 — 기존 데이터 보존, 빠진 공고만 수집.
    빈 DB에서 실행하면 collect_all_jobs와 동일하게 전체 수집 (clear 없이)."""
    existing_ids = store.get_all_ids()
    print(f"[RESUME] 기존 {len(existing_ids)}건 보존, 빠진 공고 수집")
    return _collect_missing(scraper, store, existing_ids)
```

- [ ] **Step 2: 테스트 통과 확인**

Run: `pytest tests/test_collect.py -v`
Expected: 4 passed

- [ ] **Step 3: 기존 테스트 전체 통과 확인**

Run: `pytest tests/ -v`
Expected: 전체 통과 (기존 15 + 신규 4 = 19 passed)

- [ ] **Step 4: 커밋**

```bash
git add usecases/collect.py
git commit -m "refactor: collect.py에서 _collect_missing 공유 엔진 추출, resume_collect 추가"
```

---

### Task 3: sync.py 조기 종료 — 테스트 작성

**Files:**
- Create: `tests/test_sync.py`

Task 1의 `FakeScraper`/`FakeStore`를 재사용한다. 테스트 간 중복을 피하기 위해 `tests/conftest.py`에 공유 fixture를 추출할 수도 있지만, 현재 규모에서는 각 테스트 파일에 독립적으로 두는 것이 명확하다.

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_sync.py
from models import Job
from usecases.sync import SyncResult, sync_jobs


def _make_job(wanted_auth_no: str) -> Job:
    return Job(
        wanted_auth_no=wanted_auth_no,
        scraped_at="2026-03-19T00:00:00",
        title=f"공고 {wanted_auth_no}",
        job_description="테스트",
        qualification="학력무관",
        experience="경력무관",
        preferences=None,
        location="서울",
        detail_url="https://example.com",
        hiring_process="면접",
        employment_conditions="월급 300만원",
        company="테스트회사",
        benefits=None,
        application_method="이메일",
        deadline_date="2026-04-01",
        registration_date="2026-03-19",
    )


class FakeScraper:
    def __init__(self, pages: dict[int, list[str]], details: dict[str, Job | None]):
        self._pages = pages
        self._details = details
        self._total = sum(len(ids) for ids in pages.values())
        self.fetched_pages: list[int] = []

    def get_total_count(self) -> int:
        return self._total

    def fetch_listing_page(self, page: int, per_page: int = 50) -> list[str]:
        self.fetched_pages.append(page)
        return self._pages.get(page, [])

    def fetch_job_detail(self, wanted_auth_no: str) -> Job | None:
        return self._details.get(wanted_auth_no)


class FakeStore:
    def __init__(self, initial: dict[str, Job] | None = None):
        self._jobs: dict[str, Job] = dict(initial) if initial else {}

    def get_all_ids(self) -> set[str]:
        return set(self._jobs.keys())

    def add_job(self, job: Job) -> None:
        self._jobs[job.wanted_auth_no] = job

    def load_all(self) -> dict[str, Job]:
        return dict(self._jobs)


def test_sync_collects_new_jobs():
    """기존에 없는 신규 공고만 수집"""
    existing = _make_job("A001")
    new_job = _make_job("A002")
    scraper = FakeScraper(
        pages={1: ["A001", "A002"]},
        details={"A002": new_job},
    )
    store = FakeStore(initial={"A001": existing})

    result = sync_jobs(scraper, store)

    assert result.new_count == 1
    assert store.get_all_ids() == {"A001", "A002"}


def test_sync_early_stop():
    """연속 empty_stop 페이지 동안 신규 없으면 조기 종료"""
    # 5페이지 구성: page 1에 신규 1건, page 2~4는 전부 기존
    existing_a = _make_job("A001")
    existing_b = _make_job("B001")
    existing_c = _make_job("C001")
    new_job = _make_job("NEW01")
    scraper = FakeScraper(
        pages={
            1: ["NEW01"],
            2: ["A001"],
            3: ["B001"],
            4: ["C001"],
            5: ["A001"],  # 여기까지 도달하면 안 됨
        },
        details={"NEW01": new_job},
    )
    store = FakeStore(initial={
        "A001": existing_a,
        "B001": existing_b,
        "C001": existing_c,
    })

    result = sync_jobs(scraper, store, early_stop=3)

    assert result.new_count == 1
    # page 2, 3, 4에서 연속 3회 empty → page 5 도달 전 중단
    assert 5 not in scraper.fetched_pages
    assert result.scanned_pages == 4


def test_sync_no_early_stop_when_new_found():
    """신규가 발견되면 consecutive_empty 리셋"""
    job_a = _make_job("A001")
    job_c = _make_job("C001")
    scraper = FakeScraper(
        pages={
            1: ["A001"],    # 전부 기존
            2: ["A001"],    # 전부 기존
            3: ["C001"],    # 신규 → 리셋
            4: ["A001"],    # 전부 기존
            5: ["A001"],    # 전부 기존
        },
        details={"C001": job_c},
    )
    store = FakeStore(initial={"A001": job_a})

    result = sync_jobs(scraper, store, early_stop=3)

    assert result.new_count == 1
    # page 3에서 리셋되므로 page 5까지 도달
    assert 5 in scraper.fetched_pages


def test_sync_scanned_pages_reflects_actual():
    """scanned_pages는 실제 스캔한 페이지 수를 반영"""
    scraper = FakeScraper(
        pages={1: ["A001"], 2: ["A001"], 3: ["A001"]},
        details={},
    )
    store = FakeStore(initial={"A001": _make_job("A001")})

    result = sync_jobs(scraper, store, early_stop=3)

    assert result.scanned_pages == 3
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_sync.py -v`
Expected: FAIL — `sync_jobs`가 `early_stop` 파라미터를 아직 받지 않음

- [ ] **Step 3: 커밋 (테스트만)**

```bash
git add tests/test_sync.py
git commit -m "test: sync 조기 종료 단위 테스트 작성"
```

---

### Task 4: sync.py 조기 종료 — 구현

**Files:**
- Modify: `usecases/sync.py`

- [ ] **Step 1: sync.py를 스펙대로 수정**

`usecases/sync.py` 전체를 다음으로 교체:

```python
from dataclasses import dataclass
from math import ceil


@dataclass
class SyncResult:
    scanned_pages: int
    new_count: int
    failed: int


def sync_jobs(scraper, store, early_stop: int = 3) -> SyncResult:
    """신규 공고만 추가 — 연속 early_stop 페이지 신규 0이면 중단"""
    existing_ids = store.get_all_ids()
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    new_count = 0
    failed = 0
    scanned_pages = 0
    consecutive_empty = 0

    for page in range(1, total_pages + 1):
        scanned_pages = page
        try:
            ids = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            continue

        new_ids = [id for id in ids if id not in existing_ids]

        if not new_ids:
            consecutive_empty += 1
            if consecutive_empty >= early_stop:
                print(f"[STOP] 연속 {early_stop}페이지 신규 없음 → 스캔 중단")
                break
        else:
            consecutive_empty = 0
            for wanted_auth_no in new_ids:
                try:
                    job = scraper.fetch_job_detail(wanted_auth_no)
                    if job:
                        store.add_job(job)
                        existing_ids.add(wanted_auth_no)
                        new_count += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"[ERROR] 상세 조회 실패 ({wanted_auth_no}): {e}")
                    failed += 1

        print(f"[{page}] 신규: {len(new_ids)}, 누적: {new_count}")

    return SyncResult(scanned_pages=scanned_pages, new_count=new_count, failed=failed)
```

- [ ] **Step 2: sync 테스트 통과 확인**

Run: `pytest tests/test_sync.py -v`
Expected: 4 passed

- [ ] **Step 3: 전체 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: 전체 통과 (기존 15 + collect 4 + sync 4 = 23 passed)

- [ ] **Step 4: 커밋**

```bash
git add usecases/sync.py
git commit -m "feat: sync_jobs에 early_stop 조기 종료 로직 추가"
```

---

### Task 5: resume_scrap.py CLI 진입점

**Files:**
- Create: `resume_scrap.py`

- [ ] **Step 1: resume_scrap.py 작성**

```python
from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.collect import resume_collect

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 고용24 채용공고 수집 재개 ===")
    result = resume_collect(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"총 공고: {result.total}")
    print(f"신규 수집: {result.collected}")
    print(f"실패: {result.failed}")
```

- [ ] **Step 2: import 검증**

Run: `python -c "from usecases.collect import resume_collect; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add resume_scrap.py
git commit -m "feat: resume_scrap.py CLI 진입점 추가"
```

---

### Task 6: 문서 갱신

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/design-spec.md`

- [ ] **Step 1: CLAUDE.md CLI 테이블에 resume_scrap 추가**

CLI 스크립트 테이블을 다음으로 교체:

```markdown
| 명령 | 설명 |
|------|------|
| `init_scrap` | 고용24 전체 채용공고 수집 + storage 초기화 |
| `resume_scrap` | 중단된 수집 재개 (기존 데이터 보존, 빠진 공고만 수집) |
| `sync_scrap` | 신규 공고 추가 (최신 페이지 위주 조기 종료) |
| `validate_job` | 수집된 공고의 유효성 검증, 마감 공고 제거 |
```

- [ ] **Step 2: CLAUDE.md 사용법 섹션에 resume_scrap.py 추가**

사용법 코드 블록에 추가:

```bash
python resume_scrap.py   # 중단된 수집 재개
```

- [ ] **Step 3: CLAUDE.md 프로젝트 구조에 resume_scrap.py 추가**

프로젝트 구조 블록에서 `sync_scrap.py` 아래에 추가:

```
├── resume_scrap.py            # CLI: 중단된 수집 재개
```

- [ ] **Step 4: docs/design-spec.md usecase 섹션 갱신**

섹션 5의 `usecases/collect.py` 부분을 다음으로 교체:

```markdown
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
```

섹션 5의 `usecases/sync.py` 부분을 다음으로 교체:

```markdown
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
```

- [ ] **Step 5: 커밋**

```bash
git add CLAUDE.md docs/design-spec.md
git commit -m "docs: resume_scrap 추가 및 collect/sync 변경사항 문서 반영"
```

---

### Task 7: 최종 검증

- [ ] **Step 1: 전체 테스트 실행**

Run: `pytest tests/ -v`
Expected: 23 passed (models 3 + store 6 + scraper_parse 4 + collect 4 + sync 4 + 기존 2 = 약 23)

- [ ] **Step 2: import 검증**

```bash
python -c "
from usecases.collect import collect_all_jobs, resume_collect, CollectResult
from usecases.sync import sync_jobs, SyncResult
print('collect_all_jobs:', collect_all_jobs)
print('resume_collect:', resume_collect)
print('sync_jobs:', sync_jobs)
print('All imports OK')
"
```
Expected: 모든 import 성공

- [ ] **Step 3: CLI 스크립트 import 검증**

```bash
python -c "import init_scrap; print('init OK')"
python -c "import resume_scrap; print('resume OK')"
python -c "import sync_scrap; print('sync OK')"
python -c "import validate_job; print('validate OK')"
```
Expected: 모든 import 성공 (실행은 `__main__` 가드로 방지)

- [ ] **Step 4: 커밋 (필요 시)**

변경사항이 있으면 커밋. 없으면 skip.
