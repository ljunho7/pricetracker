import requests
from playwright.sync_api import sync_playwright

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

def get(url, session=None, timeout=15, **kwargs):
    s = session or make_session()
    resp = s.get(url, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp

class PlaywrightResponse:
    """Mimics requests.Response for use in scrapers."""
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

def playwright_get(url, timeout=30000) -> PlaywrightResponse:
    """Fetch a page using Playwright headless browser — bypasses bot detection."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = ctx.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_timeout(2000)  # let JS render
            text = page.content()
        finally:
            browser.close()
        return PlaywrightResponse(text)

def get_with_fallback(url, session=None, timeout=15) -> PlaywrightResponse:
    """Try requests first, fall back to Playwright on 403/429."""
    try:
        resp = get(url, session=session, timeout=timeout)
        return PlaywrightResponse(resp.text, resp.status_code)
    except Exception as e:
        if "403" in str(e) or "429" in str(e) or "Forbidden" in str(e):
            print(f"  [playwright fallback] {url[:60]}...")
            return playwright_get(url)
        raise
