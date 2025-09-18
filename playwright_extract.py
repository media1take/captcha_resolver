# playwright_extract.py
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ---- config defaults ----
WAIT_SECONDS = 12   # time to wait for JS/XHR
HEADFUL = False     # show browser for debugging
SAVE_DIR = Path(".")

# Helper regexes
RE_SECRET = re.compile(r"secret_key\s*[:=]\s*['\"]([A-Za-z0-9_\-]{6,300})['\"]")
RE_SESSION = re.compile(r"SessionID\s*[:=]\s*['\"]([A-Za-z0-9_\-]{6,300})['\"]")

async def extract_from_html(html: str):
    out = {"secret_key": None, "SessionID": None}
    for m in RE_SECRET.finditer(html):
        out["secret_key"] = m.group(1)
        break
    for m in RE_SESSION.finditer(html):
        out["SessionID"] = m.group(1)
        break
    return out

async def run(url: str, wait_seconds: int = WAIT_SECONDS, headful: bool = HEADFUL):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headful, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context()
        page = await context.new_page()

        captured = {"xhr_found": False, "cfnl_request": None, "cfnl_response": None}

        # listen for requests
        async def on_request(req):
            try:
                if "/cfnl" in req.url:
                    post_data = None
                    try:
                        post_data = await req.post_data()
                    except:
                        pass
                    captured["cfnl_request"] = {
                        "url": req.url,
                        "method": req.method,
                        "post_data": post_data,
                        "headers": dict(req.headers)
                    }
                    captured["xhr_found"] = True
            except Exception:
                pass

        # listen for responses
        async def on_response(resp):
            try:
                if "/cfnl" in resp.url:
                    text = None
                    try:
                        text = await resp.text()
                    except:
                        text = "<no text>"
                    captured["cfnl_response"] = {"url": resp.url, "status": resp.status, "text": text}
                    captured["xhr_found"] = True
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=120000)  # 2 min
        except PWTimeout:
            pass  # continue even if navigation times out

        await asyncio.sleep(wait_seconds)

        html = await page.content()
        cookies = await context.cookies()

        # extract hidden inputs
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
        if heur.get("secret_key") and not hidden_inputs.get("secret_key"):
            hidden_inputs["secret_key"] = heur["secret_key"]
        if heur.get("SessionID") and not hidden_inputs.get("SessionID"):
            hidden_inputs["SessionID"] = heur["SessionID"]

        # extract get_id from DOM or URL
        get_id = None
        try:
            down_id = await page.eval_on_selector("#down-id", "el => el ? el.textContent.trim() : null")
            get_id = down_id if down_id else url.split("/file/")[-1] if "/file/" in url else None
        except:
            if "/file/" in url:
                get_id = url.split("/file/")[-1]

        # extract sitekey
        sitekey = None
        try:
            sitekey = await page.eval_on_selector(".cf-turnstile", "el => el ? el.getAttribute('data-sitekey') : null")
        except:
            pass

        await browser.close()

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
