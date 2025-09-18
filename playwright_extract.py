# playwright_extract.py
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from typing import Optional, Dict, Any

# ---- config defaults ----
WAIT_SECONDS = 12   # time to wait for JS/XHR
HEADFUL = False     # show browser for debugging
SAVE_DIR = Path(".")

# Helper regexes
RE_SECRET = re.compile(r"secret_key\s*[:=]\s*['\"]([A-Za-z0-9_\-]{6,300})['\"]")
RE_SESSION = re.compile(r"SessionID\s*[:=]\s*['\"]([A-Za-z0-9_\-]{6,300})['\"]")


async def extract_from_html(html: str) -> Dict[str, Optional[str]]:
    out = {"secret_key": None, "SessionID": None}
    secret_match = RE_SECRET.search(html)
    session_match = RE_SESSION.search(html)
    if secret_match:
        out["secret_key"] = secret_match.group(1)
    if session_match:
        out["SessionID"] = session_match.group(1)
    return out


async def run(url: str, wait_seconds: int = WAIT_SECONDS, headful: bool = HEADFUL) -> Dict[str, Any]:
    browser = context = page = None
    captured = {"xhr_found": False, "cfnl_request": None, "cfnl_response": None}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=not headful, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context()
            page = await context.new_page()

            # Listen for requests
            async def on_request(req):
                if "/cfnl" in req.url:
                    try:
                        post_data = await req.post_data()
                    except:
                        post_data = None
                    captured["cfnl_request"] = {
                        "url": req.url,
                        "method": req.method,
                        "post_data": post_data,
                        "headers": dict(req.headers),
                    }
                    captured["xhr_found"] = True

            # Listen for responses
            async def on_response(resp):
                if "/cfnl" in resp.url:
                    try:
                        text = await resp.text()
                    except:
                        text = "<no text>"
                    captured["cfnl_response"] = {"url": resp.url, "status": resp.status, "text": text}
                    captured["xhr_found"] = True

            page.on("request", on_request)
            page.on("response", on_response)

            try:
                await page.goto(url, wait_until="networkidle", timeout=120000)
            except PWTimeout:
                pass

            # Wait JS/XHR
            await asyncio.sleep(wait_seconds)

            html = await page.content()
            cookies = await context.cookies()

            # Extract hidden inputs
            hidden_inputs = {}
            try:
                hidden_pairs = await page.eval_on_selector_all(
                    "input[type=hidden]",
                    """nodes => nodes.map(n => ({name: n.name || n.getAttribute('name'), value: n.value || n.getAttribute('value')}))"""
                )
                for p in hidden_pairs:
                    if p.get("name"):
                        hidden_inputs[p["name"]] = p.get("value")
            except:
                pass

            heur = await extract_from_html(html)
            for key in ("secret_key", "SessionID"):
                if heur.get(key) and not hidden_inputs.get(key):
                    hidden_inputs[key] = heur[key]

            # Extract get_id from DOM or URL
            get_id = None
            try:
                down_id = await page.eval_on_selector("#down-id", "el => el ? el.textContent.trim() : null")
                get_id = down_id or (url.split("/file/")[-1] if "/file/" in url else None)
            except:
                if "/file/" in url:
                    get_id = url.split("/file/")[-1]

            # Extract sitekey
            sitekey = None
            try:
                sitekey = await page.eval_on_selector(".cf-turnstile", "el => el ? el.getAttribute('data-sitekey') : null")
            except:
                pass

            return {
                "status": "xhr_seen" if captured["xhr_found"] else "no_xhr",
                "cfnl_request": captured["cfnl_request"],
                "cfnl_response": captured["cfnl_response"],
                "extracted": {
                    "get_id": get_id,
                    "sitekey": sitekey,
                    "secret_key": hidden_inputs.get("secret_key"),
                    "SessionID": hidden_inputs.get("SessionID"),
                    "all_hidden_inputs": hidden_inputs
                },
                "cookies": cookies
            }

    finally:
        if browser:
            await browser.close()
