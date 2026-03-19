from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.collect import resume_collect

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 고용24 채용공고 수집 재개 ===")
    result = resume_collect(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"총 공고: {result.total}")
    print(f"신규 수집: {result.collected}")
    print(f"실패: {result.failed}")
