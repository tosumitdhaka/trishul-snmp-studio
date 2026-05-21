from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BundleObject(Base):
    __tablename__ = "bundle_objects"
    __table_args__ = (
        UniqueConstraint(
            "bundle_set_id",
            "module_name",
            "object_name",
            name="uq_bundle_objects_bundle_module_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_set_id: Mapped[int] = mapped_column(
        ForeignKey("bundle_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bundle_module_id: Mapped[int | None] = mapped_column(
        ForeignKey("bundle_modules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    module_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    oid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    object_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nodetype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    syntax: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_access: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    augments: Mapped[str | None] = mapped_column(String(255), nullable=True)
    constraints_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BundleNotification(Base):
    __tablename__ = "bundle_notifications"
    __table_args__ = (
        UniqueConstraint(
            "bundle_set_id",
            "module_name",
            "notification_name",
            name="uq_bundle_notifications_bundle_module_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_set_id: Mapped[int] = mapped_column(
        ForeignKey("bundle_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bundle_module_id: Mapped[int | None] = mapped_column(
        ForeignKey("bundle_modules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    module_name: Mapped[str] = mapped_column(String(255), nullable=False)
    notification_name: Mapped[str] = mapped_column(String(255), nullable=False)
    oid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    object_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    members_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
