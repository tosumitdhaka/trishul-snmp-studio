import os
import shutil
import json
import logging
import aiofiles
from fastapi import UploadFile
from core.config import settings

logger = logging.getLogger(__name__)

class FileService:
    @staticmethod
    def list_mibs():
        """Returns list of uploaded MIB files"""
        if not os.path.exists(settings.MIB_DIR):
            return []
        return [f for f in os.listdir(settings.MIB_DIR) if f.endswith(('.mib', '.my', '.txt'))]

    @staticmethod
    async def save_mib(file: UploadFile):
        """Saves an uploaded MIB file"""
        os.makedirs(settings.MIB_DIR, exist_ok=True)
        file_path = os.path.join(settings.MIB_DIR, file.filename)
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        return file.filename

    @staticmethod
    def delete_mib(filename: str):
        """Deletes a MIB file"""
        file_path = os.path.join(settings.MIB_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    @staticmethod
    def get_custom_data():
        """Reads custom_data.json"""
        if os.path.exists(settings.CUSTOM_DATA_FILE):
            try:
                with open(settings.CUSTOM_DATA_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def save_custom_data(data: dict):
        """Writes to custom_data.json"""
        os.makedirs(settings.CONFIG_DIR, exist_ok=True)
        with open(settings.CUSTOM_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
