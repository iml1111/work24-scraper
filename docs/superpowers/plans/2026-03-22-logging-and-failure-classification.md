# 로깅 개선 및 실패 분류 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스크래이퍼의 실패 원인을 구분(만료/차단/에러)하고, 건별 + 페이지 요약 로그를 출력하며, 딜레이를 3~7초로 상향한다.

**Architecture:** `fetch_job_detail` 반환값을 `tuple[Job | None, str]`로 변경하여 status를 전파. usecase 레이어에서 status별 카운터 관리 및 로그 출력. CLI 스크립트에서 최종 요약 출력.

**Tech Stack:** Python 3.12+, dataclasses, pytest

**Spec:** `docs/superpowers/specs/2026-03-22-logging-and-failure-classification-design.md`

---

### Task 1: `adapters/scraper.py` — 응답 분류 및 딜레이 변경

**Files:**
- Modify: `adapters/scraper.py` — `parse_job_detail` 만료 체크 제거 + 반환 타입 `Job | None` → `Job`
- Modify: `adapters/scraper.py` — 딜레이 기본값 변경
- Modify: `adapters/scraper.py` — `fetch_job_detail` 반환값 `tuple[Job | None, str]`로 변경
- Test: `tests/test_scraper_parse.py`

- [ ] **Step 1: 기존 테스트 통과 확인**

Run: `pytest tests/test_scraper_parse.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 2: `parse_job_detail`에서 만료 체크 제거 + 반환 타입 변경**

두 가지 변경:
1. `is_expired_page` 체크 2줄 제거 (lines 290-291)
2. 반환 타입 `Job | None` → `Job` (line 288)

```python
# 기존
def parse_job_detail(html: str, wanted_auth_no: str) -> Job | None:
    """상세 페이지 HTML을 파싱하여 Job 객체 반환. 만료 시 None."""
    if is_expired_page(html):
        return None

# 변경 (만료 체크 제거, 반환 타입 Job으로 변경)
def parse_job_detail(html: str, wanted_auth_no: str) -> Job:
    """상세 페이지 HTML을 파싱하여 Job 객체 반환."""
```

- [ ] **Step 3: `test_scraper_parse.py` — `test_parse_job_detail` 만료 테스트 분리 확인**

`test_is_expired_page_true`와 `test_is_expired_page_false`는 `is_expired_page` 직접 테스트이므로 영향 없음.

Run: `pytest tests/test_scraper_parse.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 4: `fetch_job_detail` 반환값을 `tuple[Job | None, str]`로 변경**

`adapters/scraper.py:494-503`:

```python
def fetch_job_detail(self, wanted_auth_no: str) -> tuple[Job | None, str]:
    """상세 페이지 조회. 반환: (job, status). status: 'ok'|'expired'|'blocked'|'error'"""
    try:
        resp = self._request_with_delay(
            "GET", DETAIL_URL,
            params={"wantedAuthNo": wanted_auth_no, "infoTypeCd": "VALIDATION", "infoTypeGroup": "tb_workinfoworknet"},
        )
        if self._is_blocked(resp):
            return (None, "blocked")
        if is_expired_page(resp.text):
            return (None, "expired")
        job = parse_job_detail(resp.text, wanted_auth_no)
        if job:
            return (job, "ok")
        return (None, "error")
    except requests.RequestException:
        return (None, "error")
```

- [ ] **Step 5: 딜레이 기본값 변경**

`adapters/scraper.py:393`:

```python
# 기존
delay_range: tuple[float, float] = (0.3, 1.5),

# 변경
delay_range: tuple[float, float] = (3.0, 7.0),
```

- [ ] **Step 6: 테스트 확인**

Run: `pytest tests/test_scraper_parse.py -v`
Expected: 모든 테스트 PASS (파싱 테스트는 HTTP 무관)

- [ ] **Step 7: 커밋**

```bash
git add adapters/scraper.py
git commit -m "refactor: fetch_job_detail 반환값 분류 및 딜레이 상향"
```

---

### Task 2: `usecases/collect.py` — 분류별 카운터 및 로그

**Files:**
- Modify: `usecases/collect.py` (CollectResult, _collect_missing)
- Test: `tests/test_collect.py`

