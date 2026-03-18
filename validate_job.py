from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.validate import validate_all_jobs

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 채용공고 유효성 검증 시작 ===")
    result = validate_all_jobs(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"검증 건수: {result.total_checked}")
    print(f"제거 (마감): {result.removed}")
    print(f"유효 (채용중): {result.still_active}")
