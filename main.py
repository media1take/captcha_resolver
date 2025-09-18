# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright_extract import run

app = FastAPI(title="Captcha Resolver")

class URLRequest(BaseModel):
    url: str
    wait_seconds: int = 12000  # default 12 seconds
    headful: bool = False

@app.post("/resolve")
async def resolve_captcha(req: URLRequest):
    try:
        # Await the async Playwright coroutine directly
        result = await run(req.url, req.wait_seconds / 1000, req.headful)  # convert ms to seconds if needed
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
