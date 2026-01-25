import logging
from fastapi import APIRouter
from services.sim_manager import SimulatorManager
from pydantic import BaseModel

router = APIRouter(prefix="/simulator", tags=["Simulator"])

logger = logging.getLogger(__name__)

class SimConfig(BaseModel):
    port: int = None
    community: str = None

@router.get("/status")
def get_status():
    return SimulatorManager.status()

@router.post("/start")
def start_simulator(config: SimConfig = None):
    # If no config provided, use defaults
    p = config.port if config else None
    c = config.community if config else None
    return SimulatorManager.start(port=p, community=c)

@router.post("/stop")
def stop_simulator():
    return SimulatorManager.stop()

@router.post("/restart")
def restart_simulator():
    return SimulatorManager.restart()
