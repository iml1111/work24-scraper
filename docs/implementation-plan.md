# work24-scraper 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 고용24 채용공고를 HTTP 스크래핑으로 수집/동기화/검증하는 CLI 기반 도구 구현

**Architecture:** adapters(HTTP 스크래퍼, JSON Store) → usecases(순수 로직) → CLI 진입점. 단방향 의존. models.py는 전 계층 공유.

**Tech Stack:** Python 3.12+, requests, beautifulsoup4, lxml, dataclasses, json

**Spec:** `docs/design-spec.md`
**Research:** `docs/research-site-analysis.md`

---

## File Structure

| 파일 | 역할 |
|------|------|
| `pyproject.toml` | 프로젝트 설정 및 의존성 |
| `models.py` | Job dataclass + 직렬화 헬퍼 |
| `adapters/__init__.py` | 패키지 초기화 |
| `adapters/store.py` | JsonJobStore — JSON 파일 CRUD |
| `adapters/scraper.py` | Work24Scraper — HTTP 요청 + HTML 파싱 |
| `usecases/__init__.py` | 패키지 초기화 |
| `usecases/collect.py` | collect_all_jobs — 전체 수집 |
| `usecases/sync.py` | sync_jobs — 증분 동기화 |
| `usecases/validate.py` | validate_all_jobs — 유효성 검증 |
| `init_scrap.py` | CLI 진입점: 초기 수집 |
| `sync_scrap.py` | CLI 진입점: 동기화 |
| `validate_job.py` | CLI 진입점: 검증 |
| `tests/test_models.py` | models 단위 테스트 |
| `tests/test_store.py` | JsonJobStore 단위 테스트 |
| `tests/test_scraper_parse.py` | HTML 파싱 로직 단위 테스트 |

---

### Task 1: 프로젝트 초기 설정

**Files:**
- Create: `pyproject.toml`
- Create: `adapters/__init__.py`
- Create: `usecases/__init__.py`
- Create: `data/.gitkeep`
- Modify: `.gitignore`
- Modify: `CLAUDE.md`

- [ ] **Step 1: pyproject.toml 생성**

```toml
[project]
name = "work24-scraper"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "requests",
    "beautifulsoup4",
    "lxml",
]

[project.optional-dependencies]
dev = [
    "pytest",
]
```

- [ ] **Step 2: 디렉토리 구조 생성**

```bash
mkdir -p adapters usecases data tests
touch adapters/__init__.py usecases/__init__.py data/.gitkeep tests/__init__.py
```

- [ ] **Step 3: .gitignore에 data/jobs.json 추가**

`.gitignore` 파일 끝에 추가:
```
# Scraped data
data/jobs.json
```

- [ ] **Step 4: CLAUDE.md 프로젝트 구조를 설계 문서 기준으로 갱신**

프로젝트 구조 섹션을 `docs/design-spec.md` 섹션 2의 구조로 교체.

- [ ] **Step 5: 의존성 설치 및 확인**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 6: 커밋**

```bash
git add pyproject.toml adapters/ usecases/ data/.gitkeep tests/__init__.py .gitignore CLAUDE.md
git commit -m "chore: 프로젝트 초기 구조 설정"
```

---

### Task 2: 데이터 모델 (`models.py`)

**Files:**
- Create: `models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_models.py
from models import Job, job_to_dict, job_from_dict

def make_sample_job() -> Job:
    return Job(
        wanted_auth_no="KF10882603180014",
        scraped_at="2026-03-18T18:00:00",
        title="[장기동] 재가요양보호사 모집",
        job_description="장기동 장기주공아파트 3등급 여자어르신 가사서비스",
        qualification="학력무관 | 자격면허: 요양보호사",
        experience="관계없음",
        preferences=None,
        location="대구광역시 달서구 용산로 88",
        detail_url="https://www.work24.go.kr/wk/a/b/1500/empDetailAuthView.do?wantedAuthNo=KF10882603180014&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet",
        hiring_process="면접",
        employment_conditions="기간의 정함이 없는 근로계약(시간제) | 시급 10,320원 이상 | 주 2일 근무 (주 6시간) | 14:00~17:00",
        company="해맑은노인복지센터 | 사회복지 상담서비스 제공업 | 52명",
        benefits=None,
        application_method="방문 | 이력서 | 채용시까지 (마감: 2026-04-01)",
        deadline_date="2026-04-01",
        registration_date="2026-03-18",
    )

def test_job_to_dict_roundtrip():
    job = make_sample_job()
    d = job_to_dict(job)
    restored = job_from_dict(d)
    assert restored == job

def test_job_to_dict_contains_all_fields():
    job = make_sample_job()
    d = job_to_dict(job)
    assert d["wanted_auth_no"] == "KF10882603180014"
    assert d["title"] == "[장기동] 재가요양보호사 모집"
    assert d["preferences"] is None

def test_job_from_dict_with_none_fields():
    job = make_sample_job()
    d = job_to_dict(job)
    d["preferences"] = None
    d["benefits"] = None
    restored = job_from_dict(d)
    assert restored.preferences is None
    assert restored.benefits is None
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_models.py -v
```
Expected: FAIL — `models` 모듈 없음

