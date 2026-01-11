"""
Station management utilities.

This module handles station creation and updates.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import Station, Location
from schemas import StationDataCreate
from .geocoding import get_or_create_location


def get_or_create_station(db: Session, station: StationDataCreate):
    """
    Get existing station or create a new one.
    
    If the station exists, validates the API key and updates location/firmware if needed.
    If it doesn't exist, creates a new station and location.
    
    Args:
        db: Database session
        station: Station data from request
    
    Returns:
        Station object
    
    Raises:
        HTTPException: If API key is invalid (401)
    """
    # Check if station already exists
    db_station = db.query(Station).filter(Station.device == station.device).first()

    if db_station is None:
        # Create new station and new location
        new_location = Location(
            lat=station.location.lat,
            lon=station.location.lon,
            height=float(station.location.height)
        )
        db.add(new_location)
        db.commit()
        db.refresh(new_location)

        # Create new station and check source field (default is 1)
        db_station = Station(
            device=station.device,
            firmware=station.firmware,
            apikey=station.apikey,
            location_id=new_location.id,
            last_active=station.time,
            source=station.source if station.source is not None else 1
        )
        db.add(db_station)
        db.commit()
        db.refresh(db_station)
    else:
        # Station exists, validate API key
        if db_station.apikey != station.apikey:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        updated = False

        # Check if location needs to be updated
        if db_station.location is None or (
            db_station.location.lat != station.location.lat or 
            db_station.location.lon != station.location.lon or
            db_station.location.height != float(station.location.height)
        ):
            new_location = get_or_create_location(db, station.location.lat, station.location.lon, float(station.location.height))
            db_station.location_id = new_location.id
            updated = True

        if db_station.firmware != station.firmware:
            db_station.firmware = station.firmware
            updated = True

        if updated:
            db.commit()

    return db_station
