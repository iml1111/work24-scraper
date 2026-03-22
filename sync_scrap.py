from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.sync import sync_jobs

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 고용24 신규 채용공고 동기화 시작 ===")
    result = sync_jobs(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"스캔 페이지: {result.scanned_pages}")
    print(f"신규 추가: {result.new_count}")
    print(f"만료 스킵: {result.expired}")
    print(f"차단: {result.blocked}")
    print(f"에러: {result.errors}")
