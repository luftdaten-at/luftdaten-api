from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
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

    def __init__(self, name, country_id, tz):
        self.name = name
        self.slug = slugify(name)
        self.country_id = country_id
        self.tz = tz


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


class HourlyAverages(Base):
    __tablename__ = "hourly_averages"
    
    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey('stations.id'))
    station = relationship("Station")
    avg_value = Column(Float)
    sensor_model = Column(Integer)
    dimension = Column(Integer)
    timestamp = Column(DateTime)


class StationStatus(Base):
    __tablename__ = "StationStatus"

    id = Column(Integer, primary_key=True, index=True)
    Column(Integer, ForeignKey('stations.id'))
    timestamp = Column(DateTime)
    level = Column(Integer)
    message = Column(String)
