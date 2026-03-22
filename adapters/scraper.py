import random
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from domain.models import Job, JobRef

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


def parse_total_count(html: str) -> int:
    """HTML에서 totalRecordCount 추출"""
    match = re.search(r"totalRecordCount\s*:\s*(\d+)", html)
    if not match:
        raise ValueError("totalRecordCount not found in HTML")
    return int(match.group(1))


# ---------------------------------------------------------------------------
# Detail page helpers
# ---------------------------------------------------------------------------

def _clean_text(text: str | None) -> str:
    """공백·개행 정리하여 한 줄 텍스트로 반환"""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_table_fields(soup: BeautifulSoup) -> dict[str, str]:
    """모든 table 내 th/td 쌍을 dict로 반환"""
    fields: dict[str, str] = {}
    for th in soup.find_all("th", scope="row"):
        key = _clean_text(th.get_text())
        td = th.find_next_sibling("td")
        if td:
            value = _clean_text(td.get_text())
            if key:
                fields[key] = value
    return fields


def _extract_title(soup: BeautifulSoup) -> str:
    """채용공고 제목 추출 (div.tit_area > strong.title)"""
    tit_area = soup.find("div", class_="tit_area")
    if tit_area:
        strong = tit_area.find("strong", class_="title")
        if strong:
            return _clean_text(strong.get_text())
    return ""


def _extract_company_name(soup: BeautifulSoup) -> str:
    """기업명 추출 (div.tit_area > p.corp_info > strong)"""
    tit_area = soup.find("div", class_="tit_area")
    if tit_area:
        corp_info = tit_area.find("p", class_="corp_info")
        if corp_info:
            strong = corp_info.find("strong")
            if strong:
                return _clean_text(strong.get_text())
    return ""


def _extract_job_description(soup: BeautifulSoup) -> str:
    """직무내용 텍스트 추출"""
    strong = soup.find("strong", string=re.compile(r"직무내용"))
    if not strong:
        return ""
    # 직무내용 strong 태그의 부모 div.fold 안의 텍스트
    parent = strong.parent
    if parent:
        # strong 태그를 제외한 나머지 텍스트를 가져옴
        # br 태그를 개행으로 변환
        for br in parent.find_all("br"):
            br.replace_with("\n")
        text = parent.get_text()
        # "직무내용" 헤더 텍스트 제거
        text = re.sub(r"^\s*직무내용\s*", "", text)
        text = text.replace("\xa0", " ")
        # 연속 개행 정리
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        return "\n".join(lines)
    return ""


def _extract_hiring_process(soup: BeautifulSoup) -> str:
    """전형방법 추출 (서류, 면접 등 — disable 아닌 항목)"""
    panel = soup.find("div", id="tab-panel05")
    if not panel:
        return "정보없음"
    items_ul = panel.find("ul", class_="emp_box_items")
    if not items_ul:
        return "정보없음"
    steps: list[str] = []
    for li in items_ul.find_all("li"):
        if "disable" in (li.get("class") or []):
            continue
        p_tag = li.find("p")
        if p_tag:
            step = _clean_text(p_tag.get_text())
            if step:
                steps.append(step)
    return " > ".join(steps) if steps else "정보없음"


def _extract_company_info(soup: BeautifulSoup, company_name: str) -> str:
    """기업정보 섹션에서 기업명, 업종, 기업규모, 근로자수를 조합"""
    panel = soup.find("div", id="tab-panel06")
    if not panel:
        return company_name or "정보없음"

    info: dict[str, str] = {}
    for li in panel.find_all("li"):
        em = li.find("em", class_="tit")
        if em:
            key = _clean_text(em.get_text())
            # em 태그 이후의 텍스트를 가져옴
            value = _clean_text(li.get_text().replace(key, "", 1))
            if key and value and value != "-":
                info[key] = value

    parts: list[str] = []
    if company_name:
        parts.append(company_name)
    for k in ["업종", "기업규모", "근로자수"]:
        if k in info:
            parts.append(f"{k}: {info[k]}")
    return " | ".join(parts) if parts else "정보없음"


def _extract_benefits(soup: BeautifulSoup) -> str | None:
    """복리후생 항목 추출 (disable이 아닌 것 + 기타 복리후생)"""
    panel = soup.find("div", id="tab-panel04")
    if not panel:
        return None

    items: list[str] = []
    # 아이콘 복리후생 목록에서 제공되는 항목만
    items_ul = panel.find("ul", class_="emp_box_items")
    if items_ul:
        for li in items_ul.find_all("li"):
            if "disable" in (li.get("class") or []):
                continue
            p_tag = li.find("p")
            if p_tag:
                name = _clean_text(p_tag.get_text())
                if name:
                    items.append(name)

    # 기타 복리후생
    etc_strong = panel.find("strong", string=re.compile(r"기타 복리후생"))
    if etc_strong:
        p_tag = etc_strong.find_next_sibling("p")
        if p_tag:
            text = _clean_text(p_tag.get_text())
            if text and text != "-":
                items.append(text)

    return ", ".join(items) if items else None


def _extract_deadline_text(soup: BeautifulSoup) -> str:
    """접수 마감일 텍스트 추출"""
    strong = soup.find("strong", string=re.compile(r"접수 마감일"))
    if not strong:
        return ""
    parent = strong.parent
    if not parent:
        return ""
    p_tag = parent.find("p")
    if p_tag:
        return "마감일: " + _clean_text(p_tag.get_text())
    return ""


