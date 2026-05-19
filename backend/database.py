from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# DATA_DIR poate fi suprascris prin env var (ex: Fly.io setează DATA_DIR=/data)
# Fallback: directorul `data/` din rădăcina proiectului (dev local)
DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data")
)
DB_PATH = os.path.join(DATA_DIR, "planning.db")
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
