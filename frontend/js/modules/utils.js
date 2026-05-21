/**
 * js/modules/utils.js
 * ~~~~~~~~~~~~~~~~~~~
 * Shared utility functions used across all Trishul modules.
 * Loaded FIRST (before ws-client.js and all module scripts) so every
 * module can call TrishulUtils.* without any import ceremony.
 */
window.TrishulUtils = {
    THEME_KEY: 'trishul_theme',

    escapeHtml: function(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    encodeDataAttr: function(value) {
        try {
            return encodeURIComponent(JSON.stringify(value));
        } catch (_) {
            return '';
        }
    },

    decodeDataAttr: function(value, fallback) {
        try {
            return JSON.parse(decodeURIComponent(value));
        } catch (_) {
            return fallback;
        }
    },

    downloadText: function(filename, content, mimeType) {
        var blob = new Blob([content], { type: mimeType || 'text/plain;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },

    buildPanelPlaceholder: function(options) {
        var opts = options || {};
        var state = opts.state === 'loading' ? 'loading' : 'empty';
        var title = this.escapeHtml(opts.title || (state === 'loading' ? 'Loading' : 'Nothing to show'));
        var copy = opts.copy ? '<span class="app-panel-placeholder-copy">' + this.escapeHtml(opts.copy) + '</span>' : '';
        var compact = opts.compact ? ' is-compact' : '';
        var iconClass = String(opts.icon || 'fa-circle-info').replace(/[^a-z0-9\- ]/gi, '').trim() || 'fa-circle-info';
        var indicator = state === 'loading'
            ? '<span class="spinner-border spinner-border-sm app-tone-primary" role="status" aria-hidden="true"></span>'
            : '<span class="app-panel-placeholder-icon"><i class="fas ' + iconClass + '"></i></span>';
        var actionHtml = opts.actionHtml ? '<div class="app-panel-placeholder-action">' + String(opts.actionHtml) + '</div>' : '';
        return (
            '<div class="app-panel-placeholder is-' + state + compact + '">' +
                indicator +
                '<span class="app-panel-placeholder-title">' + title + '</span>' +
                copy +
                actionHtml +
            '</div>'
        );
    },

    toCsv: function(rows, columns) {
        var cols = Array.isArray(columns) ? columns : [];
        var escapeCell = function(value) {
            var text = String(value ?? '');
            return '"' + text.replace(/"/g, '""') + '"';
        };
        var header = cols.map(function(col) {
            return escapeCell(col.label || col.key || '');
        }).join(',');
        var body = rows.map(function(row) {
            return cols.map(function(col) {
                return escapeCell(row[col.key]);
            }).join(',');
        }).join('\n');
        return header + '\n' + body;
    },

    getTheme: function() {
        try {
            return localStorage.getItem(this.THEME_KEY) === 'dark' ? 'dark' : 'light';
        } catch (_) {
            return document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
        }
    },

    applyTheme: function(theme) {
        const nextTheme = theme === 'dark' ? 'dark' : 'light';

        document.documentElement.setAttribute('data-bs-theme', nextTheme);
        document.documentElement.style.colorScheme = nextTheme;

        try {
            localStorage.setItem(this.THEME_KEY, nextTheme);
        } catch (_) {}

        this.syncThemeToggle(nextTheme);
        return nextTheme;
    },

    syncThemeToggle: function(theme) {
        const activeTheme = theme === 'dark' ? 'dark' : 'light';
        const nextActionLabel = activeTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        const nextActionText = activeTheme === 'dark' ? 'Light' : 'Dark';

        document.querySelectorAll('[data-theme-toggle]').forEach(function(toggle) {
            const icon = toggle.querySelector('i');
            const label = toggle.querySelector('[data-theme-label]');

            toggle.setAttribute('aria-pressed', String(activeTheme === 'dark'));
            toggle.setAttribute('aria-label', nextActionLabel);
            toggle.title = nextActionLabel;

            if (icon) {
                icon.className = activeTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
            }
            if (label) {
                label.textContent = nextActionText;
            }
        });
    },

    toggleTheme: function() {
        const newTheme = this.getTheme() === 'dark' ? 'light' : 'dark';
        return this.applyTheme(newTheme);
    },

    initTheme: function() {
        const savedTheme = this.getTheme();
        this.applyTheme(savedTheme);
        return savedTheme;
    },

    setElementState: function(el, stateClass, value) {
        if (el) {
            el.className = stateClass;
            el.textContent = value;
        }
    },

    composeClasses: function() {
        var classes = [];

        var append = function(value) {
            if (!value) return;
            if (Array.isArray(value)) {
                value.forEach(append);
                return;
            }
            String(value).split(/\s+/).forEach(function(token) {
                if (token && classes.indexOf(token) === -1) {
                    classes.push(token);
                }
            });
        };

        Array.prototype.slice.call(arguments).forEach(append);
        return classes.join(' ');
    },

    normalizeBadgeTone: function(tone) {
        var value = String(tone || 'neutral').toLowerCase();
        if (value === 'secondary') value = 'neutral';
        if (value === 'error') value = 'danger';
        if (value === 'warn') value = 'warning';

        if (['primary', 'neutral', 'success', 'danger', 'warning', 'info', 'light'].indexOf(value) === -1) {
            return 'neutral';
        }
        return value;
    },

    normalizeStatusBadgeState: function(state) {
        var value = String(state || 'pending').toLowerCase();
        if (value === 'success') value = 'running';
        if (value === 'danger') value = 'error';
        if (value === 'warning') value = 'pending';

        if (['pending', 'starting', 'running', 'online', 'live', 'stopped', 'idle', 'offline', 'error'].indexOf(value) === -1) {
            return 'pending';
        }
        return value;
    },

    normalizeStatusTextState: function(state) {
        var value = String(state || 'idle').toLowerCase();
        if (value === 'success') value = 'running';
        if (value === 'danger') value = 'error';

        if (['pending', 'starting', 'warning', 'running', 'online', 'live', 'stopped', 'idle', 'offline', 'error', 'info'].indexOf(value) === -1) {
            return 'idle';
        }
        return value;
    },

    setStatusBadgeState: function(el, state, value, extraClasses) {
        if (!el) return;
        el.className = this.composeClasses(
            'badge app-status-badge',
            'is-' + this.normalizeStatusBadgeState(state),
            extraClasses
        );
        if (value != null) {
            el.textContent = value;
        }
    },

    setStatusTextState: function(el, state, value, extraClasses) {
        if (!el) return;
        el.className = this.composeClasses(
            extraClasses,
            'app-status-text',
            'is-' + this.normalizeStatusTextState(state)
        );
        if (value != null) {
            el.textContent = value;
        }
    },

    setAppBadgeTone: function(el, tone, value, extraClasses) {
        if (!el) return;
        el.className = this.composeClasses(
            'badge app-badge',
            'is-' + this.normalizeBadgeTone(tone),
            extraClasses
        );
        if (value != null) {
            el.textContent = value;
        }
    },

    setAccentBoxTone: function(el, tone, extraClasses) {
        if (!el) return;
        el.className = this.composeClasses(
            'app-accent-box',
            'is-' + this.normalizeBadgeTone(tone),
            extraClasses
        );
    },

    setAlertState: function(el, tone, value, extraClasses) {
        if (!el) return;
        var normalized = String(tone || 'secondary').toLowerCase();
        if (normalized === 'error') normalized = 'danger';
        if (normalized === 'neutral') normalized = 'secondary';
        if (['success', 'danger', 'warning', 'info', 'secondary'].indexOf(normalized) === -1) {
            normalized = 'secondary';
        }
        el.className = this.composeClasses(
            'alert',
            'small',
            'py-2',
            'mb-3',
            'alert-' + normalized,
            extraClasses
        );
        if (value != null) {
            el.textContent = value;
        }
        el.classList.remove('d-none');
    },

    formatClockTime: function(value, fallback) {
        var fallbackText = fallback || new Date().toLocaleTimeString([], {
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit'
        });

        if (value == null || value === '') return fallbackText;

        try {
            var date = null;

            if (value instanceof Date) {
                date = value;
            } else if (typeof value === 'number') {
                date = new Date(value < 1e10 ? value * 1000 : value);
            } else if (typeof value === 'string') {
                var trimmed = value.trim();
                var parsed = Date.parse(trimmed);

                if (!Number.isNaN(parsed)) {
                    date = new Date(parsed);
                } else {
                    var match = trimmed.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AP]M))?$/i);
                    if (match) {
                        var now = new Date();
                        var hours = parseInt(match[1], 10);
                        var minutes = parseInt(match[2], 10);
                        var seconds = parseInt(match[3] || '0', 10);
                        var meridiem = match[4] ? match[4].toUpperCase() : '';

                        if (meridiem === 'PM' && hours < 12) hours += 12;
                        if (meridiem === 'AM' && hours === 12) hours = 0;

                        date = new Date(
                            now.getFullYear(),
                            now.getMonth(),
                            now.getDate(),
                            hours,
                            minutes,
                            seconds
                        );
                    }
                }

                if (!date) return trimmed || fallbackText;
            } else {
                return fallbackText;
            }

            if (Number.isNaN(date.getTime())) return fallbackText;

            return date.toLocaleTimeString([], {
                hour: 'numeric',
                minute: '2-digit',
                second: '2-digit'
            });
        } catch (_) {
            return typeof value === 'string' && value.trim() ? value.trim() : fallbackText;
        }
    },

    /**
     * Convert an ISO timestamp string OR Unix timestamp to a human-readable
     * relative time string.
     */
    formatRelativeTime: function(dateString) {
        if (dateString == null || dateString === '') return '--';
        try {
            var date;
            if (typeof dateString === 'number') {
                date = dateString < 1e10 ? new Date(dateString * 1000)
                                         : new Date(dateString);
            } else {
                date = new Date(dateString);
            }

            var timeMs = date.getTime();

            // Treat unparseable dates or Unix epoch as "never"
            if (isNaN(timeMs) || timeMs < 1000) return '--';

            var now     = new Date();
            var diffMs  = now - date;
            var diffSec = Math.floor(diffMs / 1000);
            var diffMin = Math.floor(diffSec / 60);
            var diffHr  = Math.floor(diffMin / 60);
            var diffDay = Math.floor(diffHr  / 24);

            if (diffSec < 5)   return 'just now';
            if (diffSec < 60)  return diffSec + 's ago';
            if (diffMin < 60)  return diffMin + 'm ago';
            if (diffHr  < 24)  return diffHr  + 'h ago';
            if (diffDay < 7)   return diffDay  + 'd ago';
            return date.toLocaleDateString();
        } catch (_) {
            return '--';
        }
    },

    /**
     * Convert a duration in whole seconds to a compact human-readable string.
     */
    formatUptime: function(seconds) {
        if (seconds == null || seconds < 0) return '--';
        seconds = Math.floor(seconds);
        if (seconds < 60) {
            return seconds + 's';
        }
        if (seconds < 3600) {
            var m = Math.floor(seconds / 60);
            var s = seconds % 60;
            return s > 0 ? (m + 'm ' + s + 's') : (m + 'm');
        }
        if (seconds < 86400) {
            var h = Math.floor(seconds / 3600);
            var m = Math.floor((seconds % 3600) / 60);
            return m > 0 ? (h + 'h ' + m + 'm') : (h + 'h');
        }
        var d = Math.floor(seconds / 86400);
        var h = Math.floor((seconds % 86400) / 3600);
        return h > 0 ? (d + 'd ' + h + 'h') : (d + 'd');
    },

    /**
     * Show a dismissible toast-style notification banner at top-right.
     */
    showNotification: function(message, type, duration) {
        type     = type     || 'info';
        duration = duration || 3000;

        var icon = 'fa-info-circle';
        var tone = String(type).toLowerCase();

        if (tone === 'danger') {
            tone = 'error';
        }

        if      (tone === 'success') { icon = 'fa-check-circle'; }
        else if (tone === 'error')   { icon = 'fa-exclamation-circle'; }
        else if (tone === 'warning') { icon = 'fa-exclamation-triangle'; }
        else                         { tone = 'info'; }

        var banner = document.createElement('div');
        banner.className = 'app-toast app-toast--' + tone;
        banner.setAttribute('role', 'status');
        banner.setAttribute('aria-live', 'polite');
        banner.style.top = (80 + document.querySelectorAll('.app-toast').length * 76) + 'px';

        var iconWrap = document.createElement('div');
        iconWrap.className = 'app-toast-icon';
        var iconEl = document.createElement('i');
        iconEl.className = 'fas ' + icon;
        iconWrap.appendChild(iconEl);
        banner.appendChild(iconWrap);

        var body = document.createElement('div');
        body.className = 'app-toast-body';
        body.textContent = String(message ?? '');
        banner.appendChild(body);

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close';
        closeBtn.setAttribute('aria-label', 'Dismiss notification');
        closeBtn.addEventListener('click', function() {
            if (banner.parentNode) {
                banner.remove();
            }
        });
        banner.appendChild(closeBtn);

        document.body.appendChild(banner);
        setTimeout(function() { if (banner.parentNode) banner.remove(); }, duration);
    },
};

document.addEventListener('DOMContentLoaded', () => {
    if (window.TrishulUtils && TrishulUtils.initTheme) {
        TrishulUtils.initTheme();
    }
});
