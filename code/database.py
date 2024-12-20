from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

import os

# Umgebungsvariablen auslesen
DB_USER = os.getenv("POSTGRES_USER", "")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_NAME = os.getenv("POSTGRES_DB", "")

# Erstellen der korrekten DATABASE_URL mit f-String
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# Engine und Session erstellen
engine = create_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Basis-Model für die Deklaration der Datenbanktabellen
Base = declarative_base()

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
