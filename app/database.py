from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import text, Index, Column, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import BigInteger, Text, TIMESTAMP
from typing import Optional, Any, Dict
from app.config import settings
from enum import Enum
from sqlalchemy import Enum as SqlEnum


engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class LogRecord(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    kind: Mapped[str] = mapped_column(Text)  # 'interaction' | 'network'
    body: Mapped[Dict[str, Any]] = mapped_column(JSONB)


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    fullname = Column(String, nullable=False)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    role = Column(SqlEnum(Role), nullable=False)

Index("ix_logs_ts", LogRecord.ts)
Index("ix_logs_kind", LogRecord.kind)

async def init_models():
    # Create tables
    from app.models.alert import Alert
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
