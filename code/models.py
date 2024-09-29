from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    lat = Column(Float)
    lon = Column(Float)
    height = Column(Float)
    # Relationships:
    stations = relationship("Station", back_populates="location")
    measurements = relationship("Measurement", back_populates="location")


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    device = Column(String, index=True, unique=True)
    firmware = Column(String)
    apikey = Column(String)
    last_active = Column(DateTime)
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
    

# class City(Base):
#     __tablename__ = "cities"

#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, unique=True, index=True)
    