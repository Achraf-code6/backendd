import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/analyze", tags=["analyze"])
app.include_router(titles_router, prefix="/generate", tags=["generate"])
app.include_router(image_router, prefix="/image", tags=["image"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "winning-product-finder"}
