"""
Station management utilities.

This module handles station creation and updates.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from models import Station, Location
from schemas import StationDataCreate
from .geocoding import get_or_create_location
from .helpers import as_naive_utc


async def update_station_apikey_admin(db: AsyncSession, device: str, new_apikey: str) -> None:
    """Set ``apikey`` for an existing station (admin-only caller must be enforced by router)."""
    r = await db.execute(select(Station).where(Station.device == device))
    db_station = r.scalar_one_or_none()
    if db_station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        )
    db_station.apikey = new_apikey
    await db.commit()


async def get_or_create_station(db: AsyncSession, station: StationDataCreate):
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
    r = await db.execute(
        select(Station)
        .where(Station.device == station.device)
        .options(selectinload(Station.location))
    )
    db_station = r.scalar_one_or_none()

    if db_station is None:
        new_location = Location(
            lat=station.location.lat,
            lon=station.location.lon,
            height=float(station.location.height)
        )
        db.add(new_location)
        await db.flush()

        db_station = Station(
            device=station.device,
            firmware=station.firmware,
            apikey=station.apikey,
            location_id=new_location.id,
            last_active=as_naive_utc(station.time),
            source=station.source if station.source is not None else 1
        )
        db.add(db_station)
        await db.commit()
    else:
        if db_station.apikey != station.apikey:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        updated = False

        if db_station.location is None or (
            db_station.location.lat != station.location.lat or
            db_station.location.lon != station.location.lon or
            db_station.location.height != float(station.location.height)
        ):
            new_location = await get_or_create_location(
                db, station.location.lat, station.location.lon, float(station.location.height)
            )
            db_station.location_id = new_location.id
            updated = True

        if db_station.firmware != station.firmware:
            db_station.firmware = station.firmware
            updated = True

        if updated:
            await db.commit()

    return db_station
