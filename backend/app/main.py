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

# Environment-aware CORS setup
if settings.env == "production" and settings.cors_origins:
    origins = [o.strip() for o in settings.cors_origins.split(",")]
else:
    origins = ["*"]

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
