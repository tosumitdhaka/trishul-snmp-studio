from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, false, func, or_, select, text

from app.core.config import Settings, get_settings
from app.db.session import create_session_factory
from app.models import NotificationEvent

_ALLOWED_DIRECTIONS = {"received", "sent", "decoded"}
_SEARCH_TOKEN_RE = re.compile(r"[0-9A-Za-z_:-]+")


class EventHistoryServiceError(RuntimeError):
    """Raised when notification history operations fail."""


class EventHistoryService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.session_factory = create_session_factory(self.settings.database_url)

    def record_event(
        self,
        *,
        direction: str,
        pdu_type: str,
        event: dict[str, Any],
        bundle_set_id: int | None = None,
        request_id: int | None = None,
        community: str | None = None,
        source_host: str | None = None,
        source_port: int | None = None,
        target_host: str | None = None,
        target_port: int | None = None,
        notification_oid: str | None = None,
        notification_name: str | None = None,
        notification_description: str | None = None,
        uptime: int | None = None,
        payload_hex: str | None = None,
        recorded_at: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_direction = direction.strip().lower()
        if normalized_direction not in _ALLOWED_DIRECTIONS:
            raise EventHistoryServiceError(
                "direction must be one of: received, sent, decoded."
            )
        normalized_pdu_type = pdu_type.strip()
        if not normalized_pdu_type:
            raise EventHistoryServiceError("pdu_type cannot be empty.")
        if not isinstance(event, dict):
            raise EventHistoryServiceError("event must be a JSON object payload.")
        if payload_hex is not None and not isinstance(payload_hex, str):
            raise EventHistoryServiceError("payload_hex must be a string when provided.")

        row_recorded_at = recorded_at or datetime.now(timezone.utc)
        normalized_event = dict(event)

        with self.session_factory() as session:
            row = NotificationEvent(
                bundle_set_id=bundle_set_id,
                direction=normalized_direction,
                pdu_type=normalized_pdu_type,
                request_id=request_id,
                community=community,
                source_host=source_host,
                source_port=source_port,
                target_host=target_host,
                target_port=target_port,
                notification_oid=notification_oid,
                notification_name=notification_name,
                notification_description=notification_description,
                uptime=uptime,
                payload_hex=payload_hex,
                event_json=normalized_event,
                recorded_at=row_recorded_at,
            )
            session.add(row)
            session.flush()
            session.execute(
                text(
                    """
                    INSERT INTO notification_event_search (
                        event_id,
                        bundle_set_id,
                        direction,
                        pdu_type,
                        community,
                        source_host,
                        target_host,
                        notification_name,
                        notification_oid,
                        notification_description,
                        event_text
                    ) VALUES (
                        :event_id,
                        :bundle_set_id,
                        :direction,
                        :pdu_type,
                        :community,
                        :source_host,
                        :target_host,
                        :notification_name,
                        :notification_oid,
                        :notification_description,
                        :event_text
                    )
                    """
                ),
                {
                    "event_id": str(row.id),
                    "bundle_set_id": "" if row.bundle_set_id is None else str(row.bundle_set_id),
                    "direction": row.direction,
                    "pdu_type": row.pdu_type,
                    "community": row.community or "",
                    "source_host": row.source_host or "",
                    "target_host": row.target_host or "",
                    "notification_name": row.notification_name or "",
                    "notification_oid": row.notification_oid or "",
                    "notification_description": row.notification_description or "",
                    "event_text": json.dumps(normalized_event, ensure_ascii=True, sort_keys=True),
                },
            )
            session.commit()
            session.refresh(row)
            return self._decorate_event(row)

    def list_events(
        self,
        *,
        q: str | None = None,
        direction: str | None = None,
        pdu_type: str | None = None,
        community: str | None = None,
        notification: str | None = None,
        source_host: str | None = None,
        target_host: str | None = None,
        bundle_set_id: int | None = None,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        self._validate_paging(limit=limit, offset=offset)

        normalized_query = (q or "").strip().lower()
        normalized_direction = (direction or "").strip().lower() or None
        normalized_pdu_type = (pdu_type or "").strip() or None
        normalized_community = (community or "").strip()
        normalized_notification = (notification or "").strip().lower()
        normalized_source_host = (source_host or "").strip().lower()
        normalized_target_host = (target_host or "").strip().lower()

        if normalized_direction is not None and normalized_direction not in _ALLOWED_DIRECTIONS:
            raise EventHistoryServiceError(
                "direction must be one of: received, sent, decoded."
            )

        with self.session_factory() as session:
            stmt = select(NotificationEvent).order_by(
                NotificationEvent.recorded_at.desc(),
                NotificationEvent.id.desc(),
            )
            if bundle_set_id is not None:
                stmt = stmt.where(NotificationEvent.bundle_set_id == bundle_set_id)
            if normalized_direction is not None:
                stmt = stmt.where(NotificationEvent.direction == normalized_direction)
            if normalized_pdu_type is not None:
                stmt = stmt.where(NotificationEvent.pdu_type == normalized_pdu_type)
            if normalized_community:
                stmt = stmt.where(NotificationEvent.community.ilike(f"%{normalized_community}%"))
            if normalized_notification:
                pattern = f"%{normalized_notification}%"
                stmt = stmt.where(
                    or_(
                        NotificationEvent.notification_name.ilike(pattern),
                        NotificationEvent.notification_oid.ilike(pattern),
                    )
                )
            if normalized_source_host:
                stmt = stmt.where(NotificationEvent.source_host.ilike(f"%{normalized_source_host}%"))
            if normalized_target_host:
                stmt = stmt.where(NotificationEvent.target_host.ilike(f"%{normalized_target_host}%"))
            if recorded_from is not None:
                stmt = stmt.where(NotificationEvent.recorded_at >= recorded_from)
            if recorded_to is not None:
                stmt = stmt.where(NotificationEvent.recorded_at <= recorded_to)
            if normalized_query:
                matched_ids = self._search_event_ids(session, normalized_query)
                pattern = f"%{normalized_query}%"
                match_filter = or_(
                    NotificationEvent.notification_name.ilike(pattern),
                    NotificationEvent.notification_oid.ilike(pattern),
                    NotificationEvent.community.ilike(pattern),
                    NotificationEvent.source_host.ilike(pattern),
                    NotificationEvent.target_host.ilike(pattern),
                    NotificationEvent.id.in_(matched_ids) if matched_ids else false(),
                )
                stmt = stmt.where(match_filter)

            total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
            rows = session.scalars(stmt.limit(limit).offset(offset)).all()
            return {
                "items": [self._event_summary(row) for row in rows],
                "total": int(total),
                "limit": limit,
                "offset": offset,
            }

    def clear_events(self) -> dict[str, Any]:
        with self.session_factory() as session:
            deleted_total = (
                session.scalar(select(func.count()).select_from(NotificationEvent)) or 0
            )
            session.execute(delete(NotificationEvent))
            session.execute(text("DELETE FROM notification_event_search"))
            session.commit()
        return {"status": "cleared", "deleted": int(deleted_total)}

    def get_event(self, event_id: int) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(NotificationEvent, event_id)
            if row is None:
                raise EventHistoryServiceError(f"Notification event {event_id} does not exist.")
            payload = self._event_summary(row)
            payload["event"] = self._decorate_event(row)
            payload["payload_hex"] = row.payload_hex
            return payload

    def _search_event_ids(self, session, query: str) -> list[int]:
        fts_query = self._fts_query(query)
        if not fts_query:
            return []
        rows = session.execute(
            text(
                """
                SELECT DISTINCT CAST(event_id AS INTEGER)
                FROM notification_event_search
                WHERE notification_event_search MATCH :query
                """
            ),
            {"query": fts_query},
        ).scalars()
        return [int(value) for value in rows if value is not None]

    def _event_summary(self, row: NotificationEvent) -> dict[str, Any]:
        event = row.event_json or {}
        varbinds = event.get("varbinds")
        resolve_mibs = event.get("resolve_mibs")
        return {
            "id": row.id,
            "bundle_set_id": row.bundle_set_id,
            "direction": row.direction,
            "pdu_type": row.pdu_type,
            "request_id": row.request_id,
            "community": row.community,
            "source_address": self._serialize_socket_address(row.source_host, row.source_port),
            "target_address": self._serialize_socket_address(row.target_host, row.target_port),
            "notification_oid": row.notification_oid,
            "notification_name": row.notification_name,
            "notification_description": row.notification_description,
            "uptime": row.uptime,
            "payload_available": row.payload_hex is not None,
            "varbind_count": len(varbinds) if isinstance(varbinds, list) else 0,
            "varbinds": varbinds if isinstance(varbinds, list) else [],
            "resolve_mibs": resolve_mibs if isinstance(resolve_mibs, bool) else None,
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at is not None else None,
        }

    def _decorate_event(self, row: NotificationEvent) -> dict[str, Any]:
        event = dict(row.event_json or {})
        event["event_id"] = row.id
        event["recorded_at"] = row.recorded_at.isoformat() if row.recorded_at is not None else None
        event["direction"] = row.direction
        event.setdefault("source_address", self._serialize_socket_address(row.source_host, row.source_port))
        event.setdefault("target_address", self._serialize_socket_address(row.target_host, row.target_port))
        return event

    def _serialize_socket_address(self, host: str | None, port: int | None) -> dict[str, Any] | None:
        if host is None or port is None:
            return None
        return {
            "host": host,
            "port": port,
        }

    def _validate_paging(self, *, limit: int, offset: int) -> None:
        if limit < 1 or limit > 500:
            raise EventHistoryServiceError("limit must be between 1 and 500.")
        if offset < 0:
            raise EventHistoryServiceError("offset cannot be negative.")

    def _fts_query(self, query: str) -> str:
        tokens = [token.lower() for token in _SEARCH_TOKEN_RE.findall(query)]
        if not tokens:
            return ""
        return " AND ".join(f'"{token}"*' for token in tokens)
