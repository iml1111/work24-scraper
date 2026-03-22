from dataclasses import dataclass
from math import ceil

from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore


@dataclass
class SyncResult:
    scanned_pages: int
    new_count: int
    expired: int
    blocked: int
    errors: int


def sync_jobs(scraper: Work24Scraper, store: JsonJobStore, early_stop: int = 3) -> SyncResult:
    """신규 공고만 추가 — 연속 early_stop 페이지 신규 0이면 중단"""
    existing_ids = store.get_all_ids()
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    new_count = 0
    expired = 0
    blocked = 0
    errors = 0
    scanned_pages = 0
    consecutive_empty = 0

    for page in range(1, total_pages + 1):
        scanned_pages = page
        try:
            refs = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            continue

        new_refs = [ref for ref in refs if ref.wanted_auth_no not in existing_ids]

        if not new_refs:
            consecutive_empty += 1
            if consecutive_empty >= early_stop:
                print(f"[STOP] 연속 {early_stop}페이지 신규 없음 → 스캔 중단")
                break
        else:
            consecutive_empty = 0
            for ref in new_refs:
                try:
                    job, status = scraper.fetch_job_detail(ref)
                    if status == "ok":
                        store.add_job(job)
                        existing_ids.add(ref.wanted_auth_no)
                        new_count += 1
                        print(f"[{page}] {ref.wanted_auth_no} {job.title} → 수집")
                    elif status == "expired":
                        expired += 1
                        print(f"[{page}] {ref.wanted_auth_no} → 만료")
                    elif status == "blocked":
                        blocked += 1
                        print(f"[{page}] {ref.wanted_auth_no} → 차단")
                    else:
                        errors += 1
                        print(f"[{page}] {ref.wanted_auth_no} → 에러")
                except Exception as e:
                    errors += 1
                    print(f"[{page}] {ref.wanted_auth_no} → 에러: {e}")

        print(f"[{page}] 신규: {len(new_refs)}, 누적: {new_count}")

    return SyncResult(scanned_pages=scanned_pages, new_count=new_count, expired=expired, blocked=blocked, errors=errors)
