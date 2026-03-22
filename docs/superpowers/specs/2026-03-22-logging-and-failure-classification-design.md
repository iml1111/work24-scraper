# 로깅 개선 및 실패 분류 설계

## 배경

`init_scrap.py --dry` 실행 시 500건 중 421건(84%)이 실패로 기록되었으나, 로그가 단순하여 원인 파악이 불가능했다.

### 진단 결과

- HTTP 에러나 봇 차단은 발생하지 않음 (0.3초 딜레이에서도 차단 없음)
- 실패의 원인은 **목록 페이지가 이미 만료된 공고 ID를 반환**하는 것
- 만료 페이지: ~1.3KB, `alert("해당 구인인증번호의 상세 내역이 없습니다")` 포함
- 정상 페이지: ~290KB, `div.tit_area` + `tab-panel` 6개 포함
- 현재 코드는 만료/차단/파싱에러를 모두 `failed`로 카운트하여 구분 불가

## 변경 범위

| 파일 | 변경 내용 |
|------|----------|
| `adapters/scraper.py` | `fetch_job_detail` 반환값 변경, 딜레이 상향 |
| `usecases/collect.py` | 분류별 카운터, 건별 로그 + 페이지 요약, `CollectResult` 필드 추가 |
| `usecases/sync.py` | `fetch_job_detail` 반환값 변경 반영, `SyncResult` 필드 추가 |
| `init_scrap.py` | 최종 출력 필드 변경 |
| `resume_scrap.py` | 최종 출력 필드 변경 |
| `sync_scrap.py` | 최종 출력 필드 변경 |

변경 없는 파일: `domain/models.py`, `adapters/store.py`, `usecases/validate.py`, `validate_job.py`

## 설계

### 1. 응답 분류 로직 — `adapters/scraper.py`

`fetch_job_detail`의 반환값을 `Job | None`에서 `tuple[Job | None, str]`로 변경.
status 값: `"ok"`, `"expired"`, `"blocked"`, `"error"`

```python
def fetch_job_detail(self, wanted_auth_no: str) -> tuple[Job | None, str]:
    try:
        resp = self._request_with_delay(
            "GET", DETAIL_URL,
            params={...},
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

`parse_job_detail` 내부의 `is_expired_page` 체크를 제거하여 순수 파싱만 담당하도록 변경.

### 2. 딜레이 상향 — `adapters/scraper.py`

```python
# 기존
delay_range: tuple[float, float] = (0.3, 1.5)

# 변경
delay_range: tuple[float, float] = (3.0, 7.0)
```

세션 로테이션 주기(`rotate_every=200`)는 현행 유지.

### 3. 건별 로그 + 페이지 요약 — `usecases/collect.py`

#### CollectResult 필드 변경

```python
@dataclass
class CollectResult:
    total: int
    collected: int
    expired: int
    blocked: int
    errors: int
```

#### 제어 흐름

```python
collected = 0
expired = 0
blocked = 0
errors = 0

for page in range(start_page, end_page + 1):
    ids = scraper.fetch_listing_page(page)
    new_ids = [id for id in ids if id not in existing_ids]
    if not new_ids:
        continue

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

    print(f"[{page}/{total_pages} 완료] 신규: {collected}, 만료: {expired}, 차단: {blocked}, 에러: {errors}")

return CollectResult(total=total, collected=collected, expired=expired, blocked=blocked, errors=errors)
```

#### 출력 예시

```
[1/2548] K163022603220001 사무보조원 모집 → 수집
[1/2548] 50575017 → 만료
[1/2548] 53391653 → 만료
[1/2548 완료] 신규: 4, 만료: 46, 차단: 0, 에러: 0
```

### 4. sync.py 반영 — `usecases/sync.py`

#### SyncResult 필드 변경

```python
@dataclass
class SyncResult:
    scanned_pages: int
    new_count: int
    expired: int
    blocked: int
    errors: int
```

#### 제어 흐름

```python
new_count = 0
expired = 0
blocked = 0
errors = 0

for page in range(1, total_pages + 1):
    ids = scraper.fetch_listing_page(page)
    new_ids = [id for id in ids if id not in existing_ids]

    if not new_ids:
        consecutive_empty += 1
        if consecutive_empty >= early_stop:
            break
    else:
        consecutive_empty = 0
        for wanted_auth_no in new_ids:
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

    print(f"[{page}] 신규: {len(new_ids)}, 누적: {new_count}")

return SyncResult(scanned_pages=scanned_pages, new_count=new_count, expired=expired, blocked=blocked, errors=errors)
```

### 5. CLI 출력 변경

`init_scrap.py`, `resume_scrap.py`, `sync_scrap.py`의 최종 출력:

```
=== 완료 ===
총 공고: 127364
수집 성공: 79
만료 스킵: 421
차단: 0
에러: 0
```

## 변경하지 않는 것

- `validate.py` — `is_job_active()`를 사용하며 `fetch_job_detail`을 호출하지 않음
- `domain/models.py` — Job 모델 변경 없음
- `adapters/store.py` — 저장 로직 변경 없음
- 만료 공고 ID 사전 필터링 — 하지 않음. 요청은 그대로 하되 분류만 정확하게
