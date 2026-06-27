import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
import storage
from config import DB_PATH
from api.routes import documents, senders, stats, monitor

app = FastAPI(
    title="Document Archiver API",
    description="REST API fuer das private Dokumentenarchiv",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()
    storage.load_sender_registry()


app.include_router(documents.router)
app.include_router(senders.router)
app.include_router(stats.router)
app.include_router(monitor.router)


@app.get("/health")
def health():
    return {"status": "ok", "db": DB_PATH}
