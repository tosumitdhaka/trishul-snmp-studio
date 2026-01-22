# SNMP WALK UTILS (In Development)

## 1. SNMP Walk Simulator
Load a custom mib file, parse it and use it to simulate response to any SNMP Walk commands on related OIDs.
- Listens on localhost and 161 port, can be customized

## 2. SNMP Walk Decoder
Performs SNMP Walk on a UDP endpoint, parses the data map it to json format.
- Uses custom environment variables for IP, port, MIB location, etc