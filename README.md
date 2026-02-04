# 🔱 Trishul-SNMP

**Replace 5+ SNMP tools with one modern platform**

- ✅ **Net-SNMP (CLI)** → Web UI
- ✅ **snmpsim** → Custom OID simulator
- ✅ **iReasoning ($500)** → Free MIB browser
- ✅ **snmptrapd** → Real-time trap receiver
- ✅ **Custom scripts** → JSON/CSV export

**One container. Zero cost. Full control.**

---

## 🎯 What Trishul-SNMP Replaces

✅ All Net-SNMP CLI tools (for testing)  
✅ Paid MIB browsers (iReasoning, MG-SOFT)  
✅ SNMP simulators (snmpsim, snmpsimd)  
✅ Trap receivers (snmptrapd + log parsing)  
✅ Multiple scattered tools → One unified platform

---

## 👥 Best For

- 🔧 Network engineers testing devices
- 🚀 DevOps testing SNMP integrations
- 📚 Students learning SNMP
- ✅ QA teams validating implementations
- 👥 Small teams needing trap monitoring

---

## ⚠️ Not For

- ❌ Production 24/7 monitoring (use Zabbix, PRTG)
- ❌ Enterprise-scale NMS (use SolarWinds, Cisco Prime)

---

## 🚀 Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/tosumitdhaka/trishul-snmp/main/install-trishul-snmp.sh | bash
```

Access: http://localhost:8080(opens in a new tab)
Default login: admin / admin123

---


**Professional SNMP Utilities**

A modern web-based SNMP toolkit for network engineers and administrators. Manage SNMP agents, send/receive traps, walk MIBs, and monitor network devices—all from a clean, intuitive interface.

---

## ✨ Features

### 📊 Dashboard
- Real-time system statistics
- Service status monitoring (Simulator, Trap Receiver)
- Quick access to all tools

### 🖥️ SNMP Simulator
- Start/stop SNMP agent on custom port
- Configure custom OID values (JSON editor)
- Real-time activity logging
- Support for standard and custom MIBs

### 🚶 Walk & Parse
- Execute SNMP walks with MIB resolution
- Parse results to structured JSON
- Export to JSON/CSV formats
- Copy output to clipboard
- Toggle MIB resolution on/off

### 📡 Trap Manager

**Sender:**
- Send SNMP v2c traps to any target
- Select traps from loaded MIBs
- Add custom VarBinds with type selection
- Browse MIB objects for VarBinds

**Receiver:**
- Capture incoming SNMP traps
- Real-time trap display with timestamps
- Resolve OIDs using loaded MIBs
- Export traps to JSON
- Clear trap history

### 📚 MIB Manager
- Upload and validate MIB files (.mib, .txt, .my)
- Automatic dependency detection
- Browse available traps by module
- View trap details (OID, objects, description)
- Send traps directly from MIB browser
- Failed MIB diagnostics

### ⚙️ Settings
- Update authentication credentials
- Secure password management
- Session-based authentication

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Ports available: 8080 (Web UI), 8000 (API), 1061/udp (SNMP), 1162/udp (Traps)

### Installation

#### Option 1: One shot installation and management
```
# Direct installation
curl -s  https://raw.githubusercontent.com/tosumitdhaka/trishul-snmp/refs/heads/main/install-trishul-snmp.sh | bash

# Managing app
# Download it first
curl -fsSL https://raw.githubusercontent.com/tosumitdhaka/snmp-studio/main/install-trishul-snmp.sh -o install-trishul-snmp.sh
chmod +x install-trishul-snmp.sh

# Management commands:
./install-trishul-snmp.sh up
./install-trishul-snmp.sh status
./install-trishul-snmp.sh logs
./install-trishul-snmp.sh restart
./install-trishul-snmp.sh down
./install-trishul-snmp.sh backup
./install-trishul-snmp.sh restore <backup file path>
```

#### Option 2: Docker Compose
```bash
# Clone repository
git clone <repository-url>
cd trishul-snmp

# Start services
docker-compose up -d

# Access Web UI
open http://localhost:8080
```

### Default Credentials
- **Username:** `admin`
- **Password:** `admin123`

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser                          │
│              http://localhost:8080                      │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌─────▼──────┐
    │ Frontend │          │  Backend   │
    │  Nginx   │◄────────►│  FastAPI   │
    │  :8080   │   API    │   :8000    │
    └──────────┘          └─────┬──────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
              ┌─────▼─────┐         ┌──────▼──────┐
              │ Simulator │         │  Receiver   │
              │ UDP: 1061 │         │ UDP: 1162   │
              └───────────┘         └─────────────┘
```

### Stack
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla), Bootstrap 5, Font Awesome
- **Backend:** Python 3.11, FastAPI, pysnmp, pysmi
- **Web Server:** Nginx (Alpine)
- **Deployment:** Docker, Docker Compose

---

## 📦 Project Structure

