from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers.subscriptions import router as subscriptions_router
from routers.analytics import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables automatically if they don't exist
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="BrightLoop Backend - Quotations & Subscriptions API",
    description="Unified subscription and quotation lifecycle management module for BrightLoop.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Next.js frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(subscriptions_router, prefix="/api")
app.include_router(subscriptions_router)  # Direct root routes for flexible API consumption
app.include_router(analytics_router, prefix="/api")
app.include_router(analytics_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "BrightLoop Quotations & Subscriptions API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
