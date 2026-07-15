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
from api.routes import documents, senders, stats, monitor, chat, collections, config as config_router, items, contracts, services, feedback, low_value_rules, tax


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

    def _preload():
        try:
            load_model()
        except Exception as e:
            from api.routes import config as config_router
            config_router._load_error = str(e)

    threading.Thread(target=_preload, daemon=True, name="llm-preload").start()
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
app.include_router(services.router)
app.include_router(feedback.router)
app.include_router(low_value_rules.router)
app.include_router(tax.router)


@app.get("/health")
def health():
    return {"status": "ok", "db": DB_PATH}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# Serve static files of frontend if built
from fastapi.responses import FileResponse
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file_path = os.path.join(FRONTEND_DIST, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

