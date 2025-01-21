import logging
import requests
from database import get_db
from services.data_service import process_and_import_data, sensorcommunity_import_grouped_by_location
from enums import Source

# Logging-Konfiguration
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
        
        try:
            db = next(get_db())  # Öffne die Datenbank-Session

        except Exception as e:
            logger.error(f"Failed to open database session: {e}")
            return

        try:
            sensorcommunity_import_grouped_by_location(db, data, source=Source.SC)  # Verarbeite und speichere die Daten
            logger.info("Data processed and imported successfully.")
        except Exception as e:
            logger.error(f"Error processing and importing data: {e}")
        finally:
            db.close()
            logger.debug("Database session closed.")
    else:
        logger.error(f"Failed to fetch data: Status Code {response.status_code}")