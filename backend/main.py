from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import config, dataset, ocr
from backend.services.credentials import store as credential_store

# Reconcile the tracing toggle at startup: sets WEAVE_DISABLED based on the
# persisted toggle, and runs weave.init only when the toggle is on AND all
# three credentials are present. Non-fatal if creds are missing.
credential_store.apply_tracing_setting()

app = FastAPI(
    title="OCR Notes API",
    description="API for converting handwritten notes to markdown",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(dataset.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
