"""
Output formatting utilities.

This module provides functions to format data as CSV or JSON.
"""

import json
from itertools import groupby
from models import Station, Location


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
        csv_data += f"{device},{time.strftime("%Y-%m-%dT%H:%M")},{dim},{val}\n"
    return csv_data


def standard_output_to_json(data, db, include_location=False):
    """
    Convert data to JSON format.
    
    Args:
        data: list of tuples (Station.device, Measurement.time_measured, Values.dimension, Values.value)
        db: Database session (required if include_location=True)
        include_location: If True, includes location coordinates in the output
    
    Returns:
        JSON string with array of measurement objects
    
    Example output:
    [
        {
            "device": "75509",
            "time_measured": "2024-11-29T08:18",
            "values": [
                {
                    "dimension": 7,
                    "value": 28.32
                }
            ]
        }
    ]
    """
    groups = groupby(data, lambda x: (x[0], x[1]))
    json_data = [
        {
            "device": device,
            "time_measured": time.strftime("%Y-%m-%dT%H:%M"),
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
            db_station = db.query(Station).filter(Station.device == data_point["device"]).first()
            db_location = db.query(Location).filter(Location.id == db_station.location.id).first()
            data_point["location"] = {
                "lat": db_location.lat,
                "lon": db_location.lon,
                "height": db_location.height
            }

    return json.dumps(json_data)
