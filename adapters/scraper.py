import re

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.work24.go.kr"
LISTING_URL = f"{BASE_URL}/wk/a/b/1200/retriveDtlEmpSrchListInPost.do"
DETAIL_URL = f"{BASE_URL}/wk/a/b/1500/empDetailAuthView.do"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 0.5


def parse_listing_ids(html: str) -> list[str]:
    """HTML에서 wantedAuthNo 목록 추출 (empDetailAuthView 링크에서)"""
    matches = re.findall(r'empDetailAuthView\.do\?wantedAuthNo=([^&"]+)', html)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def parse_total_count(html: str) -> int:
    """HTML에서 totalRecordCount 추출"""
    match = re.search(r"totalRecordCount\s*:\s*(\d+)", html)
    if not match:
        raise ValueError("totalRecordCount not found in HTML")
    return int(match.group(1))
