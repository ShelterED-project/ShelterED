from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import config

# Файл бази даних задає LOCAL_DB_PATH (за замовчуванням ./shelter.db)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{config.LOCAL_DB_PATH}"

# check_same_thread=False: базою користуються і запити, і фоновий потік синхронізації
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 15}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
