import asyncio
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

async def run(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(10)  # wait for CAPTCHA JS

        # Extract SessionID, secret_key, hidden inputs, cookies
        session_id = await page.eval_on_selector("input[name=SessionID]", "el => el.value")
        secret_key = await page.eval_on_selector("input[name=secret_key]", "el => el.value")
        cookies = await context.cookies()

        await browser.close()
        return {
            "status": "success",
            "session_id": session_id,
            "secret_key": secret_key,
            "cookies": cookies
        }
