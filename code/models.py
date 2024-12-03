from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from database import Base

from slugify import slugify


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)
    code = Column(String, unique=True, index=True)
    # Relationships:
    cities = relationship("City", back_populates="country")

    def __init__(self, name, code):
        self.name = name
        self.slug = slugify(name)
        self.code = code


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    slug = Column(String, unique=True, index=True)
    tz = Column(String, nullable=True)
    # Relationships:
    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship("Country", back_populates="cities")
    locations = relationship("Location", back_populates="city")

    lat = Column(Float)
    lon = Column(Float)

    def __init__(self, name, country_id, tz, lat, lon):
        self.name = name
        self.slug = slugify(name)
        self.country_id = country_id
        self.tz = tz
        self.lat = lat
        self.lon = lon


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    lat = Column(Float)
    lon = Column(Float)
    height = Column(Float)
    # Relationships:
    city_id = Column(Integer, ForeignKey('cities.id'))
    city = relationship("City", back_populates="locations")
    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship("Country")
    stations = relationship("Station", back_populates="location")
    measurements = relationship("Measurement", back_populates="location")


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    device = Column(String, index=True, unique=True)
    firmware = Column(String)
    apikey = Column(String)
    last_active = Column(DateTime)
    source = Column(Integer)
    # Relationships:
    location_id = Column(Integer, ForeignKey('locations.id'))
    location = relationship("Location", back_populates="stations")
    measurements = relationship("Measurement", back_populates="station")
    hourly_avg = relationship("HourlyDimensionAverages", back_populates="station")
    stationStatus = relationship("StationStatus", back_populates="station")


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    time_received = Column(DateTime)
    time_measured = Column(DateTime)
    sensor_model = Column(Integer)
    # Relationships:
    location_id = Column(Integer, ForeignKey('locations.id'))
    location = relationship("Location", back_populates="measurements")
    station_id = Column(Integer, ForeignKey('stations.id'))
    station = relationship("Station", back_populates="measurements")
    values = relationship("Values", back_populates="measurement")


class Values(Base):
    __tablename__ = "values"

    id = Column(Integer, primary_key=True, index=True)
    dimension = Column(Integer)
    value = Column(Float)
    # Relationships:
    measurement_id = Column(Integer, ForeignKey('measurements.id'))
    measurement = relationship("Measurement", back_populates="values")


class StationStatus(Base):
    __tablename__ = "stationStatus"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey('stations.id'))
    station = relationship("Station", back_populates="stationStatus")
    timestamp = Column(DateTime)
    level = Column(Integer)
    message = Column(String)

class HourlyDimensionAverages(Base):
    __tablename__ = 'hourly_avg'  # This should match your view name in PostgreSQL

    station_id = Column(Integer, ForeignKey('stations.id'), primary_key=True)  # Assuming 'station_id' uniquely identifies the record
    station = relationship("Station", back_populates="hourly_avg")
    hour = Column(DateTime, primary_key=True)       # Hour as a datetime truncated to hour precision
    dimension_avg = Column(JSON)                    # JSON column to store {dimension_id: avg_value} dictionary
