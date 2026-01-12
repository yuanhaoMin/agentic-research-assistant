import re
from typing import Any, Dict, List
import requests
from bs4 import BeautifulSoup


DEFAULT_MOCK = {
    "Tesla": {
        "partnerships": [
            "Panasonic (battery collaboration)",
            "Various charging infrastructure partners",
        ],
        "urls": ["https://en.wikipedia.org/wiki/Tesla,_Inc."],
    },
    "OpenAI": {
        "partnerships": [
            "Microsoft (strategic partnership)",
            "Various research collaborators",
        ],
        "urls": ["https://en.wikipedia.org/wiki/OpenAI"],
    },
}


def mock_web_search(
    company_name: str, enable_live: bool = False, max_pages: int = 2
) -> Dict[str, Any]:
    """
    MVP web tool:
    - Default: return mocked URLs and partnerships.
    - If enable_live=True: crawl the URLs (mock or wikipedia) and extract text.
    """
    entry = DEFAULT_MOCK.get(company_name, {"partnerships": [], "urls": []})

    urls = list(entry.get("urls", []))
    partnerships = list(entry.get("partnerships", []))

    combined_text_parts: List[str] = []

    if enable_live and urls:
        for url in urls[:max_pages]:
            text = crawl_url(url)
            if text:
                combined_text_parts.append(f"Source: {url}\n{text}")

    return {
        "company": company_name,
        "partnerships": partnerships,
        "urls": urls,
        "combined_text": "\n\n".join(combined_text_parts).strip(),
    }


def crawl_url(url: str, timeout: int = 12) -> str:
    """
    Very simple page crawler:
    - Downloads HTML
    - Extracts visible text from <p> tags
    - Removes extra whitespace
    """
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "mvp-agent/0.1"})
        r.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(r.text, "html.parser")
    ps = soup.find_all("p")
    text = "\n".join(p.get_text(" ", strip=True) for p in ps)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:12000]
