from dataclasses import dataclass
from math import ceil


@dataclass
class CollectResult:
    total: int
    collected: int
    failed: int


def _collect_missing(scraper, store, existing_ids: set[str]) -> CollectResult:
    """전체 페이지를 순회하며 existing_ids에 없는 공고만 수집.
    existing_ids는 in-place로 갱신되어 같은 실행 내 중복 요청을 방지한다."""
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

        new_ids = [id for id in ids if id not in existing_ids]
        if not new_ids:
            continue

        for wanted_auth_no in new_ids:
            try:
                job = scraper.fetch_job_detail(wanted_auth_no)
                if job:
                    store.add_job(job)
                    existing_ids.add(wanted_auth_no)
                    collected += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[ERROR] 상세 조회 실패 ({wanted_auth_no}): {e}")
                failed += 1

        print(f"[{page}/{total_pages}] 신규: {collected}, 실패: {failed}")

    return CollectResult(total=total, collected=collected, failed=failed)


def collect_all_jobs(scraper, store) -> CollectResult:
    """완전 초기 수집 — DB 초기화 후 전체 수집"""
    store.clear()
    return _collect_missing(scraper, store, existing_ids=set())


def resume_collect(scraper, store) -> CollectResult:
    """중단 재개 — 기존 데이터 보존, 빠진 공고만 수집.
    빈 DB에서 실행하면 collect_all_jobs와 동일하게 전체 수집 (clear 없이)."""
    existing_ids = store.get_all_ids()
    print(f"[RESUME] 기존 {len(existing_ids)}건 보존, 빠진 공고 수집")
    return _collect_missing(scraper, store, existing_ids)
