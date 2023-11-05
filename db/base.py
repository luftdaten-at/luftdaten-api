from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import DeclarativeBase
from core.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
Base = DeclarativeBase()