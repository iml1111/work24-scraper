from dataclasses import dataclass
from math import ceil


@dataclass
class SyncResult:
    scanned_pages: int
    new_count: int
    failed: int


def sync_jobs(scraper, store) -> SyncResult:
    existing_ids = store.get_all_ids()
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    new_count = 0
    failed = 0

    for page in range(1, total_pages + 1):
        try:
            ids = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            continue

        new_ids = [id for id in ids if id not in existing_ids]

        for wanted_auth_no in new_ids:
            try:
                job = scraper.fetch_job_detail(wanted_auth_no)
                if job:
                    store.add_job(job)
                    existing_ids.add(wanted_auth_no)
                    new_count += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[ERROR] 상세 조회 실패 ({wanted_auth_no}): {e}")
                failed += 1

        page_new = len(new_ids)
        print(f"[{page}/{total_pages}] 이 페이지 신규: {page_new}, 누적 신규: {new_count}")

    return SyncResult(scanned_pages=total_pages, new_count=new_count, failed=failed)
