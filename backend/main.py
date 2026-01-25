from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.meta import meta
from core.security import validate_auth
from api.routers import simulator, walker, files, settings as settings

app = FastAPI(title=meta.NAME, version=meta.VERSION)

# CORS (Allow Frontend to talk to Backend if needed, though Nginx handles this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/meta")
def get_app_metadata():
    """Returns App Name and Version for the UI"""
    return {
        "name": meta.NAME,
        "version": meta.VERSION,
        "author": meta.AUTHOR
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "snmp-studio-backend"}

app.include_router(simulator.router, prefix="/api", dependencies=[Depends(validate_auth)]) 
app.include_router(walker.router, prefix="/api", dependencies=[Depends(validate_auth)])
app.include_router(files.router, prefix="/api", dependencies=[Depends(validate_auth)])
app.include_router(settings.router, prefix="/api", dependencies=[Depends(validate_auth)])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
