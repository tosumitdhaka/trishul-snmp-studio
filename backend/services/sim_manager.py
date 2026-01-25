import subprocess
import sys
import os
import signal
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class SimulatorManager:
    _process = None

    @classmethod
    def start(cls, port=None, community=None):
        # ... check if running ...

        # Use overrides or defaults from settings
        target_port = str(port) if port else str(settings.SNMP_PORT)
        target_comm = community if community else settings.COMMUNITY

        cmd = [
            sys.executable,
            os.path.join(settings.BASE_DIR, "workers", "snmp_simulator.py"),
            "--port", target_port,
            "--community", target_comm,
            "--mib-dir", settings.MIB_DIR,
            "--data-file", settings.CUSTOM_DATA_FILE
        ]

        # ✅ CHANGE: Redirect stdout and stderr to the main process output
        # This ensures errors appear in 'docker logs'
        cls._process = subprocess.Popen(
            cmd, 
            stdout=sys.stdout, 
            stderr=sys.stderr
        )
        
        return {"status": "started", "pid": cls._process.pid}

    @classmethod
    def stop(cls):
        # Check if process object exists
        if cls._process:
            # Check if it is actually running
            if cls._process.poll() is None:
                cls._process.terminate()
                try:
                    cls._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    cls._process.kill()
            
            # Clean up reference regardless
            cls._process = None
            return {"status": "stopped"}
            
        return {"status": "not_running"}

    @classmethod
    def restart(cls):
        cls.stop()
        return cls.start()

    @classmethod
    def status(cls):
        running = cls._process is not None and cls._process.poll() is None
        return {
            "running": running,
            "pid": cls._process.pid if running else None,
            "port": settings.SNMP_PORT,
            "community": settings.COMMUNITY
        }
