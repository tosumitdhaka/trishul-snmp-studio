import sys
import os
import random
import json
import logging
import asyncio
import argparse

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.smi import builder, compiler
from pysnmp.proto.api import v2c

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

HIDE_DEPRECATED = True
HIDE_NOT_ACCESSIBLE = True 
SYSTEM_MIB_DIR = "/usr/share/snmp/mibs"

class MibDataGenerator:

    def get_value(self, syntax_obj, custom_val=None):
        # 1. Custom Value
        if custom_val is not None:
            try:
                type_name = syntax_obj.__class__.__name__
                if "Integer" in type_name: return v2c.Integer32(int(custom_val))
                elif "Unsigned" in type_name: return v2c.Unsigned32(int(custom_val))
                elif "Gauge" in type_name: return v2c.Gauge32(int(custom_val))
                elif "Counter64" in type_name: return v2c.Counter64(int(custom_val))
                elif "Counter" in type_name: return v2c.Counter32(int(custom_val))
                elif "String" in type_name: return v2c.OctetString(str(custom_val))
                elif "IpAddress" in type_name: return v2c.IpAddress(str(custom_val))
                elif any(x in type_name for x in ["Oid", "ObjectIdentifier", "AutonomousType"]):
                    return v2c.ObjectIdentifier(str(custom_val))
                
                # Try generic digit parsing if no type matched
                if str(custom_val).isdigit(): return v2c.Integer32(int(custom_val))
            except Exception as e:
                logger.warning(f"Failed to apply custom value '{custom_val}': {e}")

        # 2. Random Fallback
        try:
            type_name = syntax_obj.__class__.__name__

            if any(x in type_name for x in ["Oid", "ObjectIdentifier", "AutonomousType"]):
                return v2c.ObjectIdentifier(f"1.3.6.1.2.1.{random.randint(1,100)}")
            elif "Integer" in type_name: return v2c.Integer32(random.randint(1, 100))
            elif "Unsigned" in type_name: return v2c.Unsigned32(random.randint(1, 10000))
            elif "Gauge" in type_name: return v2c.Gauge32(random.randint(1, 100))
            elif "Counter64" in type_name: return v2c.Counter64(random.randint(1000000, 999999999))
            elif "Counter" in type_name: return v2c.Counter32(random.randint(1000, 999999))
            elif "TimeTicks" in type_name: return v2c.TimeTicks(random.randint(0, 5000000))
            elif "IpAddress" in type_name: return v2c.IpAddress("127.0.0.1")
            
            # Handle PhysAddress/MacAddress
            elif "PhysAddress" in type_name or "MacAddress" in type_name:
                mac_bytes = bytes([random.randint(0, 255) for _ in range(6)])
                return v2c.OctetString(mac_bytes)

            elif "String" in type_name: return v2c.OctetString(f"Sim-{random.randint(1,99)}")
            
            else: return v2c.Integer32(0)
        except: 
            return v2c.Integer32(0)

class MockController:
    def __init__(self, data_dict):
        self.db = data_dict
        self.sorted_oids = sorted(self.db.keys())

    def read_variables(self, *var_binds, **kwargs):
        logger.debug(f"RX GET: {var_binds}")
        rsp = []
        for oid, val in var_binds:
            key = tuple(oid)
            if key in self.db:
                rsp.append((v2c.ObjectIdentifier(oid), self.db[key]))
            else:
                rsp.append((v2c.ObjectIdentifier(oid), v2c.NoSuchObject()))
        return rsp

    def read_next_variables(self, *var_binds, **kwargs):
        logger.debug(f"RX WALK/NEXT: {var_binds}")
        rsp = []
        for oid, val in var_binds:
            current_oid = tuple(oid)
            next_oid = None
            for db_oid in self.sorted_oids:
                if db_oid > current_oid:
                    next_oid = db_oid
                    break
            if next_oid:
                rsp.append((v2c.ObjectIdentifier(next_oid), self.db[next_oid]))
            else:
                rsp.append((v2c.ObjectIdentifier(oid), v2c.EndOfMibView()))
        return rsp

