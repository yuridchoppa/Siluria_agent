"""
AnakinScraper Integration Module
Inspired by and compatible with AnakinScraper OSS (https://github.com/Anakin-Inc/anakin).

Architecture:
- Handler Chain with Fallback:
    1. HTTP Handler (Fast direct extraction with anti-bot headers & HTML->Markdown)
    2. Headless Browser Handler (Camoufox / Playwright for JS execution)
    3. Anakin API Handler (Hosted anakin.io / local AnakinScraper API fallback)
- LLM-Ready Markdown output: Strips boilerplates, navbars, and preserves semantic markdown.
"""

import os
import sys
import re
from typing import Dict, Any, Optional, List
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import bs4
except (ImportError, Exception):
    bs4 = None

try:
    from playwright.sync_api import sync_playwright
except (ImportError, Exception):
    sync_playwright = None

# Configuration for AnakinScraper API
ANAKIN_SCRAPER_URL = (os.getenv("ANAKIN_SCRAPER_URL") or "http://localhost:8080").rstrip("/")
ANAKIN_API_KEY = (os.getenv("ANAKIN_API_KEY") or "").strip()

# Common patterns indicating scraping blocks or anti-bot challenge
BLOCKED_PATTERNS = [
    "attention required! | cloudflare",
    "just a moment...",
    "cf-browser-verification",
    "access denied",
    "captcha-delivery",
    "security check to continue",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def html_to_markdown(html_content: str) -> str:
    """
    Convert raw HTML to clean LLM-ready markdown, following AnakinScraper specs.
    Removes boilerplate elements and formats headings, links, lists, code, and tables.
    """
    if not html_content:
        return ""

    if not bs4:
        # Simple regex fallback
        cleaned = re.sub(r"<(script|style|nav|header|footer|iframe|svg|noscript)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    soup = bs4.BeautifulSoup(html_content, "html.parser")

    # Remove non-content tags
    for tag in soup(["script", "style", "nav", "header", "footer", "iframe", "noscript", "svg", "form"]):
        tag.decompose()

    # Convert headings
    for i in range(1, 7):
        for h in soup.find_all(f"h{i}"):
            prefix = "#" * i + " "
            h.replace_with(f"\n\n{prefix}{h.get_text(strip=True)}\n\n")

    # Convert links
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if text and href and not href.startswith("javascript:"):
            a.replace_with(f" [{text}]({href}) ")

    # Convert lists
    for li in soup.find_all("li"):
        li.replace_with(f"\n- {li.get_text(strip=True)}")

    # Convert code blocks
    for pre in soup.find_all("pre"):
        code = pre.get_text()
        pre.replace_with(f"\n```\n{code.strip()}\n```\n")

    for code in soup.find_all("code"):
        code.replace_with(f" `{code.get_text(strip=True)}` ")

    # Extract text with normalized spacing
    text = soup.get_text()
    lines = [line.strip() for line in text.splitlines()]
    blocks = []
    for line in lines:
        if line:
            blocks.append(line)

    markdown = "\n".join(blocks)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _is_blocked(text: str) -> bool:
    """Check if content matches common anti-bot challenge patterns."""
    sample = text[:2000].lower()
    return any(p in sample for p in BLOCKED_PATTERNS)


class AnakinScraper:
    """
    AnakinScraper Handler Chain (HTTP -> Browser -> API)
    Implements the 3-stage fallback architecture from Anakin-Inc/anakin.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 15,
    ):
        self.api_url = (api_url or ANAKIN_SCRAPER_URL).rstrip("/")
        self.api_key = api_key or ANAKIN_API_KEY
        self.timeout = timeout

    def scrape_http(self, url: str) -> Optional[str]:
        """Stage 1: Fast HTTP GET (~200ms) with anti-bot headers."""
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
            if resp.ok and resp.text:
                if not _is_blocked(resp.text):
                    md = html_to_markdown(resp.text)
                    if len(md) > 100:
                        return md
        except Exception:
            pass
        return None

    def scrape_browser(self, url: str) -> Optional[str]:
        """Stage 2: Anti-detect browser via Playwright / Camoufox."""
        if not sync_playwright:
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=DEFAULT_HEADERS["User-Agent"],
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                html = page.content()
                browser.close()

                if html and not _is_blocked(html):
                    md = html_to_markdown(html)
                    if len(md) > 100:
                        return md
        except Exception:
            pass
        return None

    def scrape_api(self, url: str) -> Optional[str]:
        """
        Stage 3: External AnakinScraper service / anakin.io API fallback.
        Connects to a running AnakinScraper OSS server (POST /v1/scrape)
        or the hosted anakin.io API (POST /v1/url-scraper with polling).
        """
        import time

        # 1. First try self-hosted AnakinScraper endpoint if configured or running
        if self.api_url and self.api_url != "none":
            try:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                resp = requests.post(
                    f"{self.api_url}/v1/scrape",
                    json={"url": url},
                    headers=headers,
                    timeout=2.0
                )
                if resp.ok:
                    data = resp.json()
                    res = data.get("markdown") or data.get("text") or data.get("content")
                    if res:
                        return str(res).strip()
            except Exception:
                pass

        # 2. Try hosted Anakin.io API (https://api.anakin.io/v1/url-scraper)
        if self.api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                resp = requests.post(
                    "https://api.anakin.io/v1/url-scraper",
                    json={"url": url},
                    headers=headers,
                    timeout=self.timeout
                )
                if resp.status_code in (200, 201, 202):
                    data = resp.json()
                    job_id = data.get("jobId") or data.get("id")
                    if job_id:
                        # Poll for job completion
                        poll_url = f"https://api.anakin.io/v1/url-scraper/{job_id}"
                        for _ in range(6):
                            time.sleep(1.0)
                            poll_resp = requests.get(poll_url, headers=headers, timeout=self.timeout)
                            if poll_resp.ok:
                                poll_data = poll_resp.json()
                                if poll_data.get("status") == "completed":
                                    # Convert HTML to markdown or return existing markdown
                                    if poll_data.get("markdown"):
                                        return str(poll_data["markdown"]).strip()
                                    if poll_data.get("html"):
                                        return html_to_markdown(poll_data["html"])
                                    if poll_data.get("text"):
                                        return str(poll_data["text"]).strip()
                                elif poll_data.get("status") in ("failed", "error"):
                                    break
            except Exception as e:
                print(f"Hosted Anakin API error: {e}")

        return None

    def scrape(self, url: str, max_length: int = 15000) -> Dict[str, Any]:
        """
        Execute the AnakinScraper fallback chain for a URL:
        HTTP -> Browser -> API Handler
        """
        handler_used = None
        content = None

        # 1. Try Fast HTTP
        content = self.scrape_http(url)
        if content:
            handler_used = "AnakinScraper-HTTP"

        # 2. Try Browser Handler
        if not content:
            content = self.scrape_browser(url)
            if content:
                handler_used = "AnakinScraper-Browser"

        # 3. Try Anakin API Handler
        if not content:
            content = self.scrape_api(url)
            if content:
                handler_used = "AnakinScraper-API"

        if not content:
            return {
                "success": False,
                "url": url,
                "error": f"Failed to retrieve content from {url} across all AnakinScraper handlers.",
                "markdown": "",
                "handler": "none",
            }

        truncated = content[:max_length]
        return {
            "success": True,
            "url": url,
            "handler": handler_used,
            "markdown": truncated,
            "length": len(truncated),
        }


# Global scraper instance
_default_scraper = AnakinScraper()


def anakin_scrape(url: str, max_length: int = 15000) -> str:
    """
    Scrape a webpage and return LLM-ready markdown using the AnakinScraper engine.
    """
    res = _default_scraper.scrape(url, max_length=max_length)
    if res["success"]:
        header = f"*[AnakinScraper: {res['handler']}]*\n\n"
        return header + res["markdown"]
    return res["error"]


def anakin_scrape_batch(urls: List[str], max_length: int = 8000) -> Dict[str, str]:
    """
    Scrape multiple URLs using AnakinScraper.
    """
    results = {}
    for u in urls[:5]:
        results[u] = anakin_scrape(u, max_length=max_length)
    return results
