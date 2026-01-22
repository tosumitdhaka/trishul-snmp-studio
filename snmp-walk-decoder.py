#!/usr/bin/env python3
import subprocess
import re
import json
import sys
import os
import time

# ================= CONFIGURATION =================
TARGET_HOST = os.getenv("SNMP_HOST", "localhost")
TARGET_PORT = os.getenv("SNMP_PORT", "161")
COMMUNITY = os.getenv("SNMP_COMMUNITY", "public")
ROOT_OID = os.getenv("SNMP_OID", ".")
MIBS_TO_LOAD = os.getenv("SNMP_MIBS", "ALL")
MIB_DIRS = os.getenv("MIB_DIRS", "./mibs")

DEBUG_MODE = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
# =================================================

def get_category_from_oid(oid_string):
    """
    Extracts the category name directly from the input OID.
    Input:  FORTINET-FORTIGATE-MIB::fgProcessors
    Output: fgProcessors
    """
    if not oid_string or oid_string == ".":
        return "General"

    # Split by :: if present
    if "::" in oid_string:
        return oid_string.split("::")[1]

    # Return raw OID if no module prefix
    return oid_string

def run_snmpwalk(host, port, community, oid, mib_dirs, mibs_to_load):
    target = f"{host}:{port}"
    cmd = ["snmpwalk", "-v2c", "-c", community, "-O", "e"]

    if mib_dirs:
        cmd.extend(["-M", f"+{mib_dirs}"])

    cmd.extend(["-m", mibs_to_load])
    cmd.extend([target, oid])

    if DEBUG_MODE:
        print(f"DEBUG: Command: {' '.join(cmd)}", file=sys.stderr)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if DEBUG_MODE and not result.stdout:
            print("DEBUG: snmpwalk returned no output (Empty OID?).", file=sys.stderr)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: snmpwalk failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: 'snmpwalk' command not found.", file=sys.stderr)
        sys.exit(1)

def parse_snmp_output(lines):
    parsed_data = {}

    regex_mib = re.compile(r'^(.*?)::(.*?)\.(.*?) (.*)$')
    regex_raw = re.compile(r'^(.*?)\.(.*?) (.*)$')

    for line in lines:
        module = "Unknown"
        obj_name = ""
        index = ""
        raw_value = ""

        match = regex_mib.match(line)
        if match:
            module = match.group(1)
            obj_name = match.group(2)
            index = match.group(3).strip()
            raw_value = match.group(4).strip()
        else:
            match_raw = regex_raw.match(line)
            if match_raw:
                full_name = match_raw.group(1)
                if "." in full_name:
                    obj_name = full_name
                    index = match_raw.group(2)
                else:
                    obj_name = full_name
                    index = match_raw.group(2)
                raw_value = match_raw.group(3).strip()
            else:
                continue

        if raw_value.startswith("= "):
            raw_value = raw_value[2:]

        if ": " in raw_value:
            val_type, val_data = raw_value.split(": ", 1)
        else:
            val_type = "Unknown"
            val_data = raw_value

        val_data = val_data.strip('"')

        if index not in parsed_data:
            parsed_data[index] = {"index": index, "labels": {}, "metrics": {}}

        # Classification Logic
        is_metric = False
        metric_types = ["Counter32", "Counter64", "Gauge32", "Integer", "INTEGER", "Unsigned32", "TimeTicks"]

        if any(t in val_type for t in metric_types):
            if any(x in obj_name.lower() for x in ["index", "id", "name", "descr", "serial", "mac", "type", "version"]):
                is_metric = False
            else:
                is_metric = True

        if "TimeTicks" in val_type:
            ticks_match = re.search(r'\((\d+)\)', val_data)
            if ticks_match:
                val_data = int(ticks_match.group(1)) / 100.0
            is_metric = True

        if is_metric:
            try:
                if "(" in str(val_data) and ")" in str(val_data):
                    val_data = re.search(r'\((\d+)\)', str(val_data)).group(1)

                clean_str = str(val_data).split()[0]
                clean_val = float(clean_str)
                if clean_val.is_integer():
                    clean_val = int(clean_val)

                parsed_data[index]["metrics"][obj_name] = {
                    "value": clean_val,
                    "module": module
                }
            except (ValueError, AttributeError, IndexError):
                parsed_data[index]["labels"][obj_name] = val_data
        else:
            parsed_data[index]["labels"][obj_name] = val_data

    return parsed_data

def convert_to_final_json(parsed_data, target_host, global_category):
    output_list = []
    current_time_epoch = int(time.time())

    for idx, entry in parsed_data.items():
        row_labels = entry["labels"]
        row_labels["snmp_index"] = entry["index"]

        for metric_name, metric_data in entry["metrics"].items():
            json_obj = {
                "metric_name": metric_name,
                "value": metric_data["value"],
                "mib_module": metric_data["module"],
                "metric_category": global_category,  # Applied from CLI input
                "agent_host": target_host,
                "timestamp": current_time_epoch,
                "labels": row_labels.copy()
            }
            output_list.append(json_obj)
    return output_list

if __name__ == "__main__":
    # 1. Determine Category from CLI Input
    category = get_category_from_oid(ROOT_OID)

    # 2. Run Walk
    raw_lines = run_snmpwalk(TARGET_HOST, TARGET_PORT, COMMUNITY, ROOT_OID, MIB_DIRS, MIBS_TO_LOAD)

    # 3. Parse Data
    grouped = parse_snmp_output(raw_lines)

    # 4. Convert to JSON with Global Category
    final_json = convert_to_final_json(grouped, TARGET_HOST, category)

    print(json.dumps(final_json, indent=2))

