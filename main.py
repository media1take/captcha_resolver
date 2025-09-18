from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright_extract import run  # your existing Playwright async function
import asyncio

app = FastAPI()

class URLRequest(BaseModel):
    url: str

@app.post("/resolve")
async def resolve_captcha(req: URLRequest):
    url = req.url
    try:
        # Run the Playwright script asynchronously
        result = await run(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
