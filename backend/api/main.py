from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
import storage
from config import DB_PATH
from api.routes import documents, senders, stats, monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    db.init_db()
    storage.load_sender_registry()
    yield
    # Shutdown actions (none currently required)


app = FastAPI(
    title="Document Archiver API",
    description="REST API fuer das private Dokumentenarchiv",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(documents.router)
app.include_router(senders.router)
app.include_router(stats.router)
app.include_router(monitor.router)


@app.get("/health")
def health():
    return {"status": "ok", "db": DB_PATH}
