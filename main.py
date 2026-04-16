import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routes.analyze import router as analyze_router
from routes.titles import router as titles_router
from routes.image import router as image_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Winning Product Finder API...")
    yield
    print("🛑 Shutting down...")


app = FastAPI(
    title="Winning Product Finder API",
    description="Backend API for the Winning Product Finder Chrome Extension",
    version="1.0.0",
    lifespan=lifespan,
)

# Extended CORS origins for extension
ALLOWED_ORIGINS = [
    "*",
    "chrome-extension://mnkmbpipbambiodijgacabmppocfpglm",  # Your extension ID will vary
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Handle OPTIONS for preflight requests explicitly
@app.options("/{full_path:path}")
async def options_handler(full_path: str, request: Request):
    return JSONResponse(
        status_code=200,
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
    )

app.include_router(analyze_router, prefix="/analyze", tags=["analyze"])
app.include_router(titles_router, prefix="/generate", tags=["generate"])
app.include_router(image_router, prefix="/image", tags=["image"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "winning-product-finder"}
