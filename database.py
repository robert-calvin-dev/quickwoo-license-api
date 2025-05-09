from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_URL", "sqlite:///./licenses.db")

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables on first run
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

