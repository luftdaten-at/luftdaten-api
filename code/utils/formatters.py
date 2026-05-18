"""
Output formatting utilities.

This module provides functions to format data as CSV or JSON.
"""

import csv
import json
from io import StringIO
from itertools import groupby
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from models import Station, Location
from utils.helpers import format_datetime_vienna_iso
from enums import Dimension


def _csv_cell_value(val, value_decimal_places: int | None) -> str | int | float:
    """Stringify a measurement value for CSV; optional fixed decimal places."""
    if value_decimal_places is None:
        return val if val is not None else f"{val}"
    if val is None:
        return ""
    return f"{float(val):.{value_decimal_places}f}"


def standard_output_to_csv(
    data,
    *,
    value_decimal_places: int | None = None,
    include_dimension_name: bool = False,
) -> str:
    """
    Convert data to CSV format.

    Args:
        data: list of tuples (Station.device, Measurement.time_measured, Values.dimension, Values.value)
        value_decimal_places: If set, numeric values are rounded to this many fractional digits.
        include_dimension_name: If True, adds a dimension_name column (from Dimension.get_name).

    Returns:
        CSV string with header: device,time_measured,dimension[,dimension_name],value
    """
    buf = StringIO()
    writer = csv.writer(buf)
    header = ["device", "time_measured", "dimension"]
    if include_dimension_name:
        header.append("dimension_name")
    header.append("value")
    writer.writerow(header)

    for device, time, dim, val in data:
        row = [
            device,
            format_datetime_vienna_iso(time, timespec="minutes"),
            dim,
        ]
        if include_dimension_name:
            row.append(Dimension.get_name(dim))
        row.append(_csv_cell_value(val, value_decimal_places))
        writer.writerow(row)

    return buf.getvalue()


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