- [ ] **Step 3: models.py 구현**

```python
# models.py
from dataclasses import dataclass, asdict

@dataclass
class Job:
    wanted_auth_no: str
    scraped_at: str
    title: str
    job_description: str
    qualification: str
    experience: str
    preferences: str | None
    location: str
    detail_url: str
    hiring_process: str
    employment_conditions: str
    company: str
    benefits: str | None
    application_method: str
    deadline_date: str
    registration_date: str

def job_to_dict(job: Job) -> dict:
    return asdict(job)

def job_from_dict(d: dict) -> Job:
    return Job(**d)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_models.py -v
```
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add models.py tests/test_models.py
git commit -m "feat: Job 데이터 모델 및 직렬화 구현"
```

---

### Task 3: JSON Store 어댑터 (`adapters/store.py`)

**Files:**
- Create: `adapters/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_store.py
import json
import os
import pytest
from adapters.store import JsonJobStore
from models import Job

def make_job(wanted_auth_no: str = "TEST001") -> Job:
    return Job(
        wanted_auth_no=wanted_auth_no,
        scraped_at="2026-03-18T18:00:00",
        title="테스트 공고",
        job_description="테스트 직무내용",
        qualification="학력무관",
        experience="경력무관",
        preferences=None,
        location="서울특별시",
        detail_url="https://example.com",
        hiring_process="면접",
        employment_conditions="월급 300만원",
        company="테스트회사",
        benefits=None,
        application_method="이메일",
        deadline_date="2026-04-01",
        registration_date="2026-03-18",
    )

@pytest.fixture
def store(tmp_path):
    path = str(tmp_path / "jobs.json")
    return JsonJobStore(path=path)

def test_clear_creates_empty_db(store):
    store.clear()
    assert store.load_all() == {}

def test_add_and_load(store):
    store.clear()
    job = make_job("A001")
    store.add_job(job)
    jobs = store.load_all()
    assert "A001" in jobs
    assert jobs["A001"].title == "테스트 공고"

def test_get_all_ids(store):
    store.clear()
    store.add_job(make_job("A001"))
    store.add_job(make_job("A002"))
    ids = store.get_all_ids()
    assert ids == {"A001", "A002"}

def test_remove_job(store):
    store.clear()
    store.add_job(make_job("A001"))
    store.add_job(make_job("A002"))
    store.remove_job("A001")
    assert "A001" not in store.get_all_ids()
    assert "A002" in store.get_all_ids()

def test_load_nonexistent_file(tmp_path):
    path = str(tmp_path / "nonexistent.json")
    s = JsonJobStore(path=path)
    assert s.load_all() == {}

def test_atomic_write(store):
    store.clear()
    store.add_job(make_job("A001"))
    # 파일이 정상 JSON인지 확인
    with open(store.path) as f:
        data = json.load(f)
    assert "A001" in data
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_store.py -v
```
Expected: FAIL

- [ ] **Step 3: store.py 구현**

```python
# adapters/store.py
import json
import os
import tempfile
from models import Job, job_to_dict, job_from_dict

