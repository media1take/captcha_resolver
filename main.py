from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright_extract import run
import asyncio

app = FastAPI()

class URLRequest(BaseModel):
    url: str
    wait_seconds: int = 12
    headful: bool = False
    
def run_sync(url, wait_seconds, headful):
    return asyncio.run(run(url, wait_seconds, headful))

@app.post("/resolve")
async def resolve_captcha(req: URLRequest):
    try:
        result = await asyncio.to_thread(run_sync, req.url, req.wait_seconds, req.headful)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
