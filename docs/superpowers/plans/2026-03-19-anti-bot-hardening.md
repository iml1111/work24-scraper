# 봇 탐지 우회 — 요청 패턴 종합 강화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `adapters/scraper.py`의 Work24Scraper에 봇 탐지 우회를 위한 요청 패턴 자연화 및 복원력 강화를 적용한다.

**Architecture:** 모든 변경은 `adapters/scraper.py` 내 `Work24Scraper` 클래스에 한정. 기존 모듈 상수(`USER_AGENT`, `REQUEST_DELAY`)를 풀/범위로 교체하고, `__init__`/`_request_with_delay`를 재구성하여 UA 로테이션, 랜덤 딜레이, 세션 로테이션, 지수 백오프, 차단 감지를 통합한다. public 메서드 시그니처는 변경하지 않아 usecase/CLI 계층 수정 불필요.

**Tech Stack:** Python 3.12+, requests, random (stdlib)

**Spec:** `docs/superpowers/specs/2026-03-19-anti-bot-design.md`

---

## 변경 파일 목록

| 파일 | 작업 |
|------|------|
| `adapters/scraper.py` | 수정 — 모듈 상수 교체, Work24Scraper 클래스 전면 재구성 |
| `tests/test_scraper_stealth.py` | 생성 — `_is_blocked()` 단위 테스트 |

기존 테스트(`tests/test_collect.py`, `tests/test_sync.py` 등)는 FakeScraper를 사용하므로 영향 없음.

---

### Task 1: UA 풀 + 브라우저 헤더 + `_create_session()`

**Files:**
- Modify: `adapters/scraper.py:1-18` (모듈 상수), `adapters/scraper.py:343-347` (`__init__`)

기존 단일 `USER_AGENT` 상수와 `REQUEST_DELAY`를 제거하고, UA 풀 + 브라우저 헤더 + Referer 상수 + 차단 마커를 추가한다. `_create_session()` 메서드를 만들어 세션 생성 로직을 분리한다.

- [ ] **Step 1: 모듈 상수 교체**

`adapters/scraper.py` 상단의 상수를 교체한다:

```python
import random
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from models import Job

BASE_URL = "https://www.work24.go.kr"
LISTING_URL = f"{BASE_URL}/wk/a/b/1200/retriveDtlEmpSrchListInPost.do"
DETAIL_URL = f"{BASE_URL}/wk/a/b/1500/empDetailAuthView.do"
LISTING_REFERER = f"{BASE_URL}/wk/a/b/1200/retriveDtlEmpSrchList.do"

USER_AGENTS = [
    # Chrome (Mac)
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    # Chrome (Windows)
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    # Chrome (Mac, newer)
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    # Firefox (Windows)
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
        "Gecko/20100101 Firefox/122.0"
    ),
    # Firefox (Mac)
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    ),
    # Safari (Mac)
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.2 Safari/605.1.15"
    ),
]

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

_EXPIRED_MARKERS = [
    "구인정보를 확인할 수 없습니다",
    "해당 구인인증번호의 상세 내역이 없습니다",
]

_BLOCKED_MARKERS = [
    "captcha",
    "보안문자",
    "자동화된 요청",
    "비정상적인 접근",
]
```

주의: 기존 `USER_AGENT` (단수), `REQUEST_DELAY` 상수는 삭제한다.

- [ ] **Step 2: `_create_session()` 메서드 추가 + `__init__` 변경**

`Work24Scraper` 클래스를 수정한다:

```python
class Work24Scraper:
    def __init__(
        self,
        delay_range: tuple[float, float] = (0.3, 1.5),
        rotate_every: int = 200,
    ):
        self.delay_range = delay_range
        self.rotate_every = rotate_every
        self._request_count = 0
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """UA 랜덤 선택 + 브라우저 헤더로 새 세션 생성"""
        session = requests.Session()
        ua = random.choice(USER_AGENTS)
        session.headers.update({"User-Agent": ua, **BROWSER_HEADERS})
        return session
```

- [ ] **Step 3: 기존 23개 테스트가 통과하는지 확인**

Run: `python -m pytest -q`
Expected: 23 passed (usecase 테스트는 FakeScraper 사용, 영향 없음)

- [ ] **Step 4: Commit**

```bash
git add adapters/scraper.py
git commit -m "feat: UA 풀 + 브라우저 헤더 + _create_session()"
```

---

### Task 2: 랜덤 딜레이 + Referer + 세션 로테이션 + `_request_with_delay` 재구성

**Files:**
- Modify: `adapters/scraper.py` — `_request_with_delay`, `_rotate_session` 추가

기존 `_request_with_delay`를 재구성하여 랜덤 딜레이, Referer 헤더, 세션 로테이션을 통합한다.

- [ ] **Step 1: `_rotate_session()` 메서드 추가**

```python
    def _rotate_session(self) -> None:
        """세션 교체 — 새 UA + 헤더로 재생성"""
        self.session.close()
        self.session = self._create_session()
        self._request_count = 0
        print(f"[SESSION] 세션 갱신 (요청 {self.rotate_every}건 도달)")
```

- [ ] **Step 2: `_request_with_delay` 재구성**

기존 코드:
```python
    def _request_with_delay(self, method: str, url: str, **kwargs) -> requests.Response:
        time.sleep(self.delay)
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp
```

