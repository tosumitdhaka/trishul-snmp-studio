const API_BASE = "/api";
const HTML_CACHE = {}; 
let currentModule = null; 

// Global State
window.AppState = {
    simulator: null,
    logs: []
};

document.addEventListener("DOMContentLoaded", () => {
    // 1. Initialize Auth Flow
    initAuth();
});

async function initAuth() {
    const overlay = document.getElementById("auth-overlay");
    const wrapper = document.getElementById("wrapper");
    const statusText = document.getElementById("auth-status-text");

    try {
        // Attempt to hit a protected endpoint
        const res = await fetch('/api/settings/check');
        
        if (res.ok) {
            // 1. Stop Overlay from blocking clicks immediately
            overlay.style.pointerEvents = 'none';
            
            // 2. Reveal the App (behind the overlay)
            wrapper.style.display = 'flex';
            
            // 3. Initialize Logic (Sidebar, Routing) immediately
            initializeAppLogic();

            // 4. Start Fade Out
            overlay.style.transition = "opacity 0.5s ease";
            overlay.style.opacity = '0';
            
            // 5. Remove from DOM flow after fade
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 500);
            
        } else {
            statusText.textContent = "Authentication Required. Please refresh.";
            statusText.className = "mt-3 text-danger fw-bold";
        }
    } catch (e) {
        statusText.textContent = "Connection Failed. Backend offline?";
        statusText.className = "mt-3 text-danger fw-bold";
    }
}


function initializeAppLogic() {
    // 1. Sidebar Toggle
    const sidebarToggle = document.querySelector('#sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', e => {
            e.preventDefault();
            document.body.classList.toggle('sb-sidenav-toggled');
        });
    }

    // 2. Health & Routing
    checkBackendHealth();
    window.addEventListener('hashchange', handleRouting);
    handleRouting(); 
}

async function handleRouting() {
    let moduleName = window.location.hash.substring(1) || 'dashboard';
    
    // 1. Cleanup Previous Module
    if (currentModule && typeof currentModule.destroy === 'function') {
        currentModule.destroy();
    }
    
    // 2. Update Sidebar Active State
    document.querySelectorAll('.list-group-item').forEach(el => {
        el.classList.remove('active');
        if(el.getAttribute('href') === `#${moduleName}`) el.classList.add('active');
    });

    // 3. Load Content
    await loadModule(moduleName);
}

async function loadModule(moduleName) {
    const container = document.getElementById("main-content");
    const title = document.getElementById("page-title");

    const titles = {
        'dashboard': 'System Overview',
        'simulator': 'Simulator Manager',
        'walker': 'Walk & Parse Studio',
        'files': 'File Manager',
        'settings': 'Settings'
    };
    title.textContent = titles[moduleName] || 'SNMP Studio';

    if (!HTML_CACHE[moduleName]) {
        try {
            container.innerHTML = '<div class="text-center mt-5"><div class="spinner-border text-primary"></div></div>';
            const res = await fetch(`${moduleName}.html`);
            if (!res.ok) throw new Error("Module not found");
            HTML_CACHE[moduleName] = await res.text();
        } catch (e) {
            container.innerHTML = `<div class="alert alert-danger">Error: ${e.message}</div>`;
            return;
        }
    }

    container.innerHTML = HTML_CACHE[moduleName];

    // 4. Initialize Logic
    const moduleMap = {
        'dashboard': window.DashboardModule,
        'simulator': window.SimulatorModule,
        'walker': window.WalkerModule,
        'files': window.FilesModule,
        'settings': window.SettingsModule
    };

    if (moduleMap[moduleName]) {
        currentModule = moduleMap[moduleName]; // Set active module
        if(typeof currentModule.init === 'function') {
            currentModule.init();
        }
    }
}

// ... (keep checkBackendHealth as is) ...
async function checkBackendHealth() {
    const badge = document.getElementById("backend-status");
    try {
        const res = await fetch(`${API_BASE}/meta`);
        await res.json();
        badge.className = "badge bg-success";
        badge.textContent = "Online";
    } catch (e) {
        badge.className = "badge bg-danger";
        badge.textContent = "Offline";
    }
}
