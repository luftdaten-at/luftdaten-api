import asyncio
import logging
import requests
from database import SchedulerAsyncSessionLocal
from services.data_service import sensor_community_import_grouped_by_location
from enums import Source
from utils.cache import refresh_statistics_views, refresh_stations_summary

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def import_sensor_community_data():
    """
    Import from sensor.community
    """
    logger.info("Task 'import_sensor_community_data' started.")

    url = "https://data.sensor.community/static/v1/data.json"
    try:
        response = requests.get(url)
        logger.debug(f"Request sent to {url}, Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch data from {url}: {e}")
        return

    if response.status_code == 200:
        try:
            data = response.json()
            logger.info("Data successfully fetched and parsed from sensor.community.")
        except ValueError as e:
            logger.error(f"Error parsing JSON response: {e}")
            return

        async def _run_import():
            async with SchedulerAsyncSessionLocal() as db:
                await sensor_community_import_grouped_by_location(db, data, source=Source.SC)

        try:
            asyncio.run(_run_import())
            logger.info("Data processed and imported successfully.")
        except Exception as e:
            logger.error(f"Error processing and importing data: {e}")
    else:
        logger.error(f"Failed to fetch data: Status Code {response.status_code}")


def refresh_statistics_cache():
    """
    Refresh all statistics materialized views.
    """
    logger.info("Task 'refresh_statistics_cache' started.")

    async def _run():
        async with SchedulerAsyncSessionLocal() as db:
            await refresh_statistics_views(db)

    try:
        asyncio.run(_run())
        logger.info("Statistics materialized views refreshed successfully.")
    except Exception as e:
        logger.error(f"Error refreshing statistics views: {e}")


def refresh_stations_summary_cache():
    """
    Refresh the stations_summary materialized view.
    """
    logger.info("Task 'refresh_stations_summary_cache' started.")

    async def _run():
        async with SchedulerAsyncSessionLocal() as db:
            await refresh_stations_summary(db)

    try:
        asyncio.run(_run())
        logger.info("Stations summary materialized view refreshed successfully.")
    except Exception as e:
        logger.error(f"Error refreshing stations summary view: {e}")
