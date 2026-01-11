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
    Comprehensive health check endpoint.
    
    Checks the status of the API, database connectivity, and background scheduler.
    Returns detailed information about each component's health status.
    
    **Response:**
    JSON object containing:
    - **status**: Overall status ('healthy' or 'unhealthy')
    - **timestamp**: Current UTC timestamp (ISO format)
    - **version**: API version
    - **checks**: Object with individual component statuses:
      - **api**: Always 'healthy' if endpoint is reachable
      - **database**: 'healthy' if connection successful, 'unhealthy' otherwise
      - **scheduler**: 'healthy' if scheduler is running, 'unhealthy' otherwise
    - **scheduler_jobs**: Number of scheduled jobs (if scheduler is healthy)
    - **database_error**: Error message if database check failed (optional)
    - **scheduler_error**: Error message if scheduler check failed (optional)
    
    **Example Healthy Response:**
    ```json
    {
      "status": "healthy",
      "timestamp": "2024-01-01T12:00:00Z",
      "version": "0.3",
      "checks": {
        "api": "healthy",
        "database": "healthy",
        "scheduler": "healthy"
      },
      "scheduler_jobs": 1
    }
    ```
    
    **Example Unhealthy Response:**
    ```json
    {
      "status": "unhealthy",
      "timestamp": "2024-01-01T12:00:00Z",
      "version": "0.3",
      "checks": {
        "api": "healthy",
        "database": "unhealthy",
        "scheduler": "healthy"
      },
      "scheduler_jobs": 1,
      "database_error": "Connection refused"
    }
    ```
    
    **HTTP Status Codes:**
    - 200: All systems healthy
    - 503: One or more systems unhealthy (Service Unavailable)
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
    Simple health check endpoint.
    
    Lightweight endpoint that only verifies the API is running and responding.
    Does not check database or scheduler status. Useful for load balancers and
    monitoring systems that need fast response times.
    
    **Response:**
    JSON object containing:
    - **status**: Always 'healthy' if endpoint is reachable
    - **timestamp**: Current UTC timestamp (ISO format)
    - **version**: API version
    
    **Example Response:**
    ```json
    {
      "status": "healthy",
      "timestamp": "2024-01-01T12:00:00Z",
      "version": "0.3"
    }
    ```
    
    **HTTP Status Code:**
    - 200: API is running (always returns this if endpoint is reachable)
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.3"
    }
