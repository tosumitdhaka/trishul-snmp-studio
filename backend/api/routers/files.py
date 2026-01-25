import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.file_service import FileService
from services.sim_manager import SimulatorManager

router = APIRouter(prefix="/files", tags=["Files"])

logger = logging.getLogger(__name__)

# --- MIB Management ---
@router.get("/mibs")
def list_mibs():
    return {"mibs": FileService.list_mibs()}

@router.post("/mibs")
async def upload_mibs(files: List[UploadFile] = File(...)): # <--- Changed to List
    saved_files = []
    for file in files:
        filename = await FileService.save_mib(file)
        saved_files.append(filename)
    return {"status": "uploaded", "filenames": saved_files}

@router.delete("/mibs/{filename}")
def delete_mib(filename: str):
    if FileService.delete_mib(filename):
        return {"status": "deleted", "filename": filename}
    raise HTTPException(status_code=404, detail="File not found")

# --- Custom Data Management ---
@router.get("/data")
def get_custom_data():
    return FileService.get_custom_data()

@router.post("/data")
def update_custom_data(data: dict):
    FileService.save_custom_data(data)
    
    # ✅ FIX: Only restart if it is ALREADY running
    sim_status = SimulatorManager.status()
    if sim_status.get("running"):
        SimulatorManager.restart()
        msg = "Simulator restarted with new data"
    else:
        msg = "Data saved (Simulator is currently stopped)"

    return {"status": "saved", "message": msg}
