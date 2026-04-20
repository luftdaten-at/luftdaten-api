"""
Output formatting utilities.

This module provides functions to format data as CSV or JSON.
"""

import json
from itertools import groupby
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from models import Station, Location
from utils.helpers import format_datetime_vienna_iso


def standard_output_to_csv(data) -> str:
    """
    Convert data to CSV format.

    Args:
        data: list of tuples (Station.device, Measurement.time_measured, Values.dimension, Values.value)

    Returns:
        CSV string with header: device,time_measured,dimension,value
    """
    csv_data = "device,time_measured,dimension,value\n"
    for device, time, dim, val in data:
        csv_data += f"{device},{format_datetime_vienna_iso(time, timespec='minutes')},{dim},{val}\n"
    return csv_data


async def standard_output_to_json(data, db: AsyncSession, include_location=False):
    """
    Convert data to JSON format.

    Args:
        data: list of tuples (Station.device, Measurement.time_measured, Values.dimension, Values.value)
        db: Database session (required if include_location=True)
        include_location: If True, includes location coordinates in the output

    Returns:
        JSON string with array of measurement objects
    """
    groups = groupby(data, lambda x: (x[0], x[1]))
    json_data = [
        {
            "device": device,
            "time_measured": format_datetime_vienna_iso(time, timespec="minutes"),
            "values": [
                {
                    "dimension": dim,
                    "value": val
                }
                for (_, _, dim, val) in data
            ]
        }
        for ((device, time), data) in groups
    ]

    if include_location:
        for data_point in json_data:
            r = await db.execute(
                select(Station)
                .where(Station.device == data_point["device"])
                .options(selectinload(Station.location))
            )
            db_station = r.scalar_one_or_none()
            if db_station and db_station.location:
                db_location = db_station.location
                data_point["location"] = {
                    "lat": db_location.lat,
                    "lon": db_location.lon,
                    "height": db_location.height
                }

    return json.dumps(json_data)
