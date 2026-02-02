window.SimulatorModule = {
    intervalId: null,

    init: function() {
        this.destroy();
        
        const area = document.getElementById("sim-log-area");
        if (area && window.AppState.logs.length > 0) {
            area.innerHTML = window.AppState.logs.join("");
            area.scrollTop = area.scrollHeight;
        } else if (area) {
            area.innerHTML = '<div class="text-muted small p-2">Waiting for events...</div>';
        }

        if (window.AppState.simulator) {
            this.updateUI(window.AppState.simulator);
        } else {
            this.setButtons(false); 
        }

        this.loadCustomData();

        this.fetchStatus();
        this.intervalId = setInterval(() => this.fetchStatus(), 10000);
    },

    destroy: function() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    },

    // FIX: Updated API path
    loadCustomData: async function() {
        const editor = document.getElementById('custom-data-editor');
        if (!editor) return;

        try {
            const res = await fetch('/api/simulator/data');
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const data = await res.json();
            editor.value = JSON.stringify(data, null, 2);
        } catch (e) {
            console.error('Failed to load custom data:', e);
            editor.value = '{}';
        }
    },

    // FIX: Updated API path and response handling
    saveCustomData: async function() {
        const editor = document.getElementById('custom-data-editor');
        const content = editor.value;

        try {
            // Validate JSON
            const json = JSON.parse(content);

            // Save
            const res = await fetch('/api/simulator/data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(json)
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            const data = await res.json();

            // Log success
            this.log(`<span class="text-success">Custom data saved: ${data.message}</span>`);
            
            // Show notification
            const banner = document.createElement('div');
            banner.className = 'alert alert-success alert-dismissible fade show position-fixed';
            banner.style.cssText = 'top: 80px; right: 20px; z-index: 9999;';
            banner.innerHTML = `
                <i class="fas fa-check-circle me-2"></i> ${data.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            document.body.appendChild(banner);
            setTimeout(() => banner.remove(), 3000);

        } catch (e) {
            console.error('Save error:', e);
            alert('Failed to save custom data:\n\n' + e.message);
        }
    },

    start: async function() {
        const port = document.getElementById("sim-config-port").value;
        const comm = document.getElementById("sim-config-comm").value;
        
        this.log(`Starting simulator on Port ${port}...`);
        
        await fetch('/api/simulator/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port: parseInt(port), community: comm })
        });
        this.fetchStatus();
    },

    stop: async function() {
        this.log("Stopping simulator...");
        await fetch('/api/simulator/stop', { method: 'POST' });
        this.fetchStatus();
    },

    restart: async function() {
        this.log("Restarting...");
        await this.stop();
        setTimeout(() => this.start(), 1000);
    },

    fetchStatus: async function() {
        try {
            const res = await fetch('/api/simulator/status');
            if (!res.ok) return;
            const data = await res.json();
            
            window.AppState.simulator = data;
            this.updateUI(data);
        } catch (e) {
            console.error("Sim status error", e);
        }
    },

    updateUI: function(data) {
        const badge = document.getElementById("sim-badge");
        const stateText = document.getElementById("sim-state-text");
        const detailText = document.getElementById("sim-detail-text");
        
        if (!badge) return;

        if (data.running) {
            badge.className = "badge bg-success";
            badge.textContent = "RUNNING";
            stateText.textContent = "Online";
            stateText.className = "mb-0 text-success fw-bold";
            detailText.innerHTML = `Listening on <strong>UDP ${data.port}</strong> <br> Community: <code>${data.community}</code> <br> PID: ${data.pid}`;
            
            this.setButtons(true);
            
            const pInput = document.getElementById("sim-config-port");
            const cInput = document.getElementById("sim-config-comm");
            if(pInput && document.activeElement !== pInput) pInput.value = data.port;
            if(cInput && document.activeElement !== cInput) cInput.value = data.community;
        } else {
            badge.className = "badge bg-secondary";
            badge.textContent = "STOPPED";
            stateText.textContent = "Offline";
            stateText.className = "mb-0 text-secondary fw-bold";
            detailText.textContent = "Service is stopped.";
            
            this.setButtons(false);
        }
    },

    setButtons: function(isRunning) {
        const btnStart = document.getElementById("btn-start");
        const btnStop = document.getElementById("btn-stop");
        const btnRestart = document.getElementById("btn-restart");
        
        if(!btnStart) return;
        btnStart.disabled = isRunning;
        btnStop.disabled = !isRunning;
        btnRestart.disabled = !isRunning;
    },

    log: function(msg, type = 'info') {
        const area = document.getElementById("sim-log-area");
        const time = new Date().toLocaleTimeString();
        
        let icon = 'fa-info-circle';
        let color = 'text-muted';
        
        if (type === 'success') {
            icon = 'fa-check-circle';
            color = 'text-success';
        } else if (type === 'error') {
            icon = 'fa-exclamation-circle';
            color = 'text-danger';
        } else if (type === 'warning') {
            icon = 'fa-exclamation-triangle';
            color = 'text-warning';
        }
        
        const html = `
            <div class="border-bottom py-2 px-2">
                <span class="text-muted small">[${time}]</span>
                <i class="fas ${icon} ${color} ms-2"></i>
                <span class="ms-2">${msg}</span>
            </div>
        `;
        
        window.AppState.logs.push(html);
        if (window.AppState.logs.length > 100) window.AppState.logs.shift();

        if(area) {
            if(area.textContent.includes("Waiting for events")) area.innerHTML = "";
            area.innerHTML += html;
            area.scrollTop = area.scrollHeight;
        }
    },

};
