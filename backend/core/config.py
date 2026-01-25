import os

class Settings:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    
    # Paths for Simulator
    MIB_DIR = os.path.join(DATA_DIR, "mibs")
    CONFIG_DIR = os.path.join(DATA_DIR, "configs")
    CUSTOM_DATA_FILE = os.path.join(CONFIG_DIR, "custom_data.json")
    
    # Simulator Settings
    SNMP_PORT = int(os.getenv("SNMP_PORT", 1061))
    COMMUNITY = os.getenv("SNMP_COMMUNITY", "public")

    LOG_LEVEL: str = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR

    class Config:
        env_file = ".env"

settings = Settings()
