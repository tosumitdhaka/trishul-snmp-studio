import logging
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.walk_engine import WalkEngine
from core.config import settings

router = APIRouter(prefix="/walk", tags=["Walker"])

logger = logging.getLogger(__name__)

class WalkRequest(BaseModel):
    target: str = "127.0.0.1"
    port: int = 1061
    community: str = "public"
    oid: str
    parse: bool = True
    use_mibs: bool = True  # <--- Ensure this exists

@router.post("/execute")
def execute_walk(req: WalkRequest):
    try:
        # 1. Run Walk (Pass all arguments explicitly)
        raw_lines = WalkEngine.run_snmpwalk(
            host=req.target, 
            port=req.port, 
            community=req.community, 
            oid=req.oid, 
            use_mibs=req.use_mibs
        )
        
        # 2. Check for Engine Errors (returned as dict)
        if isinstance(raw_lines, dict) and "error" in raw_lines:
            print(f"Engine Error: {raw_lines['error']}") # Log it
            raise HTTPException(status_code=500, detail=raw_lines["error"])
            
        # 3. Return Raw Lines if parsing disabled
        if not req.parse:
            return {
                "mode": "raw",
                "count": len(raw_lines),
                "data": raw_lines
            }

        # 4. Parse
        json_result = WalkEngine.parse_output(raw_lines, req.target, req.oid)

        return {
            "mode": "parsed",
            "count": len(json_result),
            "data": json_result
        }
        
    except Exception as e:
        # LOG THE FULL TRACEBACK so we can see it in docker logs
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
