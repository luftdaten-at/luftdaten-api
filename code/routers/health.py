from fastapi import APIRouter, HTTPException
from database import engine
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone

router = APIRouter()

# Global scheduler reference - will be set from main.py
scheduler: BackgroundScheduler = None

def set_scheduler(sched: BackgroundScheduler):
    """Set the scheduler reference for health checks"""
    global scheduler
    scheduler = sched

@router.get("/", tags=["health"])
async def health_check():
    """
    Health check endpoint to verify the API status, database connectivity, and scheduler status.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.3",
        "checks": {
            "api": "healthy",
            "database": "unknown",
            "scheduler": "unknown"
        }
    }
    
    # Check database connectivity
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "unhealthy"
        health_status["database_error"] = str(e)
    
    # Check scheduler status
    try:
        if scheduler and scheduler.running:
            health_status["checks"]["scheduler"] = "healthy"
            health_status["scheduler_jobs"] = len(scheduler.get_jobs())
        else:
            health_status["checks"]["scheduler"] = "unhealthy"
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["checks"]["scheduler"] = "unhealthy"
        health_status["status"] = "unhealthy"
        health_status["scheduler_error"] = str(e)
    
    # Return appropriate HTTP status code
    if health_status["status"] == "healthy":
        return health_status
    else:
        raise HTTPException(status_code=503, detail=health_status)

@router.get("/simple", tags=["health"])
async def simple_health_check():
    """
    Simple health check endpoint that only checks if the API is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.3"
    }
