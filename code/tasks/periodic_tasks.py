import requests
from database import get_db
from celery import shared_task
from services.data_service import process_and_import_data

@shared_task
def import_sensor_community_data():
    """
    Import from sensor.community
    """
    url = "https://data.sensor.community/static/v1/data.json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # Öffne die Datenbank-Session
        db = next(get_db())
        process_and_import_data(db, data, source = 3)
        db.close()