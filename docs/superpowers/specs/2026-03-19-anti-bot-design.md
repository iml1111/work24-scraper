# 봇 탐지 우회 — 요청 패턴 종합 강화

> 작성일: 2026-03-19
> 상태: 승인됨

## 1. 배경

- 고용24 전체 수집(init_scrap) 시 약 13만건 상세 요청, 18시간 연속 실행
- 현재 고정 UA + 고정 딜레이(0.5s)만 적용 — 봇 패턴으로 탐지될 위험
- 현재까지 차단 경험 없으나, 예방적 방어 필요
- 프록시/TLS 핑거프린팅은 범위 제외 (단일 IP, requests 유지)

## 2. 변경 범위

- **수정 파일**: `adapters/scraper.py`만 수정
- **public 메서드 시그니처 유지**: `get_total_count`, `fetch_listing_page`, `fetch_job_detail`, `is_job_active` 변경 없음 → usecase/CLI 계층 수정 불필요
- **생성자 파라미터 변경**: `delay: float` → `delay_range: tuple`, `rotate_every: int`. 모든 호출부가 `Work24Scraper()` (인자 없음)로 사용 중이므로 영향 없음
- **새 의존성 없음**: 표준 라이브러리(`random`)만 추가 사용

## 3. 요청 패턴 자연화

### 3-1. UA 로테이션

- 5~8개 현대 브라우저 UA 풀 (Chrome/Firefox/Safari, Mac/Windows 조합)
- 세션 생성 시 랜덤 선택 (요청마다 변경하지 않음 — 실제 사용자 패턴)

구현 시 완전한 UA 문자열 사용 필요 (아래는 축약 표기):

```python
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Chrome/120.0.0.0 ...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/121.0.0.0 ...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Safari/17.2",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) ... Firefox/122.0",
    # 5~8개, 실제 브라우저에서 캡처한 완전한 UA 문자열 사용
]
```

### 3-2. 리얼리스틱 브라우저 헤더

세션 생성 시 적용:

```python
{
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
```

### 3-3. Referer 설정

요청 유형에 따라 자연스러운 Referer 부여:

| 요청 유형 | Referer |
|-----------|---------|
| 목록 (POST) | `https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do` |
| 상세 (GET) | `https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do` |

### 3-4. 랜덤 딜레이

- 기존: `time.sleep(0.5)` (고정)
- 변경: `time.sleep(random.uniform(0.3, 1.5))` (균등 분포)
- `__init__` 파라미터: `delay_range: tuple[float, float] = (0.3, 1.5)`

## 4. 복원력 (Resilience)

### 4-1. 세션 로테이션

- `rotate_every: int = 200` — N건 요청마다 세션 재생성
- 재생성 시: 새 `requests.Session()` + UA 재선택 + 헤더 재설정
- `_request_count` 카운터를 `_request_with_delay` 내에서 관리

### 4-2. 지수 백오프 + 자동 재시도

- 대상: HTTP 429 (Too Many Requests), 5xx (Server Error)
- 기존 `resp.raise_for_status()`를 즉시 호출하지 않고, 상태 코드 직접 검사 후 재시도 로직 진입
- 재시도 간격: `2^attempt * 2` 초 (2s → 4s → 8s)
- 최대 재시도: 3회
- 3회 실패 시 `requests.RequestException` 발생 → usecase에서 skip/카운트

### 4-3. 차단 신호 감지

응답 본문 검사 키워드:
- `"captcha"`, `"보안문자"`, `"자동화된 요청"`, `"비정상적인 접근"`
- 향후 실제 차단 경험 시 마커 추가 가능 (리스트로 관리)

감지 시 동작:
- 60초 대기 후 재시도 (최대 2회)
- 지속 차단 시: 예외 발생 + `[BLOCKED]` 로그 출력

### 4-4. 백오프/차단 감지 우선순위

1. 요청 실행 후 **상태 코드 먼저 확인** — 429/5xx면 지수 백오프 재시도 (최대 3회)
2. 상태 코드 정상(200)이면 **응답 본문에서 차단 신호 검사** — 감지 시 60초 대기 후 재시도 (최대 2회)
3. 두 메커니즘은 독립적 (중첩되지 않음): 백오프 성공 후 본문 검사, 본문 재시도는 백오프 루프에 재진입하지 않음

### 4-5. 로깅

기존 `[ERROR]` 패턴과 일관되게:
- 세션 로테이션: `[SESSION] 세션 갱신 (요청 {count}건 도달)`
- 백오프 재시도: `[RETRY] HTTP {status}, {delay}초 후 재시도 ({attempt}/{max})`
- 차단 감지: `[BLOCKED] 차단 신호 감지, 60초 대기 후 재시도 ({attempt}/{max})`

## 5. 구현 변경 상세

### `Work24Scraper.__init__` 변경

```python
# Before
def __init__(self, delay: float = REQUEST_DELAY):

# After
def __init__(self, delay_range: tuple[float, float] = (0.3, 1.5), rotate_every: int = 200):
```

### `_request_with_delay` 변경

```
1. _request_count 증가
2. rotate_every 도달 시 → _rotate_session()
3. random.uniform(*delay_range) 만큼 sleep
4. 요청 실행 (raise_for_status 호출하지 않음)
5. 상태 코드 검사: 429/5xx → 지수 백오프 재시도 (최대 3회, 실패 시 예외)
6. 상태 코드 정상 → 응답 본문 차단 신호 검사 → 감지 시 60s 대기 후 재시도 (최대 2회)
7. 정상 응답 반환
```

### 새 private 메서드

- `_create_session()`: UA 랜덤 선택 + 헤더 설정 + Session 생성
- `_rotate_session()`: `_create_session()` 호출 + 카운터 리셋
- `_is_blocked(response)`: 차단 신호 감지 (CAPTCHA 등)

## 6. 테스트 전략

- 기존 테스트: usecase 계층 FakeScraper 사용 → 영향 없음
- 신규 테스트 불필요: 내부 구현 변경이며, HTTP 동작 테스트는 실제 서버 필요 (통합 테스트 영역)
- 수동 검증: init_scrap 실행으로 실제 동작 확인
