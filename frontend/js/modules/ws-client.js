window.WsClient = (function () {
    const PING_MS = 30000;
    const BACKOFF_BASE = 1000;
    const BACKOFF_MAX = 30000;
    const PONG_TIMEOUT = 5000;

    let socket = null;
    let token = null;
    let pingTimer = null;
    let pongTimer = null;
    let reconnectTimer = null;
    let reconnectDelay = BACKOFF_BASE;
    let intentional = false;

    function socketUrl(value) {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        return protocol + '//' + location.host + '/api/ws?token=' + encodeURIComponent(value);
    }

    function setStatus(state) {
        const el = document.getElementById('ws-status-dot');
        if (!el) return;
        el.className = 'ws-dot ws-dot-' + state;
        const labels = {
            connecting: 'WS: Connecting...',
            online: 'WS: Live',
            offline: 'WS: Offline',
            unauthorized: 'WS: Unauthorized'
        };
        el.title = labels[state] || '';
    }

    function emit(type, detail) {
        window.dispatchEvent(new CustomEvent('trishul:ws:' + type, { detail: detail }));
    }

    function stopPing() {
        clearInterval(pingTimer);
        clearTimeout(pongTimer);
        pingTimer = null;
        pongTimer = null;
    }

    function startPing() {
        stopPing();
        pingTimer = window.setInterval(function () {
            if (!socket || socket.readyState !== WebSocket.OPEN) return;
            socket.send('ping');
            clearTimeout(pongTimer);
            pongTimer = window.setTimeout(function () {
                if (socket) socket.close(4000, 'pong timeout');
            }, PONG_TIMEOUT);
        }, PING_MS);
    }

    function scheduleReconnect() {
        if (intentional || !token) return;
        clearTimeout(reconnectTimer);
        reconnectTimer = window.setTimeout(function () {
            connectSocket(token);
        }, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, BACKOFF_MAX);
    }

    function connectSocket(nextToken) {
        setStatus('connecting');

        try {
            socket = new WebSocket(socketUrl(nextToken));
        } catch (error) {
            scheduleReconnect();
            return;
        }

        socket.onopen = function () {
            reconnectDelay = BACKOFF_BASE;
            setStatus('online');
            startPing();
            emit('open', null);
        };

        socket.onmessage = function (event) {
            if (event.data === 'pong') {
                clearTimeout(pongTimer);
                pongTimer = null;
                return;
            }

            try {
                const message = JSON.parse(event.data);
                if (message && message.type) {
                    emit(message.type, message);
                }
            } catch (error) {
            }
        };

        socket.onclose = function (event) {
            stopPing();
            setStatus(event.code === 4001 ? 'unauthorized' : 'offline');
            emit('close', { code: event.code, reason: event.reason });
            if (event.code !== 4001) {
                scheduleReconnect();
            }
        };

        socket.onerror = function () {
        };
    }

    return {
        connect: function (nextToken) {
            if (!nextToken) return;
            token = nextToken;
            intentional = false;

            if (socket && socket.readyState !== WebSocket.CLOSED) {
                socket.close(1000, 'reconnect');
            }
            connectSocket(nextToken);
        },
        disconnect: function () {
            intentional = true;
            token = null;
            stopPing();
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
            if (socket) {
                socket.close(1000, 'logout');
                socket = null;
            }
            setStatus('offline');
        },
        isConnected: function () {
            return Boolean(socket && socket.readyState === WebSocket.OPEN);
        }
    };
})();
