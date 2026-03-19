import argparse

from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.collect import resume_collect

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="고용24 채용공고 수집 재개")
    parser.add_argument("--dry", action="store_true", help="테스트 모드: 5페이지만 수집")
    args = parser.parse_args()

    scraper = Work24Scraper()
    store = JsonJobStore()

    mode = "[DRY] " if args.dry else ""
    print(f"=== {mode}고용24 채용공고 수집 재개 ===")
    result = resume_collect(scraper, store, max_pages=5 if args.dry else None)
    print(f"\n=== 완료 ===")
    print(f"총 공고: {result.total}")
    print(f"신규 수집: {result.collected}")
    print(f"실패: {result.failed}")
