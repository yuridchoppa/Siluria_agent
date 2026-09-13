import os
import sys
import re
from typing import List, Dict, Any
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from duckduckgo_search import DDGS
except (ImportError, Exception):
    DDGS = None

try:
    import bs4
except (ImportError, Exception):
    bs4 = None

try:
    from playwright.sync_api import sync_playwright
except (ImportError, Exception):
    sync_playwright = None



def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo HTML POST API with fallbacks to DDGS and Instant Answers.
    Returns a list of dictionaries containing 'title', 'url', and 'snippet'.
    """
    results = []

    # Strategy 1: Direct DuckDuckGo HTML POST (bypasses bot challenges on cloud/serverless IPs)
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://html.duckduckgo.com/",
        }
        resp = requests.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=headers, timeout=8)
        if resp.ok and bs4:
            import urllib.parse
            soup = bs4.BeautifulSoup(resp.text, "html.parser")
            for el in soup.select(".result"):
                a = el.select_one(".result__a")
                snippet_el = el.select_one(".result__snippet")
                if a:
                    raw_url = a.get("href", "")
                    if "uddg=" in raw_url:
                        actual_url = urllib.parse.unquote(raw_url.split("uddg=")[1].split("&")[0])
                    else:
                        actual_url = raw_url
                    results.append({
                        "title": a.get_text(strip=True),
                        "url": actual_url,
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else ""
                    })
                    if len(results) >= max_results:
                        break
    except Exception as e:
        print(f"DDG HTML search error: {e}")

    # Strategy 2: DDGS fallback if Strategy 1 produced 0 results
    if not results and DDGS:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
        except Exception as e:
            print(f"DDGS error: {e}")

    # Strategy 3: DuckDuckGo Instant Answer API fallback
    if not results:
        try:
            ia_resp = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=5
            )
            if ia_resp.ok:
                data = ia_resp.json()
                abstract = data.get("AbstractText")
                source_url = data.get("AbstractURL")
                heading = data.get("Heading")
                if abstract:
                    results.append({
                        "title": heading or query,
                        "url": source_url or "",
                        "snippet": abstract
                    })
        except Exception:
            pass

    if not results:
        return [{
            "title": "No Direct Results",
            "url": "",
            "snippet": f"Web search executed for '{query}', but no direct results were returned. Please synthesize the best answer based on available knowledge."
        }]

    return results


def clean_html(html_content: str) -> str:
    """
    Parse HTML and extract clean, readable text.
    Removes scripts, styles, and extra whitespace.
    """
    if bs4:
        soup = bs4.BeautifulSoup(html_content, 'html.parser')
        for element in soup(["script", "style", "nav", "header", "footer", "iframe", "noscript"]):
            element.extract()
        text = soup.get_text()
    else:
        text = re.sub(r'<[^>]+>', ' ', html_content)

    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return '\n'.join(chunk for chunk in chunks if chunk)


from tools.anakin_scraper import anakin_scrape, anakin_scrape_batch


def scrape_url(url: str, timeout: int = 15000) -> str:
    """
    Scrape a URL and return clean LLM-ready markdown using the AnakinScraper engine
    (Handler chain: Fast HTTP -> Headless Browser -> Anakin API fallback).
    """
    try:
        content = anakin_scrape(url, max_length=12000)
        if content and not content.startswith("Failed to retrieve content"):
            return content
    except Exception as e:
        print(f"AnakinScraper exception: {e}")

    # Fallback attempt 1: Playwright headless browser if installed
    if sync_playwright:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                html_content = page.content()
                browser.close()
                if html_content:
                    return clean_html(html_content)[:12000]
        except Exception:
            pass

    # Fallback attempt 2: local basic HTTP request
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.ok and len(resp.text) > 100:
            return clean_html(resp.text)[:12000]
    except Exception:
        pass

    return f"Unable to fetch content from {url}."
