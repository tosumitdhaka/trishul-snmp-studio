
window.WalkerModule = {
    lastData: null,

    init: function() { 
        this.toggleOptions(); // Set initial state
    },

    // Mutual Exclusion Logic
    toggleOptions: function() {
        const parseEl = document.getElementById("walk-parse-toggle");
        const mibEl = document.getElementById("walk-use-mibs");
        
        if (parseEl.checked) {
            // If Parsing is ON, we MUST use MIBs
            mibEl.checked = true;
            mibEl.disabled = true;
        } else {
            // If Parsing is OFF, user can choose
            mibEl.disabled = false;
        }
    },

    execute: async function() {
        const btn = document.querySelector("button[onclick='WalkerModule.execute()']");
        const output = document.getElementById("walk-output");
        const countBadge = document.getElementById("walk-count");
        
        // 1. Get Inputs
        const target = document.getElementById("walk-target").value;
        const port = parseInt(document.getElementById("walk-port").value);
        const community = document.getElementById("walk-comm").value;
        const oid = document.getElementById("walk-oid").value;
        const parse = document.getElementById("walk-parse-toggle").checked;
        const use_mibs = document.getElementById("walk-use-mibs").checked;

        // 2. UI Loading State
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        btn.disabled = true;
        output.textContent = "Walking...";
        output.className = "m-0 p-3 h-100 border-0 bg-light text-muted";

        try {
            // 3. Call API
            const res = await fetch('/api/walk/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, port, community, oid, parse, use_mibs })
            });

            const data = await res.json();
            console.log("Walker API Response:", data); // <--- Check Browser Console if this appears

            if (!res.ok) throw new Error(data.detail || "Walk failed");

            // 4. Handle Success
            this.lastData = data.data;
            countBadge.textContent = `${data.count} items`;
            
            // Update Style
            output.className = "m-0 p-3 h-100 border-0 bg-white text-dark font-monospace";

            // 5. Robust Rendering (Rely on Server Mode, not Checkbox)
            if (data.mode === 'parsed') {
                output.textContent = JSON.stringify(data.data, null, 2);
            } else {
                // Handle Raw (Array of strings)
                if (Array.isArray(data.data)) {
                    output.textContent = data.data.join("\n");
                } else {
                    output.textContent = String(data.data);
                }
            }

        } catch (e) {
            console.error("Walker Error:", e);
            output.textContent = `Error: ${e.message}`;
            output.className = "m-0 p-3 h-100 border-0 bg-light text-danger fw-bold";
            countBadge.textContent = "0 items";
            this.lastData = null;
        } finally {
            // 6. Reset Button
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    },

    copyToClipboard: function() {
        const text = document.getElementById("walk-output").textContent;
        navigator.clipboard.writeText(text).then(() => {
            // Visual feedback
            const btn = document.querySelector("button[onclick='WalkerModule.copyToClipboard()']");
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(() => btn.innerHTML = original, 1000);
        });
    },
    
    download: function(format) {
        if (!this.lastData) return alert("No data to export!");
        
        let content = "";
        let mime = "text/plain";
        let ext = "txt";

        if (format === 'json') {
            content = JSON.stringify(this.lastData, null, 2);
            mime = "application/json";
            ext = "json";
        } else if (format === 'csv') {
            if (Array.isArray(this.lastData) && this.lastData.length > 0) {
                // Flatten logic: grab all unique keys from all objects
                const allKeys = new Set();
                this.lastData.forEach(row => Object.keys(row).forEach(k => allKeys.add(k)));
                const keys = Array.from(allKeys);

                content = keys.join(",") + "\n";
                content += this.lastData.map(row => {
                    return keys.map(k => {
                        let val = row[k] === undefined ? "" : row[k];
                        // Escape quotes for CSV
                        if (typeof val === 'object') val = JSON.stringify(val).replace(/"/g, '""');
                        else val = String(val).replace(/"/g, '""');
                        return `"${val}"`;
                    }).join(",");
                }).join("\n");
            } else {
                content = "No CSV compatible data";
            }
            mime = "text/csv";
            ext = "csv";
        }

        const blob = new Blob([content], { type: mime });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `snmp_export_${Date.now()}.${ext}`;
        a.click();
        URL.revokeObjectURL(url);
    }
};
