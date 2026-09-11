from duckduckgo_search import DDGS
from playwright.sync_api import sync_playwright
import bs4
import re
from typing import List, Dict, Any

def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo and return a list of dictionaries
    containing 'title', 'href', and 'body' (snippet).
    """
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
    except Exception as e:
        print(f"Error searching web: {e}")

    return results

def clean_html(html_content: str) -> str:
    """
    Parse HTML and extract clean, readable text.
    Removes scripts, styles, and extra whitespace.
    """
    soup = bs4.BeautifulSoup(html_content, 'html.parser')

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "header", "footer", "iframe", "noscript"]):
        element.extract()

    # Get text
    text = soup.get_text()

    # Break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)

    return text

def scrape_url(url: str, timeout: int = 30000) -> str:
    """
    Navigate to a URL using a headless browser, wait for the page to render,
    and return the cleaned text content.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Navigate and sit tight until network is mostly idle
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            # Try to wait for network idle, but don't fail if it times out
            try:
                page.wait_for_load_state("networkidle", timeout=timeout // 2)
            except Exception:
                pass

            html_content = page.content()
            browser.close()

            return clean_html(html_content)
    except Exception as e:
        return f"Error scraping URL {url}: {str(e)}"

# Quick test block if run directly
if __name__ == "__main__":
    print("Testing DuckDuckGo Search:")
    print(search_web("Anakin Forge AI Hackathon", max_results=2))
    print("\nTesting Playwright Scrape (Python.org):")
    print(scrape_url("https://www.python.org")[:500] + "...\n")
