from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import logging

# Configure basic logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Scalable Flight Price Intelligence System",
    version="1.0.0"
)

# CORS setup — always allow the production frontend
origins = ["*"]

if settings.env == "production":
    origins = [
        "https://i-fly-two.vercel.app",
        "https://ifly-fam5.onrender.com",
    ]
    # Also add any extra origins from env var
    if settings.cors_origins:
        for o in settings.cors_origins.split(","):
            o = o.strip()
            if o and o not in origins:
                origins.append(o)

logger.info(f"CORS origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import flight_search, price_prediction, system
app.include_router(flight_search.router)
app.include_router(price_prediction.router)
app.include_router(system.router)

@app.get("/health")
def health_check():
    """
    Basic health check endpoint to verify service is running.
    """
    return {"status": "ok", "environment": settings.env}
