from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

import os

import db
import storage
import config
from config import DB_PATH, CORS_ORIGINS
from api.routes import documents, senders, stats, monitor, chat, collections, config as config_router, items, contracts


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    os.makedirs(config.SOURCE_DIR, exist_ok=True)
    db.init_db()
    storage.load_sender_registry()
    import feedback as fb
    fb._migrate_from_json()
    import threading
    from llm import load_model, assert_gpu_support
    if not config.MOCK_LLM:
        assert_gpu_support()
    threading.Thread(target=load_model, daemon=True, name="llm-preload").start()
    yield
    # Shutdown actions (none currently required)


app = FastAPI(
    title="Document Archiver API",
    description="REST API fuer das private Dokumentenarchiv",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = logging.getLogger("papervault")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unbehandelte Exception bei %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Interner Serverfehler"})


app.include_router(documents.router)
app.include_router(senders.router)
app.include_router(stats.router)
app.include_router(monitor.router)
app.include_router(chat.router)
app.include_router(collections.router)
app.include_router(config_router.router)
app.include_router(items.router)
app.include_router(contracts.router)


@app.get("/health")
def health():
    return {"status": "ok", "db": DB_PATH}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
