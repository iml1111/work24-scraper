# 공고 유형별 동적 파라미터 설계

## 배경

고용24 목록 페이지는 여러 출처(워크넷, 지자체, 산업인력공단, 인터넷 공고)의 채용공고를 혼합 반환한다. 각 공고의 상세 페이지 URL에는 출처별로 다른 `infoTypeCd`와 `infoTypeGroup` 파라미터가 포함되어 있다.

### 공고 유형별 파라미터

| ID 형식 | infoTypeCd | infoTypeGroup | 출처 |
|---------|-----------|---------------|------|
| K-prefix | VALIDATION | tb_workinfoworknet | 워크넷 |
| 숫자 (CJK) | CJK | tb_workinfogubun | 지자체 일자리 |
| 숫자 (CSI) | CSI | tb_workinfogubun | 산업인력공단 |
| 날짜형 (CIN) | CIN | tb_workinfogubun | 인터넷 공고 |

### 문제

기존 코드가 `infoTypeCd=VALIDATION, infoTypeGroup=tb_workinfoworknet`을 하드코딩하여 K-prefix(워크넷) 공고만 정상 조회되고 나머지 ~92%는 만료로 오판.

## 변경 범위

| 파일 | 변경 |
|------|------|
| `domain/models.py` | `JobRef` dataclass 추가 |
| `adapters/scraper.py` | `parse_listing_ids` → `parse_listing_refs` (list[JobRef] 반환), `fetch_listing_page` → list[JobRef] 반환, `fetch_job_detail(ref: JobRef)` 파라미터 동적 사용 |
| `usecases/collect.py` | JobRef 기반 순회 |
| `usecases/sync.py` | JobRef 기반 순회 |
| `tests/test_scraper_parse.py` | `parse_listing_refs` 테스트 |
| `tests/test_collect.py` | FakeScraper 인터페이스 변경 |
| `tests/test_sync.py` | FakeScraper 인터페이스 변경 |

변경 없음: `adapters/store.py`, `Job` 모델, CLI 스크립트, `validate.py`

## 설계

### 1. `JobRef` dataclass — `domain/models.py`

```python
@dataclass
class JobRef:
    wanted_auth_no: str
    info_type_cd: str
    info_type_group: str
```

### 2. 목록 파싱 변경 — `adapters/scraper.py`

`parse_listing_ids` → `parse_listing_refs`로 이름 변경. 반환값 `list[str]` → `list[JobRef]`.

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

`fetch_listing_page` 반환값도 `list[str]` → `list[JobRef]`.

### 3. 상세 조회 변경 — `adapters/scraper.py`

`fetch_job_detail(wanted_auth_no: str)` → `fetch_job_detail(ref: JobRef)`.

```python
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
        if self._is_blocked(resp):
            return (None, "blocked")
        if is_expired_page(resp.text):
            return (None, "expired")
        job = parse_job_detail(resp.text, ref)
        return (job, "ok")
    except requests.RequestException:
        return (None, "error")
```

### 3-1. `parse_job_detail` 시그니처 변경 — `adapters/scraper.py`

`parse_job_detail(html, wanted_auth_no: str)` → `parse_job_detail(html, ref: JobRef)`.

`detail_url` 생성 시 `ref`의 파라미터를 사용:

```python
def parse_job_detail(html: str, ref: JobRef) -> Job:
    ...
    detail_url = (
        f"{DETAIL_URL}?wantedAuthNo={ref.wanted_auth_no}"
        f"&infoTypeCd={ref.info_type_cd}&infoTypeGroup={ref.info_type_group}"
    )
    ...
    return Job(wanted_auth_no=ref.wanted_auth_no, ...)
```

### 4. usecase 레이어 변경 — `collect.py`, `sync.py`

`existing_ids`는 `set[str]`로 유지. `ref.wanted_auth_no`로 중복 체크.

```python
refs = scraper.fetch_listing_page(page)
new_refs = [ref for ref in refs if ref.wanted_auth_no not in existing_ids]

for ref in new_refs:
    job, status = scraper.fetch_job_detail(ref)
    if status == "ok":
        store.add_job(job)
        existing_ids.add(ref.wanted_auth_no)
        print(f"[{page}/{total_pages}] {ref.wanted_auth_no} {job.title} → 수집")
    elif status == "expired":
        ...
```

### 5. 테스트 변경

- `test_scraper_parse.py`: `parse_listing_refs` 반환값이 `list[JobRef]`인지, 각 항목에 올바른 파라미터가 포함되는지 테스트
- `test_collect.py`, `test_sync.py`: `FakeScraper.fetch_listing_page` → `list[JobRef]` 반환, `fetch_job_detail(ref: JobRef)` 인터페이스 변경

## 변경하지 않는 것

- `is_job_active` — `validate.py`에서 사용. 현재 K-prefix(워크넷) 공고만 DB에 있으므로 기존 하드코딩 파라미터 유지. 추후 DB에 다양한 유형이 쌓이면 별도 개선.
- `Job.detail_url` 필드 — 기존대로 `wanted_auth_no` 기반 URL 저장. 파라미터가 포함된 정확한 URL로 변경.
