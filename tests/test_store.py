import json

import pytest

from adapters.store import JsonJobStore
from domain.models import Job


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
    with open(store.path) as f:
        data = json.load(f)
    assert "A001" in data
