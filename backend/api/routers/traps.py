from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from pysnmp.hlapi.v3arch.asyncio import *
from pysnmp.proto.rfc1902 import *
from services.trap_manager import trap_manager

router = APIRouter(prefix="/traps", tags=["Traps"])
logger = logging.getLogger(__name__)

class TrapVarbind(BaseModel):
    oid: str
    type: str = "String"
    value: str

class TrapSendRequest(BaseModel):
    target: str
    port: int = 162
    community: str = "public"
    oid: str
    varbinds: List[TrapVarbind] = []

class TrapStartRequest(BaseModel):
    port: int = 1162
    community: str = "public"
    resolve_mibs: bool = True

@router.post("/send")
async def send_trap(req: TrapSendRequest):
    """Send SNMP trap - OID MUST be numeric"""
    try:
        logger.info(f"Sending trap OID={req.oid} to {req.target}:{req.port}")
        
        # Validate OID is numeric
        if "::" in req.oid:
            raise HTTPException(
                status_code=400,
                detail="Trap OID must be numeric. Frontend should resolve symbolic names first."
            )
        
        # Create trap
        trap_oid = ObjectIdentity(req.oid)
        notification = NotificationType(trap_oid)
        
        # Add VarBinds
        for vb in req.varbinds:
            if "::" in vb.oid:
                raise HTTPException(
                    status_code=400,
                    detail=f"VarBind OID must be numeric: {vb.oid}"
                )
            
            # Convert value
            if vb.type == "Integer": 
                val = Integer32(int(vb.value))
            elif vb.type == "Counter": 
                val = Counter32(int(vb.value))
            elif vb.type == "Gauge": 
                val = Gauge32(int(vb.value))
            elif vb.type == "OID": 
                val = ObjectIdentifier(str(vb.value))
            elif vb.type == "IpAddress": 
                val = IpAddress(str(vb.value))
            elif vb.type == "TimeTicks": 
                val = TimeTicks(int(vb.value))
            else: 
                val = OctetString(str(vb.value))
            
            notification.addVarBinds(ObjectType(ObjectIdentity(vb.oid), val))
        
        # Send
        target = await UdpTransportTarget.create((req.target, req.port))
        
        errorIndication, errorStatus, errorIndex, varBinds = await send_notification(
            SnmpEngine(),
            CommunityData(req.community, mpModel=1),
            target,
            ContextData(),
            'trap',
            notification
        )
        
        if errorIndication:
            raise HTTPException(status_code=500, detail=f"SNMP Error: {str(errorIndication)}")
        
        if errorStatus:
            raise HTTPException(status_code=500, detail=f"SNMP Error: {errorStatus.prettyPrint()}")
        
        logger.info(f"✓ Trap sent successfully")
        return {"status": "sent", "target": req.target, "port": req.port}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trap send failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/status")
def get_status(): 
    return trap_manager.get_status()

@router.post("/start")
def start_receiver(req: TrapStartRequest): 
    return trap_manager.start(req.port, req.community, req.resolve_mibs)

@router.post("/stop")
def stop_receiver(): 
    return trap_manager.stop()

@router.get("/")
def get_received_traps(limit: int = 50): 
    return {"data": trap_manager.get_traps(limit)}

@router.delete("/")
def clear_traps(): 
    trap_manager.clear_traps()
    return {"status": "cleared"}
