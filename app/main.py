from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import connect_db, disconnect_db
from app.api.v1.api import api_router


load_dotenv()

app = FastAPI(title="Profit Sharing API (FastAPI)")


@app.on_event("startup")
async def startup_event() -> None:
    await connect_db()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await disconnect_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {"status": "ok"}


app.include_router(api_router)
