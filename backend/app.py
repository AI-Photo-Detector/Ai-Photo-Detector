import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency may be absent in minimal installs
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from backend.routes import router as api_router

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="AI Photo Detector API",
    version="0.1.0",
)

_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

allowed_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "").split(",")
    if o.strip()
] or _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    app_env = os.getenv("APP_ENV", "development")
    logger.info(
        "Starting API in env=%s loaded_modules=%s",
        app_env,
        [
            "backend.routes",
            "backend.detector.preprocess",
            "backend.detector.predict",
            "backend.detector.postprocess",
        ],
    )
