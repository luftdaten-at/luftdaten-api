"""
Cache utilities for statistics and database operations.

This module provides functions to refresh materialized views and manage caching.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def refresh_statistics_views(db: Session):
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
        db.execute(text("SELECT refresh_statistics_views()"))
        db.commit()
        logger.info("Statistics materialized views refreshed successfully")
        return True
    except Exception as e:
        logger.error(f"Error refreshing statistics views: {e}")
        db.rollback()
        return False