def _extract_deadline_date(html: str) -> str:
    """JS 변수 var date = 'YYYYMMDD'에서 마감일 추출, YYYY-MM-DD 형식으로 반환"""
    match = re.search(r"var\s+date\s*=\s*'(\d{8})'", html)
    if match:
        raw = match.group(1)
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    # 접수 마감일 영역에서 날짜 패턴 시도
    match = re.search(r"접수\s*마감일.*?(\d{4})[.\-/](\d{2})[.\-/](\d{2})", html, re.DOTALL)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return "정보없음"


def _extract_registration_date(tables: dict[str, str]) -> str:
    """채용공고 등록일시에서 날짜 추출, YYYY-MM-DD 형식으로 반환"""
    raw = tables.get("채용공고 등록일시", "")
    if not raw:
        return "정보없음"
    # 형식: "2026.03.18 00:00:00"
    match = re.search(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})", raw)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return "정보없음"


# ---------------------------------------------------------------------------
# Public API — detail page
# ---------------------------------------------------------------------------

def is_expired_page(html: str) -> bool:
    """만료/존재하지 않는 공고 페이지 판별"""
    return any(marker in html for marker in _EXPIRED_MARKERS)


def parse_job_detail(html: str, ref: JobRef) -> Job:
    """상세 페이지 HTML을 파싱하여 Job 객체 반환."""
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()
    detail_url = (
        f"{DETAIL_URL}?wantedAuthNo={ref.wanted_auth_no}"
        f"&infoTypeCd={ref.info_type_cd}&infoTypeGroup={ref.info_type_group}"
    )

    # th/td 쌍 파싱
    tables = _parse_table_fields(soup)

    # 제목 및 기업명
    title = _extract_title(soup)
    company_name = _extract_company_name(soup)

    # 직무내용
    job_description = _extract_job_description(soup)

    # 지원 자격 (학력 + 자격면허)
    qual_parts = [tables.get("학력", ""), tables.get("자격 면허", "")]
    qualification = " | ".join(p for p in qual_parts if p and p != "-") or "정보없음"

    # 경력
    experience = tables.get("경력", "경력무관")

    # 우대사항
    pref_keys = ["전공", "외국어 능력", "컴퓨터 활용 능력", "우대조건", "기타 우대사항"]
    pref_parts = [tables.get(k, "") for k in pref_keys]
    pref_filtered = [p for p in pref_parts if p and p != "-"]
    preferences = " | ".join(pref_filtered) if pref_filtered else None

    # 근무 예정지
    location = tables.get("근무 예정지", "")
    location = re.sub(r"\s*지도\s*보기\s*", "", location).strip()

    # 전형방법
    hiring_process = _extract_hiring_process(soup)

    # 고용 조건
    cond_parts = [
        tables.get("고용 형태", ""),
        tables.get("임금 조건", ""),
        tables.get("근무 형태", ""),
    ]
    work_hours = tables.get("근무 시간", "")
    if work_hours:
        cond_parts.append(work_hours)
    employment_conditions = (
        " | ".join(p for p in cond_parts if p and p != "-") or "정보없음"
    )

    # 기업정보
    company = _extract_company_info(soup, company_name)

    # 복리후생
    benefits = _extract_benefits(soup)

    # 지원 방법
    app_parts: list[str] = []
    submit_method = tables.get("접수 방법", "")
    if submit_method and submit_method != "-":
        app_parts.append(submit_method)
    submit_docs = tables.get("제출 서류", "")
    if submit_docs and submit_docs != "-":
        app_parts.append(submit_docs)
    deadline_text = _extract_deadline_text(soup)
    if deadline_text:
        app_parts.append(deadline_text)
    application_method = " | ".join(app_parts) or "정보없음"

    # 날짜
    deadline_date = _extract_deadline_date(html)
    registration_date = _extract_registration_date(tables)

    return Job(
        wanted_auth_no=ref.wanted_auth_no,
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


# ---------------------------------------------------------------------------
# HTTP client wrapper
# ---------------------------------------------------------------------------

class Work24Scraper:
    def __init__(
        self,
        delay_range: tuple[float, float] = (1.0, 3.0),
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

    def _rotate_session(self) -> None:
        """세션 교체 — 새 UA + 헤더로 재생성"""
        self.session.close()
        self.session = self._create_session()
        self._request_count = 0
        print(f"[SESSION] 세션 갱신 (요청 {self.rotate_every}건 도달)")

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

    def get_total_count(self) -> int:
        resp = self._request_with_delay(
            "POST", LISTING_URL,
            data={"sortField": "DATE", "sortOrderBy": "DESC", "pageIndex": 1, "resultCnt": 10},
            allow_redirects=True,
        )
        return parse_total_count(resp.text)

    def fetch_listing_page(self, page: int, per_page: int = 10) -> list[JobRef]:
        resp = self._request_with_delay(
            "POST", LISTING_URL,
            data={"sortField": "DATE", "sortOrderBy": "DESC", "pageIndex": page, "resultCnt": per_page},
            allow_redirects=True,
        )
        return parse_listing_refs(resp.text)

    def fetch_job_detail(self, ref: JobRef) -> tuple[Job | None, str]:
        """상세 페이지 조회. 반환: (job, status). status: 'ok'|'expired'|'blocked'|'error'"""
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

    def is_job_active(self, wanted_auth_no: str) -> bool:
        try:
            resp = self._request_with_delay(
                "GET", DETAIL_URL,
                params={"wantedAuthNo": wanted_auth_no, "infoTypeCd": "VALIDATION", "infoTypeGroup": "tb_workinfoworknet"},
            )
            return not is_expired_page(resp.text)
        except requests.RequestException:
            return False
