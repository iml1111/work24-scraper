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
        self._total = max(pages.keys(), default=0) * 50
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
    """연속 early_stop 페이지 동안 신규 없으면 조기 종료"""
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
            5: ["A001"],
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
    assert 5 not in scraper.fetched_pages
    assert result.scanned_pages == 4


def test_sync_no_early_stop_when_new_found():
    """신규가 발견되면 consecutive_empty 리셋"""
    job_a = _make_job("A001")
    job_c = _make_job("C001")
    scraper = FakeScraper(
        pages={
            1: ["A001"],
            2: ["A001"],
            3: ["C001"],
            4: ["A001"],
            5: ["A001"],
        },
        details={"C001": job_c},
    )
    store = FakeStore(initial={"A001": job_a})

    result = sync_jobs(scraper, store, early_stop=3)

    assert result.new_count == 1
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
