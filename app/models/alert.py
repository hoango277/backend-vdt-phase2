from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, String, Text, TIMESTAMP
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[Optional[str]] = mapped_column(String)
    timestamp: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    severity: Mapped[Optional[str]] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String, default="new", nullable=False
    )  # new, in_progress, resolved, false_positive
    assignee: Mapped[Optional[str]] = mapped_column(String)  # người xử lý cảnh báo
    notes: Mapped[Optional[str]] = mapped_column(Text)       # ghi chú analyst
