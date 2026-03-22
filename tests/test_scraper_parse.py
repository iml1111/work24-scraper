import os

from adapters.scraper import (
    is_expired_page,
    parse_job_detail,
    parse_listing_refs,
    parse_total_count,
)
from domain.models import JobRef

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

TEST_REF = JobRef(
    wanted_auth_no="Dd04022603180062",
    info_type_cd="VALIDATION",
    info_type_group="tb_workinfoworknet",
)


def read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def test_parse_listing_refs():
    html = read_fixture("listing_page.html")
    refs = parse_listing_refs(html)
    assert len(refs) == 10
    assert all(isinstance(ref, JobRef) for ref in refs)
    assert all(len(ref.wanted_auth_no) > 5 for ref in refs)
    assert all(ref.info_type_cd for ref in refs)
    assert all(ref.info_type_group for ref in refs)
    auth_nos = [ref.wanted_auth_no for ref in refs]
    assert len(auth_nos) == len(set(auth_nos))


def test_parse_total_count():
    html = read_fixture("listing_page.html")
    count = parse_total_count(html)
    assert isinstance(count, int)
    assert count > 100000


# ---------------------------------------------------------------------------
# Detail page tests
# ---------------------------------------------------------------------------


def test_parse_job_detail():
    html = read_fixture("detail_page.html")
    job = parse_job_detail(html, TEST_REF)
    assert job is not None
    assert len(job.title) > 0
    assert len(job.company) > 0
    assert len(job.location) > 0
    assert len(job.job_description) > 0


def test_parse_job_detail_has_required_fields():
    html = read_fixture("detail_page.html")
    job = parse_job_detail(html, TEST_REF)
    assert job is not None
    assert job.qualification      # 지원 자격
    assert job.experience         # 연차
    assert job.hiring_process     # 채용 프로세스
    assert job.employment_conditions  # 채용 조건
    assert job.application_method     # 지원 방법
    assert job.detail_url         # 공고 링크
    assert job.deadline_date      # 마감일
    assert job.registration_date  # 등록일


def test_is_expired_page_true():
    html = read_fixture("expired_page.html")
    assert is_expired_page(html) is True


def test_is_expired_page_false():
    html = read_fixture("detail_page.html")
    assert is_expired_page(html) is False
