from fastapi import APIRouter

from app.api.routes import (
    browser,
    mibs,
    settings,
    simulator,
    stats,
    system,
    traps,
    walker,
    ws,
)

router = APIRouter()
router.include_router(system.router, prefix="/api", tags=["system"])
router.include_router(settings.router, prefix="/api", tags=["operator-ui"])
router.include_router(stats.router, prefix="/api", tags=["operator-ui"])
router.include_router(simulator.router, prefix="/api", tags=["operator-ui"])
router.include_router(walker.router, prefix="/api", tags=["operator-ui"])
router.include_router(traps.router, prefix="/api", tags=["operator-ui"])
router.include_router(mibs.router, prefix="/api", tags=["operator-ui"])
router.include_router(browser.router, prefix="/api", tags=["operator-ui"])
router.include_router(ws.router, prefix="/api", tags=["realtime"])
