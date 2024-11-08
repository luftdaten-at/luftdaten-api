from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from models import Measurement, Values, HourlyAverages
from sqlalchemy import func

def calculate_hourly_average(station_id: int, db: Session):
    current_time = datetime.now()
    last_hour_start = current_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    last_hour_end = current_time.replace(minute=0, second=0, microsecond=0)

    average_values = db.query(
        Values.dimension,
        func.avg(Values.value).label("avg_value")
    ).join(Measurement).filter(
        Measurement.station_id == station_id,
        Measurement.time_measured >= last_hour_start,
        Measurement.time_measured < last_hour_end
    ).group_by(Values.dimension).all()

    for avg in average_values:
        hourly_avg = HourlyAverages(
            station_id=station_id,
            dimension=avg.dimension,
            avg_value=avg.avg_value,
            timestamp=last_hour_start
        )
        db.add(hourly_avg)

    db.commit()