변경 후:
```python
    def _request_with_delay(self, method: str, url: str, **kwargs) -> requests.Response:
        # 세션 로테이션
        self._request_count += 1
        if self._request_count >= self.rotate_every:
            self._rotate_session()

        # Referer 설정
        headers = kwargs.pop("headers", {})
        headers.setdefault("Referer", LISTING_REFERER)
        kwargs["headers"] = headers

        # 랜덤 딜레이
        time.sleep(random.uniform(*self.delay_range))

        # 요청 실행 + 지수 백오프 재시도
        resp = self._request_with_retry(method, url, **kwargs)

        # 차단 신호 감지
        if self._is_blocked(resp):
            resp = self._handle_blocked(method, url, **kwargs)

        return resp
```

주의: 이 시점에서 `_request_with_retry`와 `_is_blocked`, `_handle_blocked`는 아직 없으므로, 임시로 다음과 같이 구현하여 기존 동작을 유지한다:

```python
    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    def _is_blocked(self, resp: requests.Response) -> bool:
        return False

    def _handle_blocked(self, method: str, url: str, **kwargs) -> requests.Response:
        raise requests.RequestException("차단 감지")
```

- [ ] **Step 3: 기존 23개 테스트 통과 확인**

Run: `python -m pytest -q`
Expected: 23 passed

- [ ] **Step 4: Commit**

```bash
git add adapters/scraper.py
git commit -m "feat: 랜덤 딜레이 + Referer + 세션 로테이션"
```

---

### Task 3: 지수 백오프 재시도

**Files:**
- Modify: `adapters/scraper.py` — `_request_with_retry` 실제 구현

Task 2에서 만든 stub `_request_with_retry`를 실제 지수 백오프 로직으로 교체한다.

- [ ] **Step 1: `_request_with_retry` 실제 구현**

기존 stub을 교체:

```python
    def _request_with_retry(self, method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
        """요청 실행 + 429/5xx 시 지수 백오프 재시도"""
        for attempt in range(max_retries + 1):
            resp = self.session.request(method, url, **kwargs)

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < max_retries:
                    delay = (2 ** attempt) * 2
                    print(f"[RETRY] HTTP {resp.status_code}, {delay}초 후 재시도 ({attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                # 최대 재시도 초과
                resp.raise_for_status()

            # 정상 응답 (4xx 중 429 외는 즉시 raise)
            if resp.status_code >= 400:
                resp.raise_for_status()

            return resp

        # unreachable, but for type checker
        resp.raise_for_status()
        return resp
```

- [ ] **Step 2: 기존 23개 테스트 통과 확인**

Run: `python -m pytest -q`
Expected: 23 passed

- [ ] **Step 3: Commit**

```bash
git add adapters/scraper.py
git commit -m "feat: 지수 백오프 재시도 (429/5xx)"
```

---

### Task 4: 차단 신호 감지 + 테스트

**Files:**
- Modify: `adapters/scraper.py` — `_is_blocked`, `_handle_blocked` 실제 구현
- Create: `tests/test_scraper_stealth.py` — `_is_blocked` 단위 테스트

Task 2에서 만든 stub `_is_blocked`, `_handle_blocked`를 실제 로직으로 교체한다.

- [ ] **Step 1: 테스트 작성**

`tests/test_scraper_stealth.py` 생성:

```python
from adapters.scraper import _BLOCKED_MARKERS, Work24Scraper


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_is_blocked_detects_captcha():
    """차단 마커가 포함된 응답을 감지"""
    scraper = Work24Scraper()
    for marker in _BLOCKED_MARKERS:
        resp = FakeResponse(text=f"<html>{marker}</html>")
        assert scraper._is_blocked(resp) is True


def test_is_blocked_normal_page():
    """정상 응답은 차단으로 판단하지 않음"""
    scraper = Work24Scraper()
    resp = FakeResponse(text="<html><body>정상 채용공고 페이지</body></html>")
    assert scraper._is_blocked(resp) is False


def test_is_blocked_expired_page_not_blocked():
    """만료 공고 페이지는 차단이 아님"""
    scraper = Work24Scraper()
    resp = FakeResponse(text='<script>alert("구인정보를 확인할 수 없습니다")</script>')
    assert scraper._is_blocked(resp) is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_scraper_stealth.py -v`
Expected: FAIL — `_is_blocked`가 항상 `False` 반환하는 stub이므로 `test_is_blocked_detects_captcha` 실패

- [ ] **Step 3: `_is_blocked`, `_handle_blocked` 실제 구현**

기존 stub을 교체:

```python
    def _is_blocked(self, resp: requests.Response) -> bool:
        """응답 본문에서 차단 신호 감지"""
        text_lower = resp.text.lower()
        return any(marker in text_lower for marker in _BLOCKED_MARKERS)

    def _handle_blocked(self, method: str, url: str, max_retries: int = 2, **kwargs) -> requests.Response:
        """차단 감지 시 대기 후 재시도 — 백오프 루프에 재진입하지 않음 (스펙 4-4)"""
        for attempt in range(max_retries):
            print(f"[BLOCKED] 차단 신호 감지, 60초 대기 후 재시도 ({attempt + 1}/{max_retries})")
            time.sleep(60)
            resp = self.session.request(method, url, **kwargs)
            resp.raise_for_status()
            if not self._is_blocked(resp):
                return resp
        raise requests.RequestException("[BLOCKED] 지속적 차단 감지, 요청 중단")
```

- [ ] **Step 4: 전체 테스트 통과 확인**

Run: `python -m pytest -q`
Expected: 26 passed (기존 23 + 신규 3)

- [ ] **Step 5: Commit**

```bash
git add adapters/scraper.py tests/test_scraper_stealth.py
git commit -m "feat: 차단 신호 감지 + 대기 재시도"
```
