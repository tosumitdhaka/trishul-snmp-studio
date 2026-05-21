from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("bundle_sets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    pdu_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    community: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_host: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_host: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    target_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notification_oid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notification_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notification_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    uptime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_hex: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
