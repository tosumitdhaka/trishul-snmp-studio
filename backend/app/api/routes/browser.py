from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query

from fastapi import HTTPException

from app.services import browser_service
from app.services.bundle_state import get_bundle
from app.services.session import SessionService, SessionServiceError


def _require_authenticated_user(token):
    try:
        return SessionService().require_username(token)
    except SessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

router = APIRouter()


@router.get("/mibs/browse/modules")
def browse_modules(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_authenticated_user(x_auth_token)
    return browser_service.get_modules(bundle=get_bundle())


@router.get("/mibs/browse/tree/module")
def browse_module_tree(
    module: str | None = Query(default=None),
    type_filter: str | None = Query(default=None),
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_authenticated_user(x_auth_token)
    return browser_service.get_module_tree(module=module, type_filter=type_filter, bundle=get_bundle())


@router.get("/mibs/browse/tree/oid")
def browse_oid_tree(
    root_oid: str = Query(..., min_length=1),
    depth: int = Query(1, ge=1, le=6),
    module: str | None = Query(default=None),
    type_filter: str | None = Query(default=None),
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_authenticated_user(x_auth_token)
    return browser_service.get_oid_tree(
        root_oid=root_oid,
        depth=depth,
        module=module,
        type_filter=type_filter,
        bundle=get_bundle(),
    )


@router.get("/mibs/browse/search")
def browse_search(
    query: str = Query(..., min_length=1),
    module: str | None = Query(default=None),
    type_filter: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_authenticated_user(x_auth_token)
    return browser_service.search_bundle(
        query=query,
        module=module,
        type_filter=type_filter,
        limit=limit,
        bundle=get_bundle(),
    )


@router.get("/mibs/browse/node/{oid:path}")
def browse_node(
    oid: str,
    module: str | None = None,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_authenticated_user(x_auth_token)
    return browser_service.get_node(oid, module=module, bundle=get_bundle())
