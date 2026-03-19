# collect/resume/sync 역할 분리 설계

> 작성일: 2026-03-19
> 상태: 승인됨

## 1. 문제

현재 구조의 두 가지 문제:

1. **init 재개 불가**: `collect_all_jobs()`가 `store.clear()`를 무조건 호출하므로, 중단 후 재실행하면 기존 데이터가 삭제된다.
2. **sync 비효율**: `sync_jobs()`가 매번 전체 ~2,600페이지를 목록 스캔한다. 신규 공고는 앞쪽 페이지에 몰려 있으므로 대부분의 스캔이 낭비(~22분).

init 중단 → sync로 재개하는 시나리오에서, sync에 조기 종료를 넣으면 앞쪽 페이지만 보고 멈춰 뒤쪽 갭을 못 채우는 충돌이 발생한다.

## 2. 해결: 역할 분리

| CLI 명령 | usecase 함수 | 역할 | store.clear | 스캔 범위 |
|----------|-------------|------|-------------|-----------|
| `init_scrap.py` | `collect_all_jobs()` | 완전 초기 수집 | O | 전체 페이지 |
| `resume_scrap.py` (신규) | `resume_collect()` | 중단 재개 | X | 전체 페이지 (기존 skip) |
| `sync_scrap.py` | `sync_jobs()` | 신규 공고 추가 | X | 조기 종료 |
| `validate_job.py` | `validate_all_jobs()` | 마감 검증/제거 | X | DB 내 전체 |

### 운영 시나리오

```
첫 실행:          init_scrap → 전체 수집
init 중단:        resume_scrap → 갭 메움 (전체 페이지 스캔, 기존 skip)
일상 동기화:       sync_scrap → 최신 페이지만 훑고 조기 종료
DB 초기화 필요 시: init_scrap → clear 후 처음부터
```

## 3. usecase 계층 변경

### 3.1 collect.py — 공유 엔진 추출

```python
def _collect_missing(scraper, store, existing_ids: set[str]) -> CollectResult:
    """전체 페이지를 순회하며 existing_ids에 없는 공고만 수집"""
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    collected = 0
    failed = 0

    for page in range(1, total_pages + 1):
        ids = scraper.fetch_listing_page(page)
        new_ids = [id for id in ids if id not in existing_ids]
        if not new_ids:
            continue
        for wanted_auth_no in new_ids:
            job = scraper.fetch_job_detail(wanted_auth_no)
            if job:
                store.add_job(job)
                existing_ids.add(wanted_auth_no)
                collected += 1
            else:
                failed += 1
        print(f"[{page}/{total_pages}] 신규: {collected}, 실패: {failed}")

    return CollectResult(total=total, collected=collected, failed=failed)

def collect_all_jobs(scraper, store) -> CollectResult:
    """완전 초기 수집 — DB 초기화 후 전체 수집"""
    store.clear()
    return _collect_missing(scraper, store, existing_ids=set())

def resume_collect(scraper, store) -> CollectResult:
    """중단 재개 — 기존 데이터 보존, 빠진 공고만 수집"""
    existing_ids = store.get_all_ids()
    print(f"[RESUME] 기존 {len(existing_ids)}건 보존, 빠진 공고 수집")
    return _collect_missing(scraper, store, existing_ids)
```

핵심: `_collect_missing()`이 공유 엔진. init과 resume의 차이는 clear 여부와 초기 existing_ids뿐.

### 3.2 sync.py — 조기 종료 추가

```python
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
        ids = scraper.fetch_listing_page(page)
        new_ids = [id for id in ids if id not in existing_ids]

        if not new_ids:
            consecutive_empty += 1
            if consecutive_empty >= early_stop:
                print(f"[STOP] 연속 {early_stop}페이지 신규 없음 → 스캔 중단")
                break
        else:
            consecutive_empty = 0
            for wanted_auth_no in new_ids:
                job = scraper.fetch_job_detail(wanted_auth_no)
                if job:
                    store.add_job(job)
                    existing_ids.add(wanted_auth_no)
                    new_count += 1
                else:
                    failed += 1

        print(f"[{page}] 신규: {len(new_ids)}, 누적: {new_count}")

    return SyncResult(scanned_pages=scanned_pages, new_count=new_count, failed=failed)
```

`early_stop=3`: 연속 3페이지(150건) 동안 신규가 없으면 중단. init 완료 후 일상 sync는 수십 초에 완료.

## 4. CLI 진입점

### 4.1 resume_scrap.py (신규)

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

### 4.2 기존 CLI — 변경 없음

`init_scrap.py`, `sync_scrap.py`, `validate_job.py`는 호출하는 함수 시그니처가 동일하므로 변경 불필요.

## 5. 변경 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `usecases/collect.py` | 수정 | `_collect_missing` 공유 엔진 추출, `resume_collect` 추가 |
| `usecases/sync.py` | 수정 | `early_stop` 조기 종료 로직 추가 |
| `resume_scrap.py` | 신규 | CLI 진입점 |
| `CLAUDE.md` | 수정 | CLI 명령 표, 프로젝트 구조에 `resume_scrap.py` 추가 |
