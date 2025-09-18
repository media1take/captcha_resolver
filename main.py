from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright_extract import run
import asyncio

app = FastAPI()

class URLRequest(BaseModel):
    url: str
    wait_seconds: int = 12
    headful: bool = False

@app.post("/resolve")
async def resolve_captcha(req: URLRequest):
    try:
        # Run Playwright in background thread to avoid blocking
        result = await asyncio.to_thread(run, req.url, req.wait_seconds, req.headful)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