```
trishul-snmp/
├── backend/
│   ├── api/
│   │   └── routers/          # API endpoints
│   ├── core/
│   │   ├── config.py         # Configuration
│   │   ├── meta.py           # App metadata
│   │   ├── security.py       # Authentication
│   │   └── logging.py        # Logging setup
│   ├── services/
│   │   ├── simulator.py      # SNMP agent simulator
│   │   ├── walker.py         # SNMP walk operations
│   │   ├── trap_receiver.py  # Trap listener
│   │   ├── trap_sender.py    # Trap sender
│   │   └── mib_manager.py    # MIB operations
│   ├── data/
│   │   ├── mibs/             # MIB files
│   │   ├── configs/          # Configuration files
│   │   └── logs/             # Application logs
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py               # FastAPI app
├── frontend/
│   ├── src/
│   │   ├── css/
│   │   │   └── style.css     # Custom styles
│   │   ├── js/
│   │   │   ├── app.js        # Main app logic
│   │   │   └── modules/      # Page modules
│   │   ├── img/
│   │   │   └── trishul-icon.svg
│   │   ├── index.html        # Main HTML
│   │   ├── dashboard.html
│   │   ├── simulator.html
│   │   ├── walker.html
│   │   ├── traps.html
│   │   ├── mibs.html
│   │   └── settings.html
│   ├── nginx.conf            # Nginx configuration
│   └── Dockerfile
├── docker-compose.yml
├── .env                      # Environment variables
└── README.md
```

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Application Metadata
APP_NAME=Trishul SNMP
APP_VERSION=1.1.7
APP_AUTHOR=Sumit Dhaka
APP_DESCRIPTION=Professional SNMP Utilities

# SNMP Settings
SNMP_PORT=1061
SNMP_COMMUNITY=public
TRAP_PORT=1162

# Logging
LOG_LEVEL=INFO

# Security
SESSION_TIMEOUT=3600
```

### Update Version

```bash
# Edit .env file
nano .env
# Change: APP_VERSION=1.2.0

# Restart backend only (no rebuild needed)
docker-compose restart backend

# Version updates automatically in UI
```

---

## 📖 Usage Guide

### 1. SNMP Simulator

```bash
# Start simulator on port 1061
1. Navigate to Simulator page
2. Configure port and community
3. Click "Start"
4. Add custom OID values in JSON editor
5. Click "Save" to apply custom data

# Test with snmpwalk
snmpwalk -v2c -c public localhost:1061 system
```

### 2. Walk & Parse

```bash
# Walk a device
1. Enter target IP and port
2. Enter OID (e.g., IF-MIB::ifTable)
3. Enable "Parse to JSON" for structured output
4. Click "Run Walk"
5. Export results as JSON or CSV

# Example OIDs:
- system          # System information
- IF-MIB::ifTable # Interface table
- 1.3.6.1.2.1.1   # System MIB
```

### 3. Trap Manager

**Send Trap:**

```bash
1. Select trap from MIB dropdown (e.g., IF-MIB::linkDown)
2. Or enter custom trap OID
3. Add VarBinds (click "Browse" to select from MIBs)
4. Configure target IP and port
5. Click "Send Trap"
```

**Receive Traps:**

```bash
1. Configure receiver port (default: 1162)
2. Click "Start" to begin listening
3. Traps appear in real-time table
4. Click "Download All" to export as JSON
```

### 4. MIB Manager

```bash
# Upload MIBs
1. Click "Upload" button
2. Select .mib, .txt, or .my files
3. Click "Validate" to check syntax
4. Review dependencies (if any)
5. Click "Upload & Reload"

# Browse Traps
1. View all available traps from loaded MIBs
2. Search by name or module
3. Click "View Details" for trap information
4. Click "Send" to use trap in Trap Sender
```

---

## 🐳 Docker Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# View backend logs only
docker-compose logs -f backend

# Restart backend
docker-compose restart backend

# Rebuild after code changes
docker-compose build
docker-compose up -d

# Clean rebuild (remove cache)
docker-compose build --no-cache
docker-compose up -d

# Check service status
docker-compose ps

# Access backend shell
docker exec -it trishul-snmp-backend bash

# Access frontend shell
docker exec -it trishul-snmp-frontend sh
```

---

## 🔍 Troubleshooting

### Backend Not Starting

```bash
# Check logs
docker-compose logs backend

# Common issues:
# - Port 8000 already in use
# - Missing dependencies
# - Invalid .env configuration

# Solution:
docker-compose down
docker-compose up -d --force-recreate
```

### Frontend Shows 502 Error

```bash
# Check if backend is running
curl http://localhost:8000/api/meta

# Check nginx logs
docker-compose logs frontend

# Solution: Ensure backend is running
docker-compose restart backend
```

### MIB Upload Fails

```bash
# Check MIB syntax
# Ensure dependencies are uploaded first
# Check backend logs for detailed error

docker-compose logs backend | grep -i mib
```

### Trap Receiver Not Working

