from adapters.scraper import _BLOCKED_MARKERS, Work24Scraper


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_is_blocked_detects_captcha():
    """차단 마커가 포함된 응답을 감지"""
    scraper = Work24Scraper()
    for marker in _BLOCKED_MARKERS:
        resp = FakeResponse(text=f"<html>{marker}</html>")
        assert scraper._is_blocked(resp) is True


def test_is_blocked_normal_page():
    """정상 응답은 차단으로 판단하지 않음"""
    scraper = Work24Scraper()
    resp = FakeResponse(text="<html><body>정상 채용공고 페이지</body></html>")
    assert scraper._is_blocked(resp) is False


def test_is_blocked_expired_page_not_blocked():
    """만료 공고 페이지는 차단이 아님"""
    scraper = Work24Scraper()
    resp = FakeResponse(text='<script>alert("구인정보를 확인할 수 없습니다")</script>')
    assert scraper._is_blocked(resp) is False
