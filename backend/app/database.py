import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
URL = os.getenv("DATABASE_URL", "sqlite:///./jobmatch.db")  # swap for postgresql://... later
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
