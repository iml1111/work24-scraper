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

    for i, (wanted_auth_no, job) in enumerate(list(jobs.items()), 1):
        status = "유효"
        try:
            if not scraper.is_job_active(wanted_auth_no, job.info_type_cd, job.info_type_group):
                store.remove_job(wanted_auth_no)
                removed += 1
                status = "제거"
        except Exception as e:
            status = f"에러: {e}"

        print(f"[{i}/{total}] {wanted_auth_no} → {status}")

    return ValidateResult(total_checked=total, removed=removed, still_active=total - removed)
