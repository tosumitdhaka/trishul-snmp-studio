import os
import re
import logging
from typing import List, Dict, Optional, Set
from pathlib import Path
from pysnmp.smi import builder, view, compiler
from pysnmp.proto.api import v2c
from core.config import settings

logger = logging.getLogger(__name__)

class MibDependency:
    """Represents a MIB import dependency"""
    def __init__(self, name: str, required_by: str):
        self.name = name
        self.required_by = required_by
    
    def to_dict(self):
        return {"name": self.name, "required_by": self.required_by}

class MibInfo:
    """Metadata about a loaded MIB"""
    def __init__(self, name: str, file_path: str, status: str = "loaded"):
        self.name = name
        self.file_path = file_path
        self.status = status
        self.imports: List[str] = []
        self.objects_count = 0
        self.traps_count = 0
        self.error_message: Optional[str] = None
    
    def to_dict(self):
        return {
            "name": self.name,
            "file": os.path.basename(self.file_path),
            "status": self.status,
            "imports": self.imports,
            "objects": self.objects_count,
            "traps": self.traps_count,
            "error": self.error_message
        }

class MibService:
    """
    Singleton MIB manager with dependency tracking and hot-reload support.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.mib_builder = builder.MibBuilder()
        self.mib_view = view.MibViewController(self.mib_builder)
        self.loaded_mibs: Dict[str, MibInfo] = {}
        self.failed_mibs: Dict[str, MibInfo] = {}
        
        self._configure_sources()
        self._load_all_mibs()
        
        self._initialized = True
        logger.info(f"MibService initialized: {len(self.loaded_mibs)} MIBs loaded")
    
    def _configure_sources(self):
        """Configure MIB search paths"""
        sources = [
            f'file://{os.path.abspath(settings.MIB_DIR)}',
            'file:///usr/share/snmp/mibs',
            'file:///usr/share/snmp/mibs/ietf',
            'file:///usr/share/snmp/mibs/iana',
            'https://mibs.pysnmp.com/asn1/@mib@'
        ]
        
        compiler.add_mib_compiler(self.mib_builder, sources=sources)
        logger.debug(f"MIB sources configured: {sources}")
    
    def _load_all_mibs(self):
        """Load all MIBs from the MIB directory"""
        if not os.path.exists(settings.MIB_DIR):
            logger.warning(f"MIB directory not found: {settings.MIB_DIR}")
            return
        
        mib_files = self._discover_mib_files()
        logger.info(f"Found {len(mib_files)} MIB files")
        
        for mib_name, file_path in mib_files.items():
            self._load_single_mib(mib_name, file_path)
        
        self._update_statistics()
    
    def _discover_mib_files(self) -> Dict[str, str]:
        """Scan MIB directory and return {mib_name: file_path}"""
        mib_files = {}
        
        for file_name in os.listdir(settings.MIB_DIR):
            if file_name.endswith(('.mib', '.txt', '.my')):
                mib_name = file_name.rsplit('.', 1)[0]
                file_path = os.path.join(settings.MIB_DIR, file_name)
                mib_files[mib_name] = file_path
        
        return mib_files
    
    def _load_single_mib(self, mib_name: str, file_path: str):
        """Load a single MIB and track its status"""
        try:
            self.mib_builder.load_modules(mib_name)
            
            mib_info = MibInfo(mib_name, file_path, status="loaded")
            mib_info.imports = self._extract_imports(file_path)
            
            self.loaded_mibs[mib_name] = mib_info
            logger.debug(f"✓ Loaded MIB: {mib_name}")
            
        except Exception as e:
            mib_info = MibInfo(mib_name, file_path, status="error")
            mib_info.error_message = str(e)
            
            if "Cannot find" in str(e) or "No module named" in str(e):
                mib_info.status = "missing_deps"
            
            self.failed_mibs[mib_name] = mib_info
            logger.warning(f"✗ Failed to load MIB {mib_name}: {e}")
    
    def _extract_imports(self, file_path: str) -> List[str]:
        """Parse MIB file to extract IMPORTS"""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                import_match = re.search(r'IMPORTS\s+(.*?);', content, re.DOTALL | re.IGNORECASE)
                
                if import_match:
                    import_block = import_match.group(1)
                    from_matches = re.findall(r'FROM\s+([A-Za-z0-9\-]+)', import_block)
                    imports = list(set(from_matches))
        
        except Exception as e:
            logger.debug(f"Could not parse imports from {file_path}: {e}")
        
        return imports
    
    def _update_statistics(self):
        """Count objects and traps in loaded MIBs"""
        for module_name, symbols in self.mib_builder.mibSymbols.items():
            if module_name not in self.loaded_mibs:
                continue
            
            mib_info = self.loaded_mibs[module_name]
            
            for symbol_name, symbol_obj in symbols.items():
                class_name = symbol_obj.__class__.__name__
                
                if class_name == 'NotificationType':
                    mib_info.traps_count += 1
                elif class_name in ['MibScalar', 'MibTableColumn']:
                    mib_info.objects_count += 1
    
    def _is_standard_mib(self, mib_name: str) -> bool:
        """Check if a MIB is a standard/system MIB"""
        standard_mibs = {
            'SNMPv2-SMI', 'SNMPv2-TC', 'SNMPv2-CONF', 'SNMPv2-MIB',
            'SNMP-FRAMEWORK-MIB', 'SNMP-MPD-MIB', 'SNMP-TARGET-MIB',
            'SNMP-NOTIFICATION-MIB', 'SNMP-PROXY-MIB', 'SNMP-USER-BASED-SM-MIB',
            'SNMP-VIEW-BASED-ACM-MIB', 'SNMP-COMMUNITY-MIB',
            'IANAifType-MIB', 'IANA-ADDRESS-FAMILY-NUMBERS-MIB',
            'INET-ADDRESS-MIB', 'IF-MIB', 'IP-MIB', 'TCP-MIB', 'UDP-MIB',
            'HOST-RESOURCES-MIB', 'ENTITY-MIB', 'BRIDGE-MIB',
            'RFC1155-SMI', 'RFC1213-MIB', 'RFC-1215'
        }
        
        return mib_name in standard_mibs
    
    def reload(self):
        """Hot-reload all MIBs"""
        logger.info("Reloading MIB service...")
        
        self.mib_builder = builder.MibBuilder()
        self.mib_view = view.MibViewController(self.mib_builder)
        self.loaded_mibs.clear()
        self.failed_mibs.clear()
        
        self._configure_sources()
        self._load_all_mibs()
        
        logger.info(f"Reload complete: {len(self.loaded_mibs)} loaded, {len(self.failed_mibs)} failed")
    
    def get_status(self) -> dict:
        """Get overall MIB service status"""
        return {
            "loaded": len(self.loaded_mibs),
            "failed": len(self.failed_mibs),
            "total": len(self.loaded_mibs) + len(self.failed_mibs),
            "mibs": [info.to_dict() for info in self.loaded_mibs.values()],
            "errors": [info.to_dict() for info in self.failed_mibs.values()]
        }
    
    def validate_mib_file(self, file_path: str) -> dict:
        """Validate a MIB file before loading"""
        result = {
            "valid": False,
            "mib_name": None,
            "imports": [],
            "missing_deps": [],
            "errors": []
        }
        
        try:
            mib_name = Path(file_path).stem
            result["mib_name"] = mib_name
            
            imports = self._extract_imports(file_path)
            result["imports"] = imports
            
            for imp in imports:
                if imp in self.loaded_mibs:
                    continue
                
                if self._is_standard_mib(imp):
                    continue
                
                if imp in self.mib_builder.mibSymbols:
                    continue
                
                result["missing_deps"].append(imp)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                if 'DEFINITIONS' not in content:
                    result["errors"].append("Missing DEFINITIONS keyword")
                
                if 'BEGIN' not in content or 'END' not in content:
                    result["errors"].append("Missing BEGIN/END block")
            
            if not result["errors"]:
                result["valid"] = True
        
        except Exception as e:
            result["errors"].append(f"Validation error: {str(e)}")
        
        return result
    
    def list_traps(self) -> List[dict]:
        """Enumerate all NOTIFICATION-TYPE objects"""
        traps = []
        
        for module_name, symbols in self.mib_builder.mibSymbols.items():
            for symbol_name, symbol_obj in symbols.items():
                if symbol_obj.__class__.__name__ == 'NotificationType':
                    try:
                        trap_info = {
                            "module": module_name,
                            "name": symbol_name,
                            "full_name": f"{module_name}::{symbol_name}",
                            "oid": ".".join(map(str, symbol_obj.name)),
                            "description": symbol_obj.getDescription() or "No description",
                            "objects": []
                        }
                        
                        if hasattr(symbol_obj, 'getObjects'):
                            obj_list = symbol_obj.getObjects()
                            if obj_list:
                                for obj_name in obj_list:
                                    try:
                                        if isinstance(obj_name, tuple) and len(obj_name) >= 2:
                                            obj_module = obj_name[0]
                                            obj_symbol = obj_name[-1]
                                            
                                            if obj_module in self.mib_builder.mibSymbols:
                                                if obj_symbol in self.mib_builder.mibSymbols[obj_module]:
                                                    obj_def = self.mib_builder.mibSymbols[obj_module][obj_symbol]
                                                    
                                                    trap_info["objects"].append({
                                                        "name": obj_symbol,
                                                        "full_name": f"{obj_module}::{obj_symbol}",
                                                        "oid": ".".join(map(str, obj_def.name))
                                                    })
                                    except Exception as e:
                                        logger.debug(f"Error processing object {obj_name}: {e}")
                        
                        traps.append(trap_info)
                    
                    except Exception as e:
                        logger.debug(f"Error processing trap {symbol_name}: {e}")
        
        return traps
    
    def list_objects(self, module_name: Optional[str] = None) -> List[dict]:
        """List all MIB objects"""
        objects = []
        
        modules = [module_name] if module_name else self.mib_builder.mibSymbols.keys()
        
        for mod in modules:
            if mod not in self.mib_builder.mibSymbols:
                continue
            
            symbols = self.mib_builder.mibSymbols[mod]
            
            for symbol_name, symbol_obj in symbols.items():
                class_name = symbol_obj.__class__.__name__
                
                if class_name in ['MibScalar', 'MibTableColumn']:
                    try:
                        objects.append({
                            "module": mod,
                            "name": symbol_name,
                            "full_name": f"{mod}::{symbol_name}",
                            "oid": ".".join(map(str, symbol_obj.name)),
                            "type": class_name,
                            "syntax": symbol_obj.getSyntax().__class__.__name__
                        })
                    except:
                        pass
        
        return objects
    
    def resolve_oid(self, oid: str, mode: str = "name") -> str:
        """Resolve OID to name or vice versa"""
        try:
            if mode == "numeric":
                # Name → Numeric
                if "::" not in oid:
                    # Already numeric
                    return oid
                
                parts = oid.split("::")
                if len(parts) != 2:
                    logger.warning(f"Invalid OID format: {oid}")
                    return oid
                
                module, name_with_index = parts
                
                # Check if MIB is loaded
                if module not in self.mib_builder.mibSymbols:
                    logger.error(f"MIB module '{module}' not loaded")
                    return oid
                
                # Handle index (e.g., "sysUpTime.0")
                if "." in name_with_index:
                    name, index = name_with_index.rsplit(".", 1)
                else:
                    name = name_with_index
                    index = None
                
                # Look up the symbol in the MIB
                if name not in self.mib_builder.mibSymbols[module]:
                    logger.error(f"Symbol '{name}' not found in module '{module}'")
                    return oid
                
                symbol_obj = self.mib_builder.mibSymbols[module][name]
                
                # Get the OID from the symbol
                if hasattr(symbol_obj, 'name'):
                    oid_tuple = symbol_obj.name
                    numeric = ".".join(map(str, oid_tuple))
                    
                    # Add index if present
                    if index:
                        numeric += "." + index
                    
                    logger.debug(f"Resolved {oid} -> {numeric}")
                    return numeric
                else:
                    logger.error(f"Symbol '{name}' has no OID")
                    return oid
            
            elif mode == "name":
                # Numeric → Name
                if "::" in oid:
                    # Already symbolic
                    return oid
                
                oid_tuple = tuple(int(x) for x in oid.strip('.').split('.'))
                
                try:
                    oid_obj, label, suffix = self.mib_view.getNodeName(oid_tuple)
                    
                    # Try to find MIB module name
                    for module_name, symbols in self.mib_builder.mibSymbols.items():
                        for symbol_name, symbol_obj in symbols.items():
                            if hasattr(symbol_obj, 'name') and symbol_obj.name == oid_obj:
                                result = f"{module_name}::{symbol_name}"
                                if suffix:
                                    result += "." + ".".join(map(str, suffix))
                                return result
                    
                    # Fallback
                    meaningful_labels = [l for l in label if l not in ['iso', 'org', 'dod', 'internet', 'mgmt', 'mib-2', 'private', 'enterprises']]
                    
                    if meaningful_labels:
                        result = "::".join(meaningful_labels[-2:]) if len(meaningful_labels) >= 2 else meaningful_labels[-1]
                    else:
                        result = "::".join(label[-2:]) if len(label) >= 2 else label[-1]
                    
                    if suffix:
                        result += "." + ".".join(map(str, suffix))
                    
                    return result
                except Exception as e:
                    logger.debug(f"Name resolution failed: {e}")
                    return oid
        
        except Exception as e:
            logger.error(f"OID resolution failed for '{oid}': {e}")
            return oid


    
    def get_trap_details(self, trap_identifier: str) -> Optional[dict]:
        """Get detailed information about a specific trap"""
        traps = self.list_traps()
        
        for trap in traps:
            if trap["full_name"] == trap_identifier or trap["oid"] == trap_identifier:
                return trap
        
        return None

_mib_service_instance = None

def get_mib_service() -> MibService:
    """Get or create the MibService singleton"""
    global _mib_service_instance
    if _mib_service_instance is None:
        _mib_service_instance = MibService()
    return _mib_service_instance