```bash
# Check if port is available
sudo netstat -tulpn | grep 1162

# Ensure firewall allows UDP traffic
sudo ufw allow 1162/udp

# Check receiver logs
docker-compose logs backend | grep -i trap
```

---

## 🧪 Testing

### Test SNMP Simulator

```bash
# Start simulator in UI (port 1061)

# Test with snmpget
snmpget -v2c -c public localhost:1061 sysDescr.0

# Test with snmpwalk
snmpwalk -v2c -c public localhost:1061 system
```

### Test Trap Sender/Receiver

```bash
# Terminal 1: Start receiver in UI (port 1162)

# Terminal 2: Send test trap
snmptrap -v2c -c public localhost:1162 '' \
  IF-MIB::linkDown \
  ifIndex i 1 \
  ifDescr s "eth0"

# Check UI - trap should appear in table
```

### Test Walk & Parse

```bash
# Start simulator first
# Then use Walk & Parse to query localhost:1061
# OID: system
# Should return parsed JSON with system information
```

---

## 🔐 Security

### Change Default Credentials

```bash
1. Login with admin/admin123
2. Navigate to Settings
3. Enter current password
4. Set new username and password
5. Click "Update Credentials"
6. Re-login with new credentials
```

### Authentication
- Session-based authentication with tokens
- Tokens stored in sessionStorage (cleared on logout)
- All API endpoints protected (except /login)
- Configurable session timeout (default: 3600s)

### Best Practices
- ✅ Change default credentials immediately
- ✅ Use strong passwords
- ✅ Run behind reverse proxy (nginx/Apache) in production
- ✅ Enable HTTPS in production
- ✅ Restrict network access to trusted IPs
- ✅ Keep Docker images updated

---

## 📊 API Documentation

### Endpoints

```
GET  /api/meta                    # App metadata
GET  /api/health                  # Health check

POST /api/settings/login          # Login
POST /api/settings/logout         # Logout
GET  /api/settings/check          # Check auth
POST /api/settings/update-auth    # Update credentials

GET  /api/simulator/status        # Simulator status
POST /api/simulator/start         # Start simulator
POST /api/simulator/stop          # Stop simulator
GET  /api/simulator/custom-data   # Get custom data
POST /api/simulator/custom-data   # Update custom data

POST /api/walker/walk             # Execute SNMP walk

GET  /api/traps/receiver/status   # Receiver status
POST /api/traps/receiver/start    # Start receiver
POST /api/traps/receiver/stop     # Stop receiver
GET  /api/traps/receiver/traps    # Get received traps
DELETE /api/traps/receiver/clear  # Clear traps
POST /api/traps/sender/send       # Send trap

GET  /api/mibs/list               # List MIBs
GET  /api/mibs/traps              # List traps
POST /api/mibs/upload             # Upload MIBs
POST /api/mibs/validate           # Validate MIBs
POST /api/mibs/reload             # Reload MIBs
```

### Example API Call

```bash
# Get app metadata
curl http://localhost:8000/api/meta

# Login
curl -X POST http://localhost:8000/api/settings/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Get simulator status (with auth token)
curl http://localhost:8000/api/simulator/status \
  -H "X-Auth-Token: your-token-here"
```

---

## 🛠️ Development

### Local Development Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Frontend (serve with any HTTP server)
cd frontend/src
python -m http.server 8080
```

### Code Style
- **Python:** PEP 8, type hints, docstrings
- **JavaScript:** ES6+, async/await, modular
- **HTML/CSS:** Semantic HTML5, Bootstrap 5 utilities

### Adding New Features
1. **Backend:** Add router in `backend/api/routers/`
2. **Frontend:** Add HTML in `frontend/src/`, JS module in `frontend/src/js/modules/`
3. **Update:** `app.js` routing and module map
4. **Test:** Rebuild containers and test

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

[Your License Here - e.g., MIT, Apache 2.0]

---

## 🙏 Acknowledgments

- [pysnmp](https://github.com/etingof/pysnmp) - SNMP library for Python
- [pysmi](https://github.com/etingof/pysmi) - SNMP SMI/MIB parser
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Bootstrap](https://getbootstrap.com/) - Frontend framework
- [Font Awesome](https://fontawesome.com/) - Icon library

---

## 📧 Support

- **Email:** tosumitdhaka@gmail.com
- **Documentation:** [Wiki](https://github.com/tosumitdhaka/trishul-snmp/wiki)

---

## 🔗 Links

- **Repository:** [trishul-snmp](https://github.com/tosumitdhaka/trishul-snmp)
- **Docker Hub:** [trishul-snmp-backend](https://github.com/tosumitdhaka/trishul-snmp/pkgs/container/trishul-snmp-backend)
- **Issues:** [GitHub Issues](https://github.com/tosumitdhaka/trishul-snmp/issues)
---

<div align="center">

**Made with 🔱 by Sumit Dhaka**

*Trishul SNMP - Professional SNMP Utilities*

</div>