def load_custom_data(path):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def compile_and_generate_data(mib_dir, custom_data_path):
    mibBuilder = builder.MibBuilder()

    sources = [
        f'file://{os.path.abspath(mib_dir)}',
        f'file://{SYSTEM_MIB_DIR}',
        f'file://{SYSTEM_MIB_DIR}/ietf',
        f'file://{SYSTEM_MIB_DIR}/iana'
    ]
    
    compiler.add_mib_compiler(mibBuilder, sources=sources)
    
    # Load MIBs one by one, skip failures
    mibs_to_load = []
    if os.path.exists(mib_dir):
        for f in os.listdir(mib_dir):
            if f.endswith(".mib") or f.endswith(".my") or f.endswith(".txt"):
                mibs_to_load.append(f.split('.')[0])
    
    if not mibs_to_load:
        logger.warning(f"No MIBs found in {mib_dir}")
    else:
        # Load MIBs individually to skip failures
        loaded_count = 0
        for mib_name in mibs_to_load:
            try:
                mibBuilder.load_modules(mib_name)
                loaded_count += 1
                logger.info(f"✓ Loaded MIB: {mib_name}")
            except Exception as e:
                logger.warning(f"✗ Skipped MIB {mib_name}: {str(e)[:100]}")
        
        logger.info(f"Loaded {loaded_count}/{len(mibs_to_load)} MIBs")

    custom_data = load_custom_data(custom_data_path)
    generator = MibDataGenerator()
    data_store = {}
    
    if hasattr(mibBuilder, 'mibSymbols'):
        for module_name, symbols in mibBuilder.mibSymbols.items():
            for symbol_name, symbol_obj in symbols.items():
                if not hasattr(symbol_obj, 'name') or not hasattr(symbol_obj, 'getSyntax'):
                    continue

                if HIDE_DEPRECATED and hasattr(symbol_obj, 'getStatus'):
                    if symbol_obj.getStatus() in ['deprecated', 'obsolete']:
                        continue
                
                if HIDE_NOT_ACCESSIBLE and hasattr(symbol_obj, 'getMaxAccess'):
                    if symbol_obj.getMaxAccess() == 'not-accessible':
                        continue

                base_oid = tuple(symbol_obj.name)
                
                if symbol_obj.__class__.__name__ == 'MibScalar':
                    key_str = f"{module_name}::{symbol_name}.0"
                    val = generator.get_value(symbol_obj.getSyntax(), custom_data.get(key_str))
                    data_store[base_oid + (0,)] = val
                
                elif symbol_obj.__class__.__name__ == 'MibTableColumn':
                    for i in [1, 2]:
                        key_str = f"{module_name}::{symbol_name}.{i}"
                        val = generator.get_value(symbol_obj.getSyntax(), custom_data.get(key_str))
                        data_store[base_oid + (i,)] = val

    # Inject Custom Rows
    for key, val in custom_data.items():
        if "::" not in key or "." not in key: continue
        try:
            module_obj_part, index_part = key.split(".", 1)
            module_name, obj_name = module_obj_part.split("::")
            index_tuple = tuple(int(x) for x in index_part.split("."))
            
            if module_name in mibBuilder.mibSymbols and obj_name in mibBuilder.mibSymbols[module_name]:
                symbol_obj = mibBuilder.mibSymbols[module_name][obj_name]
                base_oid = tuple(symbol_obj.name)
                
                if HIDE_NOT_ACCESSIBLE and hasattr(symbol_obj, 'getMaxAccess'):
                    if symbol_obj.getMaxAccess() == 'not-accessible':
                        continue

                snmp_val = generator.get_value(symbol_obj.getSyntax(), val)
                data_store[base_oid + index_tuple] = snmp_val
        except Exception:
            pass

    logger.info(f"Generated {len(data_store)} OID instances.")
    return data_store

async def run_simulator(port, community, mib_dir, data_path):
    mock_data = compile_and_generate_data(mib_dir, data_path)
    snmpEngine = engine.SnmpEngine()

    config.add_transport(snmpEngine, udp.DOMAIN_NAME, udp.UdpTransport().open_server_mode(('0.0.0.0', port)))
    config.add_v1_system(snmpEngine, 'my-area', community)
    config.add_vacm_user(snmpEngine, 2, 'my-area', 'noAuthNoPriv', (1, 3, 6), (1, 3, 6)) 

    snmpContext = context.SnmpContext(snmpEngine)
    snmpContext.unregister_context_name(v2c.OctetString('')) 
    snmpContext.register_context_name(v2c.OctetString(''), MockController(mock_data))

    cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.NextCommandResponder(snmpEngine, snmpContext)

    logger.info(f"✅ SIMULATOR RUNNING on UDP {port}")
    
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1061)
    parser.add_argument("--community", type=str, default="public")
    parser.add_argument("--mib-dir", type=str, required=True)
    parser.add_argument("--data-file", type=str, required=True)
    args = parser.parse_args()

    try:
        asyncio.run(run_simulator(args.port, args.community, args.mib_dir, args.data_file))
    except KeyboardInterrupt:
        pass
