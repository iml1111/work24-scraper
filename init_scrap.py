from adapters.scraper import Work24Scraper
from adapters.store import JsonJobStore
from usecases.collect import collect_all_jobs

if __name__ == "__main__":
    scraper = Work24Scraper()
    store = JsonJobStore()

    print("=== 고용24 전체 채용공고 수집 시작 ===")
    result = collect_all_jobs(scraper, store)
    print(f"\n=== 완료 ===")
    print(f"총 공고: {result.total}")
    print(f"수집 성공: {result.collected}")
    print(f"수집 실패: {result.failed}")
