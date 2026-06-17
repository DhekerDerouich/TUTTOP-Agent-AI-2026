import requests
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed


def search_web(query: str, max_results: int = 10) -> list[dict[str, str]]:
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                }
                for r in results
            ]
    except Exception:
        return _search_fallback(query, max_results)


def _search_fallback(query: str, max_results: int = 10) -> list[dict[str, str]]:
    try:
        from langchain_community.tools import DuckDuckGoSearchRun

        search = DuckDuckGoSearchRun()
        raw = search.run(
            f"{query} (site:.org OR site:.com OR site:.fr OR site:.eu OR site:.co.uk)"
        )
        return [{"title": query, "snippet": raw[:500], "url": ""}]
    except Exception:
        return []


def search_web_parallel(
    queries: list[str], max_results: int = 8
) -> list[dict[str, str]]:
    all_results = []
    with ThreadPoolExecutor(max_workers=len(queries)) as ex:
        futures = {ex.submit(search_web, q, max_results): q for q in queries}
        for f in as_completed(futures):
            q = futures[f]
            try:
                results = f.result()
                for r in results:
                    r["query"] = q
                all_results.extend(results)
            except Exception:
                pass
    return all_results


def fetch_page(url: str, timeout: int = 15) -> str:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        text = resp.text
        return _extract_text(text)[:8000]
    except Exception:
        return ""


def fetch_pages_parallel(urls: list[tuple[str, str]], timeout: int = 8) -> list[dict]:
    """Fetch multiple pages in parallel. urls = [(url, query), ...]"""
    results = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        fut_map = {ex.submit(fetch_page, u, timeout): (u, q) for u, q in urls}
        for f in as_completed(fut_map):
            url, query = fut_map[f]
            content = f.result()
            results.append({"url": url, "query": query, "page_content": content})
    return results


def _extract_text(html: str) -> str:
    try:
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self._text = []
                self._skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "nav", "footer", "header"):
                    self._skip = True

            def handle_endtag(self, tag):
                if tag in ("script", "style", "nav", "footer", "header"):
                    self._skip = False

            def handle_data(self, data):
                if not self._skip:
                    stripped = data.strip()
                    if stripped:
                        self._text.append(stripped)

            def get_text(self):
                return " ".join(self._text)

        extractor = TextExtractor()
        extractor.feed(html)
        return extractor.get_text()
    except Exception:
        import re

        clean = re.sub(r"<[^>]+>", " ", html)
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()
