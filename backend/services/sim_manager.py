import subprocess
import sys
import os
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class SimulatorManager:
    _process = None
    _port = 1061
    _community = "public"

    @classmethod
    def start(cls, port=None, community=None):
        # Check if already running
        if cls._process and cls._process.poll() is None:
            return {"status": "already_running", "pid": cls._process.pid}

        # Use overrides or defaults
        cls._port = port if port else 1061
        cls._community = community if community else "public"

        mib_dir = os.path.join(settings.BASE_DIR, "data", "mibs")
        data_file = os.path.join(settings.BASE_DIR, "data", "configs", "custom_data.json")

        cmd = [
            sys.executable,
            os.path.join(settings.BASE_DIR, "workers", "snmp_simulator.py"),
            "--port", str(cls._port),
            "--community", cls._community,
            "--mib-dir", mib_dir,
            "--data-file", data_file
        ]

        # Redirect stdout and stderr to main process
        cls._process = subprocess.Popen(
            cmd, 
            stdout=sys.stdout, 
            stderr=sys.stderr
        )
        
        return {
            "status": "started", 
            "pid": cls._process.pid,
            "port": cls._port,
            "community": cls._community
        }

    @classmethod
    def stop(cls):
        if cls._process:
            if cls._process.poll() is None:
                cls._process.terminate()
                try:
                    cls._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    cls._process.kill()
            
            cls._process = None
            return {"status": "stopped"}
            
        return {"status": "not_running"}

    @classmethod
    def restart(cls):
        cls.stop()
        import time
        time.sleep(0.5)
        return cls.start()

    @classmethod
    def status(cls):
        running = cls._process is not None and cls._process.poll() is None
        return {
            "running": running,
            "pid": cls._process.pid if running else None,
            "port": cls._port if running else None,
            "community": cls._community if running else None
        }
