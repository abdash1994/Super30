"""A tiny API used to compare Docker image sizes.

The app itself is deliberately small: the lab is about what we ship around it.
"""
from fastapi import FastAPI

app = FastAPI(title="Lab 01: slim images")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/quote")
def quote() -> dict:
    return {"quote": "Ship the machine, not the setup guide."}
