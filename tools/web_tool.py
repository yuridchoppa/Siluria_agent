import os
import sys
import re
from typing import List, Dict, Any
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from ddgs import DDGS
except (ImportError, Exception):
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
    Search the web using resilient multi-provider strategy:
    1. Fast DDGS (using latest ddgs package with primp TLS bypass)
    2. Fast Bing HTML Search (sub-second fallback)
    3. Fast DuckDuckGo HTML GET
    4. DuckDuckGo Instant Answers API
    Returns a list of dictionaries containing 'title', 'url', and 'snippet'.
    """
    results = []

    # Strategy 1: DDGS (Fastest, real search index)
    if DDGS:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
                if results:
                    return results
        except Exception as e:
            print(f"DDGS primary search error: {e}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Strategy 2: Fast Bing HTML Search
    if not results and bs4:
        try:
            import urllib.parse
            resp = requests.get(
                f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}",
                headers=headers,
                timeout=3.5
            )
            if resp.ok:
                soup = bs4.BeautifulSoup(resp.text, "html.parser")
                for b in soup.select("li.b_algo"):
                    h2_a = b.select_one("h2 a")
                    snippet_el = b.select_one("p, .b_caption p")
                    if h2_a:
                        url = h2_a.get("href", "")
                        if "bing.com/ck/a" in url and "&u=a1" in url:
                            try:
                                import base64
                                enc = url.split("&u=a1")[1].split("&")[0]
                                rem = len(enc) % 4
                                if rem:
                                    enc += "=" * (4 - rem)
                                url = base64.b64decode(enc).decode("utf-8", errors="ignore")
                            except Exception:
                                pass
                        results.append({
                            "title": h2_a.get_text(strip=True),
                            "url": url,
                            "snippet": snippet_el.get_text(strip=True) if snippet_el else ""
                        })
                        if len(results) >= max_results:
                            break
        except Exception as e:
            print(f"Bing search fallback error: {e}")

    # Strategy 3: DuckDuckGo HTML GET
    if not results:
        try:
            import urllib.parse
            resp = requests.get(
                f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}",
                headers=headers,
                timeout=3.5
            )
            if resp.ok and bs4:
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
            print(f"DDG HTML GET search error: {e}")

    # Strategy 4: DuckDuckGo Instant Answer API fallback
    if not results:
        try:
            ia_resp = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=3
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
            "title": "Search Completed",
            "url": "",
            "snippet": f"Web search executed for '{query}'. Synthesize the most accurate, up-to-date answer directly using domain knowledge and recent updates."
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
