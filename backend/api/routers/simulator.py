import os
import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.sim_manager import SimulatorManager
from core.config import settings

router = APIRouter(prefix="/simulator", tags=["Simulator"])
logger = logging.getLogger(__name__)

class SimConfig(BaseModel):
    port: int = None
    community: str = None

# Custom Data File Path
CUSTOM_DATA_FILE = os.path.join(settings.BASE_DIR, "data", "configs", "custom_data.json")

# ==================== Simulator Endpoints ====================

@router.get("/status")
def get_status():
    return SimulatorManager.status()

@router.post("/start")
def start_simulator(config: SimConfig = None):
    p = config.port if config else None
    c = config.community if config else None
    return SimulatorManager.start(port=p, community=c)

@router.post("/stop")
def stop_simulator():
    return SimulatorManager.stop()

@router.post("/restart")
def restart_simulator():
    return SimulatorManager.restart()

# ==================== Custom Data Endpoints ====================

@router.get("/data")
def get_custom_data():
    """Get custom data for simulator"""
    try:
        if not os.path.exists(CUSTOM_DATA_FILE):
            return {}
        
        with open(CUSTOM_DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load custom data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/data")
def update_custom_data(data: dict):
    """Update custom data and restart simulator if running"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(CUSTOM_DATA_FILE), exist_ok=True)
        
        # Save data
        with open(CUSTOM_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Restart simulator if running
        sim_status = SimulatorManager.status()
        if sim_status.get("running"):
            SimulatorManager.restart()
            msg = "Data saved and simulator restarted"
        else:
            msg = "Data saved (Simulator is currently stopped)"
        
        logger.info(f"Custom data updated: {len(data)} entries")
        return {"status": "saved", "message": msg}
    
    except Exception as e:
        logger.error(f"Failed to save custom data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
