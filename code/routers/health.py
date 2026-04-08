from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from database import async_engine
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone

router = APIRouter()

scheduler: BackgroundScheduler = None


def set_scheduler(sched: BackgroundScheduler):
    """Set the scheduler reference for health checks"""
    global scheduler
    scheduler = sched


async def database_health_check():
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


@router.get("/", tags=["health"])
async def health_check():
    """
    Comprehensive health check endpoint.
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

    try:
        await database_health_check()
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "unhealthy"
        health_status["database_error"] = str(e)

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

    if health_status["status"] == "healthy":
        return health_status
    raise HTTPException(status_code=503, detail=health_status)


@router.get("/simple", tags=["health"])
async def simple_health_check():
    """
    Simple health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.3"
    }
