from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Створюємо файл бази даних shelter.db у папці local_server
SQLALCHEMY_DATABASE_URL = "sqlite:///./shelter.db"

# connect_args потрібен тільки для SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()