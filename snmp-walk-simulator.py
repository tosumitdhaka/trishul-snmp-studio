import sys
import os
import random
import string
import logging
import asyncio
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.smi import builder, compiler, error
from pysnmp.proto.api import v2c

# ================= CONFIGURATION =================
LISTEN_PORT = 1061
COMMUNITY = "public"
MIB_DIR = "./mibs"
TARGET_MIBS = ["FORTINET-FORTIGATE-MIB", "FORTINET-CORE-MIB"]
# =================================================

logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)

class MibDataGenerator:
    def get_random_value(self, syntax_obj):
        try:
            type_name = syntax_obj.__class__.__name__

            # --- FIXED LOGIC v12 ---
            # Explicitly catch AutonomousType (used by fgProcessorType)
            if any(x in type_name for x in ["Oid", "ObjectIdentifier", "AutonomousType"]):
                return v2c.ObjectIdentifier("1.3.6.1.4.1.12356.101.1")

            elif "Integer" in type_name: return v2c.Integer32(random.randint(1, 100))
            elif "Unsigned" in type_name: return v2c.Unsigned32(random.randint(1, 10000))
            elif "Gauge" in type_name: return v2c.Gauge32(random.randint(1, 100))
            elif "Counter64" in type_name: return v2c.Counter64(random.randint(1000000, 999999999))
            elif "Counter" in type_name: return v2c.Counter32(random.randint(1000, 999999))
            elif "TimeTicks" in type_name: return v2c.TimeTicks(random.randint(0, 5000000))
            elif "IpAddress" in type_name: return v2c.IpAddress("127.0.0.1")
            elif "String" in type_name: return v2c.OctetString(f"Sim-{random.randint(1,99)}")
            else: return v2c.Integer32(0)
        except:
            return v2c.Integer32(0)

class MockController:
    def __init__(self, data_dict):
        self.db = data_dict
        self.sorted_oids = sorted(self.db.keys())

    def _read_vars(self, var_binds):
        rsp = []
        for oid, val in var_binds:
            try:
                key = tuple(oid)
                if key in self.db:
                    rsp.append((v2c.ObjectIdentifier(oid), self.db[key]))
                else:
                    rsp.append((v2c.ObjectIdentifier(oid), v2c.NoSuchObject()))
            except:
                rsp.append((v2c.ObjectIdentifier(oid), v2c.GenErr()))
        return rsp

    def _read_next_vars(self, var_binds):
        rsp = []
        for oid, val in var_binds:
            try:
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
            except:
                rsp.append((v2c.ObjectIdentifier(oid), v2c.GenErr()))
        return rsp

    def read_variables(self, *var_binds, **kwargs): return self._read_vars(var_binds)
    def read_next_variables(self, *var_binds, **kwargs): return self._read_next_vars(var_binds)
    def write_variables(self, *var_binds, **kwargs): return [(b[0], v2c.NotWritable()) for b in var_binds]

def compile_and_generate_data():
    mibBuilder = builder.MibBuilder()
    compiler.add_mib_compiler(mibBuilder, sources=[f'file://{os.path.abspath(MIB_DIR)}'])
    try:
        mibBuilder.load_modules(*TARGET_MIBS)
    except Exception as e:
        logging.error(f"MIB Load Error: {e}")
        sys.exit(1)

    generator = MibDataGenerator()
    data_store = {}

    if hasattr(mibBuilder, 'mibSymbols'):
        for module_name, symbols in mibBuilder.mibSymbols.items():
            for symbol_name, symbol_obj in symbols.items():
                if not hasattr(symbol_obj, 'name') or not hasattr(symbol_obj, 'getSyntax'):
                    continue

                base_oid = tuple(symbol_obj.name)

                if symbol_obj.__class__.__name__ == 'MibScalar':
                    val = generator.get_random_value(symbol_obj.getSyntax())
                    data_store[base_oid + (0,)] = val

                elif symbol_obj.__class__.__name__ == 'MibTableColumn':
                    for i in [1, 2]:
                        val = generator.get_random_value(symbol_obj.getSyntax())
                        data_store[base_oid + (i,)] = val

    logging.info(f"Generated {len(data_store)} OID instances.")
    return data_store

async def run_simulator():
    mock_data = compile_and_generate_data()
    snmpEngine = engine.SnmpEngine()

    config.add_transport(snmpEngine, udp.DOMAIN_NAME, udp.UdpTransport().open_server_mode(('0.0.0.0', LISTEN_PORT)))
    config.add_v1_system(snmpEngine, 'my-area', COMMUNITY)
    config.add_vacm_user(snmpEngine, 2, 'my-area', 'noAuthNoPriv', (1, 3, 6), (1, 3, 6))

    snmpContext = context.SnmpContext(snmpEngine)
    snmpContext.unregister_context_name(v2c.OctetString(''))
    snmpContext.register_context_name(v2c.OctetString(''), MockController(mock_data))

    cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.NextCommandResponder(snmpEngine, snmpContext)

    print(f"\n✅ SIMULATOR RUNNING on UDP {LISTEN_PORT}")
    print(f"   Target: 127.0.0.1:{LISTEN_PORT}")

    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(run_simulator())
    except KeyboardInterrupt:
        pass