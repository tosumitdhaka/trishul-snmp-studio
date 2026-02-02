import os
from pathlib import Path

class Settings:
    # Base paths
    BASE_DIR = Path(__file__).parent.parent.resolve()
    DATA_DIR = BASE_DIR / "data"
    MIB_DIR = DATA_DIR / "mibs"
    CONFIG_DIR = DATA_DIR / "configs"
    LOG_DIR = DATA_DIR / "logs"
    
    # SNMP Settings (with env overrides)
    SNMP_PORT = int(os.getenv("SNMP_PORT", "1061"))
    COMMUNITY = os.getenv("SNMP_COMMUNITY", "public")
    TRAP_PORT = int(os.getenv("TRAP_PORT", "1162"))
    
    # File paths
    CUSTOM_DATA_FILE = CONFIG_DIR / "custom_data.json"
    SECRETS_FILE = CONFIG_DIR / "secrets.json"
    TRAPS_FILE = DATA_DIR / "traps.jsonl"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")   # Options: DEBUG, INFO, WARNING, ERROR
    LOG_FILE = LOG_DIR / "app.log"
    
    # Application
    APP_NAME = os.getenv("APP_NAME", "SNMP Studio")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    
    # Security
    SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # seconds
    
    def __init__(self):
        # Ensure directories exist
        self.DATA_DIR.mkdir(exist_ok=True)
        self.MIB_DIR.mkdir(exist_ok=True)
        self.CONFIG_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)
        
        # Create default files if they don't exist
        if not self.CUSTOM_DATA_FILE.exists():
            self.CUSTOM_DATA_FILE.write_text('{}')
        
        if not self.SECRETS_FILE.exists():
            import json
            default_secrets = {
                "username": "admin",
                "password": "admin123"
            }
            self.SECRETS_FILE.write_text(json.dumps(default_secrets, indent=2))
        
        if not self.TRAPS_FILE.exists():
            self.TRAPS_FILE.touch()

settings = Settings()
