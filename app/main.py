import os
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI(title="AI Meeting Assistant")

@app.get("/", response_class=PlainTextResponse)
def root():
    return "ok"

@app.get("/healthz")
def healthz():
    return JSONResponse({"status": "ok"})
