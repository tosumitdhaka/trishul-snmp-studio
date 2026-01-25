from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.security import save_credentials, validate_auth

router = APIRouter(prefix="/settings", tags=["Settings"])

class AuthUpdate(BaseModel):
    username: str
    password: str

@router.get("/check", dependencies=[Depends(validate_auth)])
def check_auth_status():
    """Simple endpoint to trigger Basic Auth prompt"""
    return {"status": "authenticated"}

@router.post("/auth", dependencies=[Depends(validate_auth)])
def update_auth(creds: AuthUpdate):
    save_credentials(creds.username, creds.password)
    return {"status": "updated", "message": "Credentials updated. Please log in again."}