- [ ] **Step 1: 테스트의 `FakeScraper.fetch_job_detail` 반환값을 튜플로 변경**

`tests/test_collect.py:40-41`:

```python
# 기존
def fetch_job_detail(self, wanted_auth_no: str) -> Job | None:
    return self._details.get(wanted_auth_no)

# 변경
def fetch_job_detail(self, wanted_auth_no: str) -> tuple[Job | None, str]:
    job = self._details.get(wanted_auth_no)
    if job is None:
        return (None, "expired")
    return (job, "ok")
```

- [ ] **Step 2: `CollectResult` 필드 변경**

`usecases/collect.py:6-9`:

```python
# 기존
@dataclass
class CollectResult:
    total: int
    collected: int
    failed: int

# 변경
@dataclass
class CollectResult:
    total: int
    collected: int
    expired: int
    blocked: int
    errors: int
```

- [ ] **Step 3: `_collect_missing` 제어 흐름 변경**

`usecases/collect.py:12-54` 전체를 변경:

```python
def _collect_missing(
    scraper,
    store,
    existing_ids: set[str],
    start_page: int = 1,
    max_pages: int | None = None,
) -> CollectResult:
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    end_page = min(total_pages, start_page + max_pages - 1) if max_pages else total_pages
    collected = 0
    expired = 0
    blocked = 0
    errors = 0

    for page in range(start_page, end_page + 1):
        try:
            ids = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            errors += 50
            continue

        new_ids = [id for id in ids if id not in existing_ids]
        if not new_ids:
            continue

        for wanted_auth_no in new_ids:
            try:
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
            except Exception:
                errors += 1
                print(f"[{page}/{total_pages}] {wanted_auth_no} → 에러")

        print(f"[{page}/{total_pages} 완료] 신규: {collected}, 만료: {expired}, 차단: {blocked}, 에러: {errors}")

    return CollectResult(total=total, collected=collected, expired=expired, blocked=blocked, errors=errors)
```

- [ ] **Step 4: 기존 테스트 assertion 업데이트**

`tests/test_collect.py`:

`test_collect_all_clears_and_collects` (line 78-80):
```python
# 기존
assert result.collected == 2
assert result.failed == 0

# 변경
assert result.collected == 2
assert result.expired == 0
assert result.blocked == 0
assert result.errors == 0
```

`test_resume_preserves_existing_and_fills_gaps` (line 97):
```python
# 기존
assert result.collected == 1

# 변경
assert result.collected == 1
assert result.expired == 0
```

`test_resume_on_empty_db_collects_all` (line 113):
```python
# 기존
assert result.collected == 1

# 변경
assert result.collected == 1
assert result.expired == 0
```

`test_collect_counts_failed_details` (line 126-128):
```python
# 기존
assert result.collected == 1
assert result.failed == 1

# 변경 (FakeScraper가 None을 "expired"로 반환하므로)
assert result.collected == 1
assert result.expired == 1
assert result.blocked == 0
assert result.errors == 0
```

- [ ] **Step 5: 테스트 실행**

Run: `pytest tests/test_collect.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add usecases/collect.py tests/test_collect.py
git commit -m "feat: collect 분류별 카운터 및 건별 로그 출력"
```

---

### Task 3: `usecases/sync.py` — 동일 패턴 적용

**Files:**
- Modify: `usecases/sync.py` (SyncResult, sync_jobs)
- Test: `tests/test_sync.py`

- [ ] **Step 1: 테스트의 `FakeScraper.fetch_job_detail` 반환값을 튜플로 변경**

`tests/test_sync.py:40-41`:

```python
# 기존
def fetch_job_detail(self, wanted_auth_no: str) -> Job | None:
    return self._details.get(wanted_auth_no)

# 변경
def fetch_job_detail(self, wanted_auth_no: str) -> tuple[Job | None, str]:
    job = self._details.get(wanted_auth_no)
    if job is None:
        return (None, "expired")
    return (job, "ok")
```

- [ ] **Step 2: `SyncResult` 필드 변경**

`usecases/sync.py:6-9`:

```python
# 기존
@dataclass
class SyncResult:
    scanned_pages: int
    new_count: int
    failed: int

# 변경
@dataclass
class SyncResult:
    scanned_pages: int
    new_count: int
    expired: int
    blocked: int
    errors: int
```

