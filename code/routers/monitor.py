"""
Monitoring endpoint for database usage, API stats, and application metrics.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sqlalchemy import text

from database import async_engine
from middleware.request_stats import get_request_stats
from utils.helpers import format_datetime_vienna_iso

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", tags=["monitor"])
async def get_monitor(request: Request):
    """
    Get monitoring data: database usage, API endpoint stats, application metrics.
    """
    result = {
        "timestamp": format_datetime_vienna_iso(datetime.now(timezone.utc)),
        "version": "0.3",
        "database": await _get_database_metrics(),
        "api": get_request_stats(),
        "application": _get_application_metrics(request),
    }
    return result


async def _get_database_metrics() -> dict:
    """Query PostgreSQL for database usage metrics."""
    try:
        async with async_engine.connect() as conn:
            size_row = (
                await conn.execute(text("SELECT pg_database_size(current_database()) as size"))
            ).fetchone()
            size_bytes = size_row.size if size_row else 0

            conn_rows = (
                await conn.execute(text("""
                    SELECT state, count(*) as cnt
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    GROUP BY state
                """))
            ).fetchall()
            conn_map = {str(r.state) if r.state else "unknown": r.cnt for r in conn_rows}
            active = conn_map.get("active", 0)
            idle = conn_map.get("idle", 0) + conn_map.get("idle in transaction", 0)
            total = sum(conn_map.values())

            db_stat = (
                await conn.execute(text("""
                    SELECT blks_hit, blks_read, xact_commit, xact_rollback
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """))
            ).fetchone()

            blks_hit = db_stat.blks_hit or 0
            blks_read = db_stat.blks_read or 0
            total_blks = blks_hit + blks_read
            cache_hit_ratio = round(blks_hit / total_blks, 4) if total_blks > 0 else 1.0

            xact_commit = db_stat.xact_commit or 0
            xact_rollback = db_stat.xact_rollback or 0

            table_rows = (
                await conn.execute(text("""
                    SELECT
                        relname as table_name,
                        pg_total_relation_size(c.oid) as size_bytes
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relkind = 'r'
                    ORDER BY pg_total_relation_size(c.oid) DESC
                    LIMIT 10
                """))
            ).fetchall()

            top_tables = [
                {"table": r.table_name, "size_bytes": r.size_bytes}
                for r in table_rows
            ]

            return {
                "size_bytes": size_bytes,
                "connections": {
                    "active": active,
                    "idle": idle,
                    "total": total,
                },
                "cache_hit_ratio": cache_hit_ratio,
                "transactions": {
                    "committed": xact_commit,
                    "rolled_back": xact_rollback,
                },
                "top_tables": top_tables,
            }
    except Exception as e:
        logger.warning("Failed to fetch database metrics: %s", e)
        return {
            "size_bytes": None,
            "connections": {"active": None, "idle": None, "total": None},
            "cache_hit_ratio": None,
            "transactions": {"committed": None, "rolled_back": None},
            "top_tables": [],
            "error": str(e),
        }


def _get_application_metrics(request: Request) -> dict:
    """Get application-level metrics from app state."""
    app = request.app
    uptime_seconds = None
    if hasattr(app.state, "start_time"):
        uptime_seconds = int((datetime.now(timezone.utc) - app.state.start_time).total_seconds())

    scheduler_jobs = 0
    try:
        from routers.health import scheduler
        if scheduler and scheduler.running:
            scheduler_jobs = len(scheduler.get_jobs())
    except Exception:
        pass

    blacklist_size = 0
    if hasattr(app.state, "blacklisted_station_ids"):
        blacklist_size = len(app.state.blacklisted_station_ids)

    return {
        "uptime_seconds": uptime_seconds,
        "scheduler_jobs": scheduler_jobs,
        "blacklist_size": blacklist_size,
    }
