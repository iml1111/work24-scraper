from dataclasses import dataclass
from math import ceil


@dataclass
class CollectResult:
    total: int
    collected: int
    failed: int


def collect_all_jobs(scraper, store) -> CollectResult:
    store.clear()
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    collected = 0
    failed = 0

    for page in range(1, total_pages + 1):
        try:
            ids = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            failed += 50
            continue

        for wanted_auth_no in ids:
            try:
                job = scraper.fetch_job_detail(wanted_auth_no)
                if job:
                    store.add_job(job)
                    collected += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[ERROR] 상세 조회 실패 ({wanted_auth_no}): {e}")
                failed += 1

        print(f"[{page}/{total_pages}] 수집: {collected}, 실패: {failed}")

    return CollectResult(total=total, collected=collected, failed=failed)
