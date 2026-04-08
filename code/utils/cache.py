"""
Cache utilities for statistics and database operations.

This module provides functions to refresh materialized views and manage caching.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


async def refresh_statistics_views(db: AsyncSession):
    """
    Refresh all statistics materialized views concurrently.

    This function calls the PostgreSQL function to refresh all materialized views
    used by the statistics endpoint. Uses CONCURRENTLY to avoid locking tables.

    Args:
        db: Database session

    Returns:
        True if successful, False otherwise
    """
    try:
        await db.execute(text("SELECT refresh_statistics_views()"))
        await db.commit()
        logger.info("Statistics materialized views refreshed successfully")
        return True
    except Exception as e:
        logger.error(f"Error refreshing statistics views: {e}")
        await db.rollback()
        return False


async def refresh_stations_summary(db: AsyncSession):
    """
    Refresh the stations_summary materialized view concurrently.

    This function calls the PostgreSQL function to refresh the stations_summary
    materialized view used by the /stations/all endpoint. Uses CONCURRENTLY to avoid locking tables.

    Args:
        db: Database session

    Returns:
        True if successful, False otherwise
    """
    try:
        await db.execute(text("SELECT refresh_stations_summary()"))
        await db.commit()
        logger.info("Stations summary materialized view refreshed successfully")
        return True
    except Exception as e:
        logger.error(f"Error refreshing stations summary view: {e}")
        await db.rollback()
        return False
