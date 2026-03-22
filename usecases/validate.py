from dataclasses import dataclass

from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore


@dataclass
class ValidateResult:
    total_checked: int
    removed: int
    still_active: int


def validate_all_jobs(scraper: Work24Scraper, store: JsonJobStore) -> ValidateResult:
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
