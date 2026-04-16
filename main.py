import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
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

class CORSHeaderMiddleware(BaseHTTPMiddleware):
    """Force CORS headers on every response, including preflight OPTIONS.
    Must be added LAST so it is innermost and intercepts requests first.
    """

    async def dispatch(self, request: Request, call_next):
        # Handle preflight directly without hitting the route
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                    "Access-Control-Max-Age": "3600",
                },
            )
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response


# CORSMiddleware goes first (outermost, runs last - handles non-OPTIONS CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# CORSHeaderMiddleware goes last (innermost, runs first - handles preflight OPTIONS)
app.add_middleware(CORSHeaderMiddleware)

app.include_router(analyze_router, prefix="/analyze", tags=["analyze"])
app.include_router(titles_router, prefix="/generate", tags=["generate"])
app.include_router(image_router, prefix="/image", tags=["image"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "winning-product-finder"}
