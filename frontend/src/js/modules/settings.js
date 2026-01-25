window.SettingsModule = {
    init: function() {
        document.getElementById("set-auth-user").value = "admin";
    },

    updateAuth: async function(e) {
        e.preventDefault();
        
        const user = document.getElementById("set-auth-user").value;
        const pass = document.getElementById("set-auth-pass").value;
        // FIX: Renamed variable to avoid conflict with window.confirm()
        const confirmPass = document.getElementById("set-auth-pass-confirm").value; 
        const msgBox = document.getElementById("auth-msg");
        
        // Validation
        if (pass !== confirmPass) {
            msgBox.textContent = "Passwords do not match!";
            msgBox.classList.remove("d-none");
            return;
        }
        if (pass.length < 4) {
            msgBox.textContent = "Password is too weak (min 4 chars).";
            msgBox.classList.remove("d-none");
            return;
        }
        
        msgBox.classList.add("d-none");

        // Now window.confirm() works correctly
        if(!window.confirm("Are you sure you want to change credentials? You will be logged out.")) return;

        try {
            const res = await fetch('/api/settings/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, password: pass })
            });

            if (res.ok) {
                alert("Credentials updated! Reloading...");
                location.reload();
            } else {
                msgBox.textContent = "Server error updating credentials.";
                msgBox.classList.remove("d-none");
            }
        } catch (e) {
            console.error(e);
            alert("Error connecting to server.");
        }
    }
};
