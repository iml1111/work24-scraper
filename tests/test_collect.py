from domain.models import Job, JobRef
from usecases.collect import CollectResult, collect_all_jobs, resume_collect


def _make_ref(wanted_auth_no: str) -> JobRef:
    return JobRef(wanted_auth_no=wanted_auth_no, info_type_cd="VALIDATION", info_type_group="tb_workinfoworknet")


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
        self._pages = pages
        self._details = details
        self._total = sum(len(ids) for ids in pages.values())

    def get_total_count(self) -> int:
        return self._total

    def fetch_listing_page(self, page: int, per_page: int = 10) -> list[JobRef]:
        return [_make_ref(id) for id in self._pages.get(page, [])]

    def fetch_job_detail(self, ref: JobRef) -> tuple[Job | None, str]:
        job = self._details.get(ref.wanted_auth_no)
        if job is None:
            return (None, "expired")
        return (job, "ok")


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
    assert result.expired == 0
    assert result.blocked == 0
    assert result.errors == 0
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
    assert result.expired == 0
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
    assert result.expired == 0
    assert store.get_all_ids() == {"A001"}


def test_collect_counts_expired_details():
    """상세 조회가 만료 응답이면 expired 카운트 증가"""
    scraper = FakeScraper(
        pages={1: ["A001", "A002"]},
        details={"A001": _make_job("A001"), "A002": None},
    )
    store = FakeStore()

    result = collect_all_jobs(scraper, store)

    assert result.collected == 1
    assert result.expired == 1
    assert result.blocked == 0
    assert result.errors == 0
