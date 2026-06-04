import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock

from utils.geocoding import (
    _locality_from_address,
    _city_coords,
    get_or_create_location,
    reverse_geocode,
)
from models import Location, Country
from db_testing import TestAsyncSessionLocal
from sqlalchemy import select


class TestLocalityFromAddress:
    def test_prefers_city_over_municipality(self):
        address = {"city": "Vienna", "municipality": "Wien"}
        assert _locality_from_address(address) == "Vienna"

    def test_falls_back_to_municipality(self):
        address = {"municipality": "Bruxelles - Brussel", "country": "Belgium"}
        assert _locality_from_address(address) == "Bruxelles - Brussel"

    def test_falls_back_through_chain(self):
        assert _locality_from_address({"borough": "Mitte"}) == "Mitte"
        assert _locality_from_address({"hamlet": "Kleindorf"}) == "Kleindorf"
        assert _locality_from_address({"county": "Rural County"}) == "Rural County"

    def test_returns_none_when_no_locality_keys(self):
        assert _locality_from_address({"country": "Belgium", "road": "Rue Example"}) is None


class TestCityCoords:
    def test_uses_geocode_result_when_found(self):
        geolocator = MagicMock()
        geolocator.geocode.return_value = MagicMock(latitude=50.85, longitude=4.35)
        assert _city_coords(geolocator, "Brussels", 50.8353, 4.38886) == (50.85, 4.35)

    def test_falls_back_to_station_coords_when_geocode_returns_none(self):
        geolocator = MagicMock()
        geolocator.geocode.return_value = None
        assert _city_coords(geolocator, "Unknown", 50.8353, 4.38886) == (50.8353, 4.38886)


class TestReverseGeocode:
    def test_uses_municipality_when_city_missing(self):
        mock_location = MagicMock()
        mock_location.raw = {
            "address": {
                "municipality": "Bruxelles - Brussel",
                "country": "Belgium",
                "country_code": "be",
            }
        }
        geolocator = MagicMock()
        geolocator.reverse.return_value = mock_location
        with patch("utils.geocoding.Nominatim", return_value=geolocator):
            city, country, code = reverse_geocode(50.8353, 4.38886)
        assert city == "Bruxelles - Brussel"
        assert country == "Belgium"
        assert code == "be"


class TestGetOrCreateLocation:
    def test_country_only_when_city_name_missing(self):
        async def _run():
            async with TestAsyncSessionLocal() as db:
                with patch(
                    "utils.geocoding.reverse_geocode",
                    return_value=(None, "Belgium", "be"),
                ):
                    loc = await get_or_create_location(db, 50.8353, 4.38886, 120.0)

                assert loc.lat == 50.8353
                assert loc.lon == 4.38886
                assert loc.height == 120.0
                assert loc.city_id is None
                assert loc.country_id is not None

                r = await db.execute(select(Country).where(Country.id == loc.country_id))
                country = r.scalar_one()
                assert country.name == "Belgium"

        asyncio.run(_run())

    def test_coords_only_when_country_missing(self):
        async def _run():
            async with TestAsyncSessionLocal() as db:
                with patch(
                    "utils.geocoding.reverse_geocode",
                    return_value=(None, None, None),
                ):
                    loc = await get_or_create_location(db, 1.0, 2.0, 3.0)

                assert loc.city_id is None
                assert loc.country_id is None

        asyncio.run(_run())

    def test_updates_existing_location_without_city(self):
        async def _run():
            async with TestAsyncSessionLocal() as db:
                existing = Location(lat=50.8353, lon=4.38886, height=120.0)
                db.add(existing)
                await db.commit()
                await db.refresh(existing)

                with patch(
                    "utils.geocoding.reverse_geocode",
                    return_value=(None, "Belgium", "be"),
                ):
                    loc = await get_or_create_location(db, 50.8353, 4.38886, 120.0)

                assert loc.id == existing.id
                assert loc.city_id is None
                assert loc.country_id is not None

        asyncio.run(_run())