- [ ] **Step 3: `sync_jobs` 제어 흐름 변경**

`usecases/sync.py:12-54`:

```python
def sync_jobs(scraper, store, early_stop: int = 3) -> SyncResult:
    """신규 공고만 추가 — 연속 early_stop 페이지 신규 0이면 중단"""
    existing_ids = store.get_all_ids()
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    new_count = 0
    expired = 0
    blocked = 0
    errors = 0
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
                    job, status = scraper.fetch_job_detail(wanted_auth_no)
                    if status == "ok":
                        store.add_job(job)
                        existing_ids.add(wanted_auth_no)
                        new_count += 1
                        print(f"[{page}] {wanted_auth_no} {job.title} → 수집")
                    elif status == "expired":
                        expired += 1
                        print(f"[{page}] {wanted_auth_no} → 만료")
                    elif status == "blocked":
                        blocked += 1
                        print(f"[{page}] {wanted_auth_no} → 차단")
                    else:
                        errors += 1
                        print(f"[{page}] {wanted_auth_no} → 에러")
                except Exception:
                    errors += 1
                    print(f"[{page}] {wanted_auth_no} → 에러")

        print(f"[{page}] 신규: {len(new_ids)}, 누적: {new_count}")

    return SyncResult(scanned_pages=scanned_pages, new_count=new_count, expired=expired, blocked=blocked, errors=errors)
```

- [ ] **Step 4: 테스트 실행**

Run: `pytest tests/test_sync.py -v`
Expected: 모든 테스트 PASS (기존 assertion은 `new_count`, `scanned_pages`만 검증하므로 통과)

- [ ] **Step 5: 커밋**

```bash
git add usecases/sync.py tests/test_sync.py
git commit -m "feat: sync 분류별 카운터 및 건별 로그 출력"
```

---

### Task 4: CLI 스크립트 출력 변경

**Files:**
- Modify: `init_scrap.py` — 최종 출력 print 문
- Modify: `resume_scrap.py` — 최종 출력 print 문
- Modify: `sync_scrap.py` — 최종 출력 print 문

- [ ] **Step 1: `init_scrap.py` 최종 출력 변경**

```python
# 기존
print(f"총 공고: {result.total}")
print(f"수집 성공: {result.collected}")
print(f"수집 실패: {result.failed}")

# 변경
print(f"총 공고: {result.total}")
print(f"수집 성공: {result.collected}")
print(f"만료 스킵: {result.expired}")
print(f"차단: {result.blocked}")
print(f"에러: {result.errors}")
```

- [ ] **Step 2: `resume_scrap.py` 최종 출력 변경**

```python
# 기존
print(f"총 공고: {result.total}")
print(f"신규 수집: {result.collected}")
print(f"실패: {result.failed}")

# 변경
print(f"총 공고: {result.total}")
print(f"수집 성공: {result.collected}")
print(f"만료 스킵: {result.expired}")
print(f"차단: {result.blocked}")
print(f"에러: {result.errors}")
```

- [ ] **Step 3: `sync_scrap.py` 최종 출력 변경**

```python
# 기존
print(f"스캔 페이지: {result.scanned_pages}")
print(f"신규 추가: {result.new_count}")
print(f"실패: {result.failed}")

# 변경
print(f"스캔 페이지: {result.scanned_pages}")
print(f"신규 추가: {result.new_count}")
print(f"만료 스킵: {result.expired}")
print(f"차단: {result.blocked}")
print(f"에러: {result.errors}")
```

- [ ] **Step 4: 전체 테스트 실행**

Run: `pytest -v`
Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add init_scrap.py resume_scrap.py sync_scrap.py
git commit -m "feat: CLI 출력에 분류별 결과 표시"
```

---

### Task 5: 진단 스크립트 정리

**Files:**
- Delete: `scripts/diagnose_responses.py`
- Delete: `scripts/diagnose_fast.py`

- [ ] **Step 1: 진단 스크립트 삭제**

```bash
rm scripts/diagnose_responses.py scripts/diagnose_fast.py
```

- [ ] **Step 2: 커밋**

```bash
git add -u scripts/
git commit -m "chore: 진단 스크립트 정리"
```
