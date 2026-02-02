window.DashboardModule = {
    intervalId: null,

    init: function() {
        this.loadStats();
        this.intervalId = setInterval(() => this.loadStats(), 5000);
    },

    destroy: function() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    },

    loadStats: async function() {
        try {
            // MIB Stats
            const mibRes = await fetch('/api/mibs/status');
            const mibData = await mibRes.json();
            document.getElementById('stat-mibs').textContent = mibData.loaded;
            
            const trapRes = await fetch('/api/mibs/traps');
            const trapData = await trapRes.json();
            document.getElementById('stat-traps').textContent = trapData.traps.length;
            
            // Simulator Status
            const simRes = await fetch('/api/simulator/status');
            const simData = await simRes.json();
            const simEl = document.getElementById('stat-simulator');
            if (simData.running) {
                simEl.textContent = 'Online';
                simEl.className = 'mb-0 text-success fw-bold';
            } else {
                simEl.textContent = 'Offline';
                simEl.className = 'mb-0 text-secondary';
            }
            
            // Trap Receiver Status
            const recRes = await fetch('/api/traps/status');
            const recData = await recRes.json();
            const recEl = document.getElementById('stat-receiver');
            if (recData.running) {
                recEl.textContent = 'Running';
                recEl.className = 'mb-0 text-success fw-bold';
            } else {
                recEl.textContent = 'Stopped';
                recEl.className = 'mb-0 text-secondary';
            }
            
        } catch (e) {
            console.error('Failed to load stats:', e);
        }
    }
};
