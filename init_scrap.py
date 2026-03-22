import argparse

from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.collect import collect_all_jobs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="고용24 전체 채용공고 수집")
    parser.add_argument("--dry", action="store_true", help="테스트 모드: 10페이지만 수집")
    args = parser.parse_args()

    scraper = Work24Scraper()
    store = JsonJobStore()

    mode = "[DRY] " if args.dry else ""
    print(f"=== {mode}고용24 전체 채용공고 수집 시작 ===")
    result = collect_all_jobs(scraper, store, max_pages=10 if args.dry else None)
    print(f"\n=== 완료 ===")
    print(f"총 공고: {result.total}")
    print(f"수집 성공: {result.collected}")
    print(f"만료 스킵: {result.expired}")
    print(f"차단: {result.blocked}")
    print(f"에러: {result.errors}")