class JsonJobStore:
    def __init__(self, path: str = "data/jobs.json"):
        self.path = path

    def load_all(self) -> dict[str, Job]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: job_from_dict(v) for k, v in raw.items()}

    def save_all(self, jobs: dict[str, Job]) -> None:
        raw = {k: job_to_dict(v) for k, v in jobs.items()}
        dir_path = os.path.dirname(self.path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        except:
            os.unlink(tmp_path)
            raise

    def get_all_ids(self) -> set[str]:
        if not os.path.exists(self.path):
            return set()
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return set(raw.keys())

    def add_job(self, job: Job) -> None:
        jobs = self.load_all()
        jobs[job.wanted_auth_no] = job
        self.save_all(jobs)

    def remove_job(self, wanted_auth_no: str) -> None:
        jobs = self.load_all()
        jobs.pop(wanted_auth_no, None)
        self.save_all(jobs)

    def clear(self) -> None:
        self.save_all({})
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_store.py -v
```
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add adapters/store.py tests/test_store.py
git commit -m "feat: JsonJobStore JSON 파일 기반 CRUD 구현"
```

---

### Task 4: HTTP 스크래퍼 — 목록 파싱 (`adapters/scraper.py` part 1)

**Files:**
- Create: `adapters/scraper.py`
- Create: `tests/test_scraper_parse.py`
- Create: `tests/fixtures/` (테스트용 HTML 파일)

이 태스크에서는 실제 HTTP 요청 없이 HTML 파싱 로직만 구현/테스트.

- [ ] **Step 1: 테스트용 목록 HTML fixture 저장**

실제 사이트에서 목록 페이지 HTML 일부를 저장:
```bash
curl -s -L -X POST 'https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchListInPost.do' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  -d 'sortField=DATE&sortOrderBy=DESC&pageIndex=1&resultCnt=10' \
  -o tests/fixtures/listing_page.html
```

- [ ] **Step 2: 목록 파싱 테스트 작성**

```python
# tests/test_scraper_parse.py
import os
from adapters.scraper import parse_listing_ids, parse_total_count

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as f:
        return f.read()

def test_parse_listing_ids():
    html = read_fixture("listing_page.html")
    ids = parse_listing_ids(html)
    assert len(ids) == 10
    assert all(isinstance(id, str) for id in ids)
    assert all(len(id) > 5 for id in ids)

def test_parse_total_count():
    html = read_fixture("listing_page.html")
    count = parse_total_count(html)
    assert isinstance(count, int)
    assert count > 100000
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
pytest tests/test_scraper_parse.py -v
```
Expected: FAIL

- [ ] **Step 4: 파싱 함수 구현**

```python
# adapters/scraper.py
import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.work24.go.kr"
LISTING_URL = f"{BASE_URL}/wk/a/b/1200/retriveDtlEmpSrchListInPost.do"
DETAIL_URL = f"{BASE_URL}/wk/a/b/1500/empDetailAuthView.do"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_DELAY = 0.5

def parse_listing_ids(html: str) -> list[str]:
    """HTML에서 wantedAuthNo 목록 추출"""
    pattern = r'wantedAuthNo=([^&"]+)'
    # empDetailAuthView 링크에서만 추출 (중복 제거, 순서 유지)
    matches = re.findall(r'empDetailAuthView\.do\?wantedAuthNo=([^&"]+)', html)
    seen = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result

def parse_total_count(html: str) -> int:
    """HTML에서 totalRecordCount 추출"""
    match = re.search(r'totalRecordCount\s*:\s*(\d+)', html)
    if not match:
        raise ValueError("totalRecordCount not found in HTML")
    return int(match.group(1))
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_scraper_parse.py -v
```
Expected: 2 passed

- [ ] **Step 6: 커밋**

```bash
git add adapters/scraper.py tests/test_scraper_parse.py tests/fixtures/
git commit -m "feat: 목록 페이지 HTML 파싱 (wantedAuthNo, totalRecordCount)"
```

---

### Task 5: HTTP 스크래퍼 — 상세 파싱 (`adapters/scraper.py` part 2)

**Files:**
- Modify: `adapters/scraper.py`
- Modify: `tests/test_scraper_parse.py`
- Create: `tests/fixtures/detail_page.html`
- Create: `tests/fixtures/expired_page.html`

- [ ] **Step 1: 테스트용 상세/만료 HTML fixture 저장**

```bash
# 상세 페이지 (유효한 공고 하나의 wantedAuthNo 사용)
curl -s -L \
  'https://www.work24.go.kr/wk/a/b/1500/empDetailAuthView.do?wantedAuthNo=K180632603180003&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  -o tests/fixtures/detail_page.html

# 만료 페이지 (가짜 ID)
curl -s -L \
  'https://www.work24.go.kr/wk/a/b/1500/empDetailAuthView.do?wantedAuthNo=FAKE000000000000&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' \
  -o tests/fixtures/expired_page.html
```

- [ ] **Step 2: 상세 파싱 테스트 작성**

```python
# tests/test_scraper_parse.py 에 추가
from adapters.scraper import parse_job_detail, is_expired_page

def test_parse_job_detail():
    html = read_fixture("detail_page.html")
    job = parse_job_detail(html, "K180632603180003")
    assert job is not None
    assert job.wanted_auth_no == "K180632603180003"
    assert len(job.title) > 0
    assert len(job.company) > 0
    assert len(job.location) > 0
    assert len(job.job_description) > 0
    assert len(job.deadline_date) > 0
    assert len(job.registration_date) > 0

def test_parse_job_detail_has_all_fields():
    html = read_fixture("detail_page.html")
    job = parse_job_detail(html, "K180632603180003")
    assert job.qualification  # 지원 자격
    assert job.experience     # 연차
    assert job.hiring_process # 채용 프로세스
    assert job.employment_conditions  # 채용 조건
    assert job.application_method     # 지원 방법
    assert job.detail_url     # 공고 링크

def test_is_expired_page():
    html = read_fixture("expired_page.html")
    assert is_expired_page(html) is True

def test_is_not_expired_page():
    html = read_fixture("detail_page.html")
    assert is_expired_page(html) is False
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
pytest tests/test_scraper_parse.py -v
```
Expected: 새 테스트 4개 FAIL

- [ ] **Step 4: 상세 파싱 구현**

`adapters/scraper.py`에 추가. 상세 페이지 HTML 구조 기반 파싱:

```python
from datetime import datetime, timezone
from models import Job

def is_expired_page(html: str) -> bool:
    """만료된 공고 페이지인지 판별"""
    return "구인정보를 확인할 수 없습니다" in html

def parse_job_detail(html: str, wanted_auth_no: str) -> Job | None:
    """상세 페이지 HTML → Job 객체. 만료 시 None."""
    if is_expired_page(html):
        return None

    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()
    detail_url = f"{DETAIL_URL}?wantedAuthNo={wanted_auth_no}&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet"

    # 제목 + 회사명 (상단 영역)
    title = _text(soup, "strong.t3_sb, div strong") or ""
    company_name = _text(soup, "p strong, strong.b1_sb") or ""

    # 테이블 기반 파싱 — rowheader로 필드 탐색
    tables = _parse_tables(soup)

    # 직무내용
    job_desc_el = soup.select_one("strong:-soup-contains('직무내용')")
    job_description = ""
    if job_desc_el:
        parent = job_desc_el.parent
        if parent:
            job_description = parent.get_text(separator="\n", strip=True)
            job_description = job_description.replace("직무내용", "", 1).strip()

    # 필드 조합
    qualification_parts = [tables.get("학력", ""), tables.get("자격 면허", "")]
    qualification = " | ".join(p for p in qualification_parts if p and p != "-")

    experience = tables.get("경력", "경력무관")

    pref_parts = [tables.get("전공", ""), tables.get("외국어 능력", ""),
                  tables.get("컴퓨터 활용 능력", ""), tables.get("우대조건", ""),
                  tables.get("기타 우대사항", "")]
    preferences = " | ".join(p for p in pref_parts if p and p != "-") or None

    location = tables.get("근무 예정지", "")

    # 전형방법
    process_el = soup.select_one("strong:-soup-contains('전형방법')")
    hiring_parts = []
    if process_el:
        section = process_el.find_parent()
        if section:
            for li in section.find_all("li"):
                text = li.get_text(strip=True)
                if "미제공" not in text and text:
                    hiring_parts.append(text)
    hiring_process = ", ".join(hiring_parts) or tables.get("전형방법", "")

    # 채용 조건 통합
    cond_parts = [tables.get("고용 형태", ""), tables.get("임금 조건", ""),
                  tables.get("근무 형태", ""), tables.get("근무 시간", "")]
    employment_conditions = " | ".join(p for p in cond_parts if p and p != "-")

    # 회사 정보 통합
    company_items = soup.select("strong:-soup-contains('기업정보') ~ div li, strong:-soup-contains('기업정보') ~ div .item")
    company_parts = [company_name]
    for item in company_items:
        text = item.get_text(strip=True)
        if text and text != "-":
            company_parts.append(text)
    company = " | ".join(dict.fromkeys(company_parts))  # 중복 제거

    # 복리후생
    benefits_el = soup.select_one("strong:-soup-contains('복리후생')")
    benefit_parts = []
    if benefits_el:
        section = benefits_el.find_parent()
        if section:
            for li in section.find_all("li"):
                text = li.get_text(strip=True)
                if "미제공" not in text and text:
                    benefit_parts.append(text)
    benefits = ", ".join(benefit_parts) or None

    # 지원 방법
    app_parts = [tables.get("접수 방법", ""), tables.get("제출 서류", "")]
    deadline_info = _text(soup, "strong:-soup-contains('접수 마감일') ~ p") or ""
    if deadline_info:
        app_parts.append(deadline_info)
    application_method = " | ".join(p for p in app_parts if p and p != "-")

    # 날짜
    reg_text = tables.get("채용공고 등록일시", "")
    registration_date = reg_text[:10] if len(reg_text) >= 10 else ""
    registration_date = registration_date.replace(".", "-")

    deadline_match = re.search(r'마감일\s*:\s*(\d{4}-\d{2}-\d{2})', html)
    deadline_date = deadline_match.group(1) if deadline_match else ""
    if not deadline_date:
        # 2099 = 채용시까지
        deadline_match2 = re.search(r"var\s+date\s*=\s*'(\d{4}-\d{2}-\d{2})'", html)
        deadline_date = deadline_match2.group(1) if deadline_match2 else ""

    return Job(
        wanted_auth_no=wanted_auth_no,
        scraped_at=now,
        title=title,
        job_description=job_description,
        qualification=qualification,
        experience=experience,
        preferences=preferences,
        location=location,
        detail_url=detail_url,
        hiring_process=hiring_process,
        employment_conditions=employment_conditions,
        company=company,
        benefits=benefits,
        application_method=application_method,
        deadline_date=deadline_date,
        registration_date=registration_date,
    )


def _parse_tables(soup: BeautifulSoup) -> dict[str, str]:
    """모든 테이블의 rowheader→cell 매핑을 dict로 추출"""
    result = {}
    for th in soup.find_all(["th", "td"], class_=lambda c: c and "rowheader" in str(c)):
        key = th.get_text(strip=True).replace("도움말", "").strip()
        td = th.find_next_sibling("td")
        if td:
            result[key] = td.get_text(separator=" ", strip=True)
    # role="rowheader" 패턴도 시도
    for th in soup.find_all(attrs={"role": "rowheader"}):
        key = th.get_text(strip=True).replace("도움말", "").strip()
        td = th.find_next_sibling("td")
        if td:
            result[key] = td.get_text(separator=" ", strip=True)
    # 일반 th-td 패턴
    for th in soup.find_all("th"):
        key = th.get_text(strip=True).replace("도움말", "").strip()
        if key and key not in result:
            td = th.find_next_sibling("td")
            if td:
                result[key] = td.get_text(separator=" ", strip=True)
    return result


def _text(soup: BeautifulSoup, selector: str) -> str | None:
    """CSS 셀렉터로 첫 번째 매칭 요소의 텍스트 반환"""
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else None
```

> **참고:** 상세 페이지의 HTML 구조는 실제 fixture 기반으로 파싱 로직을 조정해야 할 수 있음. fixture를 저장한 뒤 테스트를 돌려가며 셀렉터를 튜닝하는 과정이 필요.

- [ ] **Step 5: 테스트 통과 확인 및 파싱 셀렉터 조정**

```bash
pytest tests/test_scraper_parse.py -v
```

실패하는 필드가 있으면 fixture HTML을 직접 확인하여 셀렉터 수정.
핵심 검증: `title`, `company`, `location`, `job_description`, `deadline_date`, `registration_date`가 비어있지 않아야 함.

- [ ] **Step 6: 커밋**

```bash
git add adapters/scraper.py tests/test_scraper_parse.py tests/fixtures/
git commit -m "feat: 상세 페이지 HTML 파싱 및 만료 판별 구현"
```

---

### Task 6: HTTP 스크래퍼 — HTTP 요청 클래스 (`adapters/scraper.py` part 3)

**Files:**
- Modify: `adapters/scraper.py`

파싱 함수들을 감싸는 `Work24Scraper` 클래스. 실제 HTTP 요청 담당.

- [ ] **Step 1: Work24Scraper 클래스 구현**

`adapters/scraper.py`에 추가:

```python
class Work24Scraper:
    def __init__(self, delay: float = REQUEST_DELAY):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _request_with_delay(self, method: str, url: str, **kwargs) -> requests.Response:
        time.sleep(self.delay)
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    def get_total_count(self) -> int:
        resp = self._request_with_delay(
            "POST", LISTING_URL,
            data={"sortField": "DATE", "sortOrderBy": "DESC", "pageIndex": 1, "resultCnt": 10},
            allow_redirects=True,
        )
        return parse_total_count(resp.text)

    def fetch_listing_page(self, page: int, per_page: int = 50) -> list[str]:
        resp = self._request_with_delay(
            "POST", LISTING_URL,
            data={"sortField": "DATE", "sortOrderBy": "DESC", "pageIndex": page, "resultCnt": per_page},
            allow_redirects=True,
        )
        return parse_listing_ids(resp.text)

    def fetch_job_detail(self, wanted_auth_no: str) -> Job | None:
        try:
            resp = self._request_with_delay(
                "GET", DETAIL_URL,
                params={"wantedAuthNo": wanted_auth_no, "infoTypeCd": "VALIDATION", "infoTypeGroup": "tb_workinfoworknet"},
            )
            return parse_job_detail(resp.text, wanted_auth_no)
        except requests.RequestException as e:
            print(f"[ERROR] 상세 조회 실패 ({wanted_auth_no}): {e}")
            return None

    def is_job_active(self, wanted_auth_no: str) -> bool:
        try:
            resp = self._request_with_delay(
                "GET", DETAIL_URL,
                params={"wantedAuthNo": wanted_auth_no, "infoTypeCd": "VALIDATION", "infoTypeGroup": "tb_workinfoworknet"},
            )
            return not is_expired_page(resp.text)
        except requests.RequestException:
            return False
```

- [ ] **Step 2: 스모크 테스트 (실제 서버 1회 호출)**

```bash
python -c "
from adapters.scraper import Work24Scraper
s = Work24Scraper()
print('Total:', s.get_total_count())
ids = s.fetch_listing_page(1, per_page=10)
print('Page 1 IDs:', ids[:3], '...')
job = s.fetch_job_detail(ids[0])
print('Job title:', job.title if job else 'None')
print('Active:', s.is_job_active(ids[0]))
print('Expired:', s.is_job_active('FAKE000000000000'))
"
```

Expected:
- Total: 130000+
- IDs: 3개 이상
- Job title: 비어있지 않은 문자열
- Active: True
- Expired: False

- [ ] **Step 3: 커밋**

```bash
git add adapters/scraper.py
git commit -m "feat: Work24Scraper HTTP 요청 클래스 구현"
```

---

### Task 7: Usecase 계층 (`usecases/`)

**Files:**
- Create: `usecases/collect.py`
- Create: `usecases/sync.py`
- Create: `usecases/validate.py`

- [ ] **Step 1: collect.py 구현**

```python
# usecases/collect.py
from dataclasses import dataclass
from math import ceil

@dataclass
class CollectResult:
    total: int
    collected: int
    failed: int

def collect_all_jobs(scraper, store) -> CollectResult:
    store.clear()
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    collected = 0
    failed = 0

    for page in range(1, total_pages + 1):
        try:
            ids = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            failed += len(ids) if 'ids' in dir() else 50
            continue

        for wanted_auth_no in ids:
            try:
                job = scraper.fetch_job_detail(wanted_auth_no)
                if job:
                    store.add_job(job)
                    collected += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[ERROR] 상세 조회 실패 ({wanted_auth_no}): {e}")
                failed += 1

        print(f"[{page}/{total_pages}] 수집: {collected}, 실패: {failed}")

    return CollectResult(total=total, collected=collected, failed=failed)
```

- [ ] **Step 2: sync.py 구현**

```python
# usecases/sync.py
from dataclasses import dataclass
from math import ceil

@dataclass
class SyncResult:
    scanned_pages: int
    new_count: int
    failed: int

def sync_jobs(scraper, store) -> SyncResult:
    existing_ids = store.get_all_ids()
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    new_count = 0
    failed = 0

    for page in range(1, total_pages + 1):
        try:
            ids = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            continue

        new_ids = [id for id in ids if id not in existing_ids]

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

        page_new = len(new_ids)
        print(f"[{page}/{total_pages}] 이 페이지 신규: {page_new}, 누적 신규: {new_count}")

    return SyncResult(scanned_pages=total_pages, new_count=new_count, failed=failed)
```

- [ ] **Step 3: validate.py 구현**

```python
# usecases/validate.py
from dataclasses import dataclass

@dataclass
class ValidateResult:
    total_checked: int
    removed: int
    still_active: int

def validate_all_jobs(scraper, store) -> ValidateResult:
    jobs = store.load_all()
    total = len(jobs)
    removed = 0

    for i, wanted_auth_no in enumerate(list(jobs.keys()), 1):
        try:
            if not scraper.is_job_active(wanted_auth_no):
                store.remove_job(wanted_auth_no)
                removed += 1
        except Exception as e:
            print(f"[ERROR] 검증 실패 ({wanted_auth_no}): {e}")

        if i % 100 == 0 or i == total:
            print(f"[{i}/{total}] 제거: {removed}, 유효: {i - removed}")

    return ValidateResult(total_checked=total, removed=removed, still_active=total - removed)
```

- [ ] **Step 4: 커밋**

```bash
git add usecases/collect.py usecases/sync.py usecases/validate.py
git commit -m "feat: usecase 계층 구현 (collect, sync, validate)"
```

---

### Task 8: CLI 진입점 스크립트

**Files:**
- Create: `init_scrap.py`
- Create: `sync_scrap.py`
- Create: `validate_job.py`

- [ ] **Step 1: init_scrap.py 구현**

```python
# init_scrap.py
from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.collect import collect_all_jobs

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 고용24 전체 채용공고 수집 시작 ===")
    result = collect_all_jobs(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"총 공고: {result.total}")
    print(f"수집 성공: {result.collected}")
    print(f"수집 실패: {result.failed}")
```

- [ ] **Step 2: sync_scrap.py 구현**

```python
# sync_scrap.py
from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.sync import sync_jobs

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 고용24 신규 채용공고 동기화 시작 ===")
    result = sync_jobs(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"스캔 페이지: {result.scanned_pages}")
    print(f"신규 추가: {result.new_count}")
    print(f"실패: {result.failed}")
```

- [ ] **Step 3: validate_job.py 구현**

```python
# validate_job.py
from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.validate import validate_all_jobs

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 채용공고 유효성 검증 시작 ===")
    result = validate_all_jobs(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"검증 건수: {result.total_checked}")
    print(f"제거 (마감): {result.removed}")
    print(f"유효 (채용중): {result.still_active}")
```

- [ ] **Step 4: 소규모 통합 테스트**

init_scrap을 1페이지만 수집하도록 수동 테스트:

```bash
python -c "
from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from models import job_to_dict
import json

scraper = Work24Scraper()
store = JsonJobStore()
store.clear()

ids = scraper.fetch_listing_page(1, per_page=5)
print(f'IDs: {ids}')
for id in ids[:2]:
    job = scraper.fetch_job_detail(id)
    if job:
        store.add_job(job)
        print(f'Saved: {job.title}')

jobs = store.load_all()
print(f'DB에 {len(jobs)}건 저장됨')
print(json.dumps(job_to_dict(list(jobs.values())[0]), ensure_ascii=False, indent=2))
"
```

- [ ] **Step 5: 커밋**

```bash
git add init_scrap.py sync_scrap.py validate_job.py
git commit -m "feat: CLI 진입점 스크립트 (init_scrap, sync_scrap, validate_job)"
```

---

### Task 9: 최종 검증

- [ ] **Step 1: 전체 테스트 실행**

```bash
pytest tests/ -v
```
Expected: 모든 테스트 통과

- [ ] **Step 2: init_scrap 소규모 실행 테스트**

코드에서 임시로 `total_pages`를 1로 제한하여 실행하거나, 첫 페이지만 테스트:

```bash
python init_scrap.py
# Ctrl+C로 조기 종료 후 data/jobs.json 확인
```

- [ ] **Step 3: sync_scrap 실행 테스트**

```bash
python sync_scrap.py
# 이미 수집된 공고는 스킵하고 신규만 추가되는지 확인
```

- [ ] **Step 4: validate_job 실행 테스트**

```bash
python validate_job.py
# 만료 공고가 제거되는지 확인
```

- [ ] **Step 5: 최종 커밋**

```bash
git add -A
git commit -m "chore: 최종 검증 완료"
```
