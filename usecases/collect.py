from dataclasses import dataclass
from math import ceil

from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore


@dataclass
class CollectResult:
    total: int
    collected: int
    expired: int
    blocked: int
    errors: int


def _collect_missing(
    scraper: Work24Scraper,
    store: JsonJobStore,
    existing_ids: set[str],
    start_page: int = 1,
    max_pages: int | None = None,
) -> CollectResult:
    """페이지를 순회하며 existing_ids에 없는 공고만 수집.
    existing_ids는 in-place로 갱신되어 같은 실행 내 중복 요청을 방지한다."""
    total = scraper.get_total_count()
    total_pages = ceil(total / 50)
    end_page = min(total_pages, start_page + max_pages - 1) if max_pages else total_pages
    collected = 0
    expired = 0
    blocked = 0
    errors = 0

    for page in range(start_page, end_page + 1):
        try:
            refs = scraper.fetch_listing_page(page)
        except Exception as e:
            print(f"[ERROR] 목록 페이지 {page} 실패: {e}")
            errors += 50
            continue

        new_refs = [ref for ref in refs if ref.wanted_auth_no not in existing_ids]
        if not new_refs:
            continue

        for ref in new_refs:
            try:
                job, status = scraper.fetch_job_detail(ref)
                if status == "ok":
                    store.add_job(job)
                    existing_ids.add(ref.wanted_auth_no)
                    collected += 1
                    print(f"[{page}/{total_pages}] {ref.wanted_auth_no} {job.title} → 수집")
                elif status == "expired":
                    expired += 1
                    print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 만료")
                elif status == "blocked":
                    blocked += 1
                    print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 차단")
                else:
                    errors += 1
                    print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 에러")
            except Exception as e:
                errors += 1
                print(f"[{page}/{total_pages}] {ref.wanted_auth_no} → 에러: {e}")

        print(f"[{page}/{total_pages} 완료] 신규: {collected}, 만료: {expired}, 차단: {blocked}, 에러: {errors}")

    return CollectResult(total=total, collected=collected, expired=expired, blocked=blocked, errors=errors)


def collect_all_jobs(scraper: Work24Scraper, store: JsonJobStore, max_pages: int | None = None) -> CollectResult:
    """완전 초기 수집 — DB 초기화 후 전체 수집"""
    store.clear()
    return _collect_missing(scraper, store, existing_ids=set(), max_pages=max_pages)


def resume_collect(scraper: Work24Scraper, store: JsonJobStore, max_pages: int | None = None) -> CollectResult:
    """중단 재개 — 기존 데이터 보존, 빠진 공고만 수집.
    빈 DB에서 실행하면 collect_all_jobs와 동일하게 전체 수집 (clear 없이)."""
    existing_ids = store.get_all_ids()
    start_page = len(existing_ids) // 50 + 1 if max_pages and existing_ids else 1
    print(f"[RESUME] 기존 {len(existing_ids)}건 보존, 페이지 {start_page}부터 수집")
    return _collect_missing(scraper, store, existing_ids, start_page=start_page, max_pages=max_pages)
